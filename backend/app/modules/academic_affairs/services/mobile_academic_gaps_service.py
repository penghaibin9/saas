"""Round7 教务四端能力补齐：学生注册自助 / 挂科可选重修 / 考勤自查 / 校历 / 清考可见 / 打印。

由 mobile.py / portal academic_service 直接调用；复用既有 registration/makeup/attendance/calendar/exam 服务。
"""
from __future__ import annotations

import json
import importlib
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import func, select, text
from app.core.exceptions import AppException, no_permission, not_found
from app.modules.academic_affairs.services.mobile_academic_affairs_service import _me, _ns
from app.services.db_service import _iso, _tid, session


_REG_TYPE_LABEL = {"ENROLL": "入学注册", "ANNUAL": "学年注册", "SEMESTER": "学期注册"}


# ═══════════ 学生注册自助 ═══════════

def registration_my(user, *, page=None, page_size=20, batch_id=None) -> dict:
    """本人注册批次与办理状态。

    学生 PC 仍可用 ``page=None`` 获取旧合同；移动端必须传明确页码，避免把
    全校多年开放批次和逐批次查询塞进手机。无论哪种读取方式，个人注册、暂缓和
    异常都采用每类一次批量查询，不再产生 ``1 + 3N`` 查询。
    """
    from app.models import (AaRegistration, AaRegistrationBatch, AaRegistrationDeferral,
                            AaRegistrationException)
    from app.modules.academic_affairs.services.academic_affairs_service import (
        registration_self_service_window_state,
    )

    if page is not None:
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "注册批次分页参数非法") from exc
        if page < 1 or page > 100000 or page_size < 1 or page_size > 50:
            raise AppException("VALIDATION_ERROR", "注册批次分页参数超出范围")
    exact_batch_id = None
    if batch_id not in (None, ""):
        try:
            exact_batch_id = int(batch_id)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "注册批次标识非法") from exc

    with session() as db:
        stu = _me(db, user)
        tenant_id = _tid()
        now = datetime.utcnow()
        base_filters = [
            AaRegistrationBatch.tenant_id == tenant_id,
            AaRegistrationBatch.is_deleted.is_(False),
        ]
        if exact_batch_id is not None:
            base_filters.append(AaRegistrationBatch.id == exact_batch_id)
        else:
            base_filters.append(AaRegistrationBatch.status == "OPEN")
        ordered = select(AaRegistrationBatch).where(*base_filters).order_by(AaRegistrationBatch.id.desc())
        if page is None:
            visible_batches = db.scalars(ordered).all()
            total = len(visible_batches)
            summary_batches = visible_batches
        else:
            total = int(db.scalar(
                select(func.count()).select_from(AaRegistrationBatch).where(*base_filters)
            ) or 0)
            visible_batches = db.scalars(ordered.offset((page - 1) * page_size).limit(page_size)).all()
            # 首页的待办理数不能由第 1 页本地猜测：只读取本人的映射行，计数仍由服务端完成。
            summary_filters = [
                AaRegistrationBatch.tenant_id == tenant_id,
                AaRegistrationBatch.is_deleted.is_(False),
            ]
            if exact_batch_id is not None:
                summary_filters.append(AaRegistrationBatch.id == exact_batch_id)
            else:
                summary_filters.append(AaRegistrationBatch.status == "OPEN")
            summary_batches = db.scalars(
                select(AaRegistrationBatch).where(*summary_filters).order_by(AaRegistrationBatch.id.desc())
            ).all()

        mapping_batch_ids = {int(batch.id) for batch in summary_batches}
        mapping_batch_ids.update(int(batch.id) for batch in visible_batches)
        registrations = {}
        deferrals = {}
        open_exceptions = {}
        if mapping_batch_ids:
            for reg in db.scalars(select(AaRegistration).where(
                AaRegistration.tenant_id == tenant_id,
                AaRegistration.student_id == stu.id,
                AaRegistration.batch_id.in_(mapping_batch_ids),
                AaRegistration.is_deleted.is_(False),
            )).all():
                registrations[int(reg.batch_id)] = reg
            for defer in db.scalars(select(AaRegistrationDeferral).where(
                AaRegistrationDeferral.tenant_id == tenant_id,
                AaRegistrationDeferral.student_id == stu.id,
                AaRegistrationDeferral.batch_id.in_(mapping_batch_ids),
                AaRegistrationDeferral.is_deleted.is_(False),
            ).order_by(AaRegistrationDeferral.batch_id.asc(), AaRegistrationDeferral.id.desc())).all():
                deferrals.setdefault(int(defer.batch_id), defer)
            for exception in db.scalars(select(AaRegistrationException).where(
                AaRegistrationException.tenant_id == tenant_id,
                AaRegistrationException.student_id == stu.id,
                AaRegistrationException.batch_id.in_(mapping_batch_ids),
                AaRegistrationException.status == "OPEN",
                AaRegistrationException.is_deleted.is_(False),
            )).all():
                open_exceptions[int(exception.batch_id)] = exception

        def _item(batch):
            reg = registrations.get(int(batch.id))
            defer = deferrals.get(int(batch.id))
            open_exception = open_exceptions.get(int(batch.id))
            eligibility = (reg.eligibility_status if reg else "PENDING") or "PENDING"
            registration_status = (reg.status if reg else "PENDING_REGISTER")
            already = registration_status == "REGISTERED"
            blocked = eligibility == "INELIGIBLE" or bool(open_exception)
            window_status, window_reason = registration_self_service_window_state(batch, now=now)
            batch_open = batch.status == "OPEN"
            can_register = batch_open and (not already) and (not blocked) and window_status == "OPEN"
            # 注册异常可能正是学生申请暂缓的原因，故保留既有“可暂缓”业务口径；窗口仍由后端强制。
            can_defer = batch_open and (not already) and (not defer or defer.status == "REJECTED") and window_status == "OPEN"
            block_reason = (
                "注册资格核验未通过" if eligibility == "INELIGIBLE"
                else ("存在未解除的注册异常，请联系辅导员" if open_exception else window_reason)
            )
            # 精确深链可回读已关闭批次；不能只把按钮置灰而不解释原因。
            if not block_reason and not already and not batch_open:
                block_reason = "注册批次已关闭，暂不能自助办理"
            return {
                "batchId": str(batch.id), "batchName": batch.batch_name,
                "batchStatus": batch.status,
                "registerType": batch.register_type,
                "registerTypeLabel": _REG_TYPE_LABEL.get(batch.register_type, "注册类型待学校核对"),
                "windowStart": _iso(batch.window_start), "windowEnd": _iso(batch.window_end),
                "windowStatus": window_status,
                "registrationStatus": registration_status,
                "registrationId": str(reg.id) if reg else None,
                "registeredAt": _iso(reg.register_at) if reg else None,
                "eligibilityStatus": eligibility,
                "eligibilityNote": (reg.eligibility_note if reg else "") or "",
                "hasOpenException": bool(open_exception),
                "exceptionType": (open_exception.exception_type if open_exception else None),
                "deferral": ({
                    "deferralId": str(defer.id), "status": defer.status, "reason": defer.reason,
                    "requestedUntil": _iso(defer.requested_until), "reviewNote": defer.review_note or "",
                } if defer else None),
                "canRegister": can_register,
                "canDefer": can_defer,
                "blockReason": block_reason,
            }

        visible_items = [_item(batch) for batch in visible_batches]
        summary_items = [_item(batch) for batch in summary_batches]
        actionable_items = [item for item in summary_items if item["canRegister"] or item["canDefer"]]
        result = {
            "studentStatus": stu.student_status,
            "studentNo": stu.student_no,
            "realName": stu.real_name,
            "batches": visible_items,
            "note": "" if visible_items else ("未找到该注册批次" if exact_batch_id else "当前无开放的注册批次"),
        }
        if page is not None:
            deadline_values = [item["windowEnd"] for item in actionable_items if item["windowEnd"]]
            result.update({
                "page": page,
                "pageSize": page_size,
                "total": total,
                "hasMore": page * page_size < total,
                "actionableTotal": len(actionable_items),
                "nextActionBatchId": actionable_items[0]["batchId"] if actionable_items else None,
                "nextActionDeadline": min(deadline_values) if deadline_values else None,
            })
        return result


def registration_self_register(user, batch_id) -> dict:
    """本人在开放且未过期的批次完成注册（最终校验与正式注册同一事务）。"""
    # 包级 ``academic_affairs_service`` 是教职工范围 facade；学生本人已经由
    # ``_me`` 从受控会话解析，必须显式进入同一正式注册命令的 self_service 分支。
    # 否则 facade 的旧三参签名既不会校验窗口，也会在运行时抛 TypeError。
    svc = importlib.import_module(".academic_affairs_service", package=__package__)
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return svc.register_student(batch_id, user, sid, self_service=True)


def registration_defer_apply_my(user, batch_id, reason, requested_until=None) -> dict:
    """本人申请暂缓注册（不走教职工数据范围校验，仅本人）。"""
    from app.models import AaRegistrationDeferral
    from app.modules.academic_affairs.services.academic_affairs_service import (
        _audit,
        _deferral_row,
        _parse_dt,
        require_registration_self_service_window,
        require_writable_registration_batch,
    )
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "暂缓原因必填")
    with session() as db:
        # Both student-self and staff writers lock this same formal batch before
        # checking for an in-flight record.  A first submission has no deferral
        # row to lock, so this is the shared concurrency boundary.
        b = require_writable_registration_batch(db, batch_id)
        stu = _me(db, user)
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "注册批次未开放或已关闭")
        require_registration_self_service_window(b)
        if stu.student_status not in ("PENDING_REGISTER", "UNREGISTERED", "REGISTERED"):
            # ANNUAL 场景下在籍生也可申请暂缓本批次义务
            raise AppException("DATA_CONFLICT", "当前学籍状态不可申请暂缓注册", http_status=409)
        dup = db.scalars(select(AaRegistrationDeferral).where(
            AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.batch_id == b.id,
            AaRegistrationDeferral.student_id == stu.id, AaRegistrationDeferral.status == "PENDING",
            AaRegistrationDeferral.is_deleted.is_(False)).with_for_update().execution_options(
                populate_existing=True)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "本批次已有待审的暂缓申请", http_status=409)
        d = AaRegistrationDeferral(
            tenant_id=_tid(), batch_id=b.id, student_id=stu.id, reason=reason,
            requested_until=_parse_dt(requested_until), status="PENDING")
        db.add(d)
        db.flush()
        _audit(db, "AA_REG_DEFERRAL", d.id, "SELF_APPLY", reason)
        db.commit()
        db.refresh(d)
        return _deferral_row(d)


# ═══════════ 重修/免修可选课程 ═══════════

def _best_grades_for_me(db, stu):
    """消费P0-11统一有效成绩策略；禁止按课程名或最高分二次计算。"""
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        resolve_effective_grade,
    )

    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
        AcademicStudent.is_deleted.is_(False))).first()
    if not acad:
        return [], None
    rows = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))).all()
    return resolve_effective_grade(rows), acad


def makeup_options_my(user) -> dict:
    """重修候选=统一有效成绩中的挂科；免修候选=尚未及格课程。"""
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        grade_identity_key,
    )

    with session() as db:
        stu = _me(db, user)
        best, _ = _best_grades_for_me(db, stu)
        fails, pending = [], []
        for g in best:
            identity = grade_identity_key(g)
            item = {
                "gradeId": str(g.id),
                "courseId": str(g.course_id or ""),
                "courseCode": g.course_code or "",
                "courseVersion": g.course_version,
                "attemptNo": g.attempt_no,
                "identityType": identity[1],
                "identityDebt": identity[1] == "LEGACY_NAME_KEY",
                "courseName": g.course_name,
                "termCode": g.term or "",
                "score": g.score,
                "credit": float(g.credit_value or 0),
                "passStatus": g.pass_status,
            }
            ps = (g.pass_status or "").upper()
            if ps in ("FAIL", "FAILED"):
                fails.append(item)
            elif ps != "PASSED":
                pending.append(item)
        fails.sort(key=lambda x: (x["termCode"] or "", x["courseCode"] or "", x["courseName"]))
        pending.sort(key=lambda x: (x["termCode"] or "", x["courseCode"] or "", x["courseName"]))
        return {
            "retakeOptions": fails,
            "exemptionOptions": pending or fails,
            "retakeTotal": len(fails),
            "exemptionTotal": len(pending or fails),
            "identityDebtCount": sum(1 for item in (fails + pending) if item["identityDebt"]),
            "policyCode": "LATEST_FORMAL_SOURCE_V1",
            "note": "请从列表选择具体成绩记录提交；历史身份欠账课程会明确标记，不会与同名课程合并。"
            if (fails or pending) else "暂无挂科/未及格课程可选",
        }


# ═══════════ 学生考勤自查 ═══════════

def _attendance_schedule_context(attendance_session) -> dict:
    """Expose only a verified, immutable formal-occurrence backlink to the student."""
    if str(getattr(attendance_session, "source_type", "") or "").upper() != "FORMAL_TEACHING":
        return {}
    try:
        evidence = json.loads(getattr(attendance_session, "source_evidence", "") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(evidence, dict):
        return {}
    schedule_item_id = str(evidence.get("scheduleItemId") or "").strip()
    session_date = str(getattr(attendance_session, "session_date", "") or "").strip()
    evidence_date = str(evidence.get("sessionDate") or "").strip()
    try:
        week_no = int(evidence.get("weekNo"))
        slot_no = int(evidence.get("slotNo"))
    except (TypeError, ValueError):
        return {}
    if not schedule_item_id.isdigit() or int(schedule_item_id) <= 0:
        return {}
    if not session_date or evidence_date != session_date or week_no <= 0:
        return {}
    if slot_no != int(getattr(attendance_session, "slot_no", 0) or 0):
        return {}
    return {
        "scheduleItemId": schedule_item_id,
        "weekNo": week_no,
        "occurrenceDate": evidence_date,
    }


def _attendance_page_args(page, page_size):
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 20
    return page, min(max(1, page_size), 100)


def _attendance_student_rows_sql(include_course: bool, include_teaching_task: bool) -> str:
    course_condition = "AND LOWER(COALESCE(s.course_name, '')) LIKE :course_keyword" if include_course else ""
    task_condition = "AND s.teaching_task_id = :teaching_task_id" if include_teaching_task else ""
    # roster_json is a legacy text snapshot. JSON_TABLE keeps that historical write
    # contract intact while returning only the current student's JSON element; IF(JSON_VALID)
    # turns malformed legacy snapshots into an empty array instead of a 500 response.
    # A few old snapshots contain the same student more than once.  The original
    # Python implementation used the first matching item, so retain that behavior
    # explicitly instead of accidentally counting one class session twice.
    return f"""
        SELECT
            session_id, course_name, session_date, slot_no, session_type,
            source_type, source_evidence, attendance_status
        FROM (
            SELECT
                s.id AS session_id,
                s.course_name AS course_name,
                s.session_date AS session_date,
                s.slot_no AS slot_no,
                s.session_type AS session_type,
                s.source_type AS source_type,
                s.source_evidence AS source_evidence,
                UPPER(COALESCE(NULLIF(roster.attendance_status, ''), 'PRESENT')) AS attendance_status,
                ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY roster.roster_position) AS roster_position_rank
            FROM t_aa_attendance_session AS s
            JOIN JSON_TABLE(
                IF(JSON_VALID(s.roster_json), s.roster_json, JSON_ARRAY()),
                '$[*]' COLUMNS (
                    roster_position FOR ORDINALITY,
                    student_id VARCHAR(64) PATH '$.studentId',
                    attendance_status VARCHAR(32) PATH '$.status'
                )
            ) AS roster ON roster.student_id = :student_id
            WHERE s.tenant_id = :tenant_id
              AND s.is_deleted = 0
              AND s.status = 'SUBMITTED'
              {task_condition}
              {course_condition}
        ) AS matched_student_sessions
        WHERE roster_position_rank = 1
    """


def _attendance_task_id(value):
    if value in (None, ""):
        return None
    try:
        task_id = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "教学任务标识不正确")
    if task_id <= 0:
        raise AppException("VALIDATION_ERROR", "教学任务标识不正确")
    return task_id


def attendance_my(user, page=1, page_size=20, course="", teaching_task_id=None) -> dict:
    """Current student's submitted attendance, SQL-paged and server-filtered."""
    with session() as db:
        stu = _me(db, user)
        page, page_size = _attendance_page_args(page, page_size)
        course = str(course or "").strip()
        teaching_task_id = _attendance_task_id(teaching_task_id)
        # Historical ownership is the submitted roster snapshot, not today's
        # administrative class.  This keeps a transferred/graduated student's
        # own old sessions visible without ever widening them to another student.
        params = {
            "tenant_id": _tid(), "student_id": str(stu.id),
        }
        if course:
            params["course_keyword"] = f"%{course.lower()}%"
        if teaching_task_id is not None:
            params["teaching_task_id"] = teaching_task_id
        rows_sql = _attendance_student_rows_sql(bool(course), teaching_task_id is not None)
        summary_row = db.execute(text(f"""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN attendance_status = 'PRESENT' THEN 1 ELSE 0 END), 0) AS present_count,
                COALESCE(SUM(CASE WHEN attendance_status = 'LATE' THEN 1 ELSE 0 END), 0) AS late_count,
                COALESCE(SUM(CASE WHEN attendance_status = 'ABSENT' THEN 1 ELSE 0 END), 0) AS absent_count,
                COALESCE(SUM(CASE WHEN attendance_status = 'LEAVE' THEN 1 ELSE 0 END), 0) AS leave_count,
                COALESCE(SUM(CASE WHEN attendance_status NOT IN ('PRESENT', 'LATE', 'ABSENT', 'LEAVE') THEN 1 ELSE 0 END), 0) AS other_count
            FROM ({rows_sql}) AS student_sessions
        """), params).mappings().one()
        total = int(summary_row["total"] or 0)
        page_params = {**params, "limit": page_size, "offset": (page - 1) * page_size}
        rows = db.execute(text(f"""
            {rows_sql}
            ORDER BY session_date DESC, session_id DESC
            LIMIT :limit OFFSET :offset
        """), page_params).mappings().all()
        items = []
        for row in rows:
            session_view = SimpleNamespace(
                source_type=row["source_type"], source_evidence=row["source_evidence"],
                session_date=row["session_date"], slot_no=row["slot_no"],
            )
            items.append({
                "sessionId": str(row["session_id"]), "courseName": row["course_name"] or "",
                "sessionDate": row["session_date"], "slotNo": row["slot_no"],
                "sessionType": row["session_type"] or "常规", "status": row["attendance_status"],
                **_attendance_schedule_context(session_view),
            })
        summary = {
            "PRESENT": int(summary_row["present_count"] or 0),
            "LATE": int(summary_row["late_count"] or 0),
            "ABSENT": int(summary_row["absent_count"] or 0),
            "LEAVE": int(summary_row["leave_count"] or 0),
            "OTHER": int(summary_row["other_count"] or 0),
        }
        note = "仅展示已提交场次；教师在小程序点名，PC 端只做统计查询，不提供补点名入口。"
        if not total:
            note = "暂无已提交的课堂考勤记录"
        return {
            "items": items, "summary": summary, "total": total,
            "page": page, "pageSize": page_size, "hasMore": page * page_size < total,
            "policy": "ROLLCALL_ON_MINIAPP_ONLY",
            "note": note,
        }


# ═══════════ 学生校历只读 ═══════════

def calendar_my(user) -> dict:
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_service as svc
    with session() as db:
        _me(db, user)
        term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False))).first()
        if not term:
            return {"hasTerm": False, "events": [], "weeks": [], "note": "尚未设置当前学期"}
        tid = term.id
        year_code = term.year_code
        term_no = term.term_no
    events = svc.list_calendar(tid, user)
    try:
        weeks_payload = svc.week_calendar(tid, user)
    except AppException as e:
        weeks_payload = {"weeks": [], "note": str(getattr(e, "message", None) or e)}
    weeks = weeks_payload.get("weeks") if isinstance(weeks_payload, dict) else []
    return {
        "hasTerm": True,
        "termId": str(tid),
        "termLabel": f"{year_code or ''}-{term_no or ''}",
        "events": events,
        "weeks": weeks or [],
        "weekMeta": {k: weeks_payload.get(k) for k in ("teachingWeeks", "examWeekStart", "startDate")
                     if isinstance(weeks_payload, dict) and k in weeks_payload},
        "note": weeks_payload.get("note") if isinstance(weeks_payload, dict) else "",
    }


# ═══════════ 清考结果学生可见 ═══════════

def clearance_my(user, page=None, page_size=20) -> dict:
    """本人被圈定的毕业清考记录（只读）。

    Student Mini always supplies a bounded page.  ``page is None`` remains for
    the existing student-PC print/read contract, which is not a handset list.
    """
    from app.models import AaMakeupBatch, AcademicGrade, AcademicMakeup, AcademicStudent
    if page is not None:
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "清考记录页码非法") from exc
        if page < 1 or page > 100000 or page_size < 1 or page_size > 50:
            raise AppException("VALIDATION_ERROR", "清考记录分页参数超出范围")
    with session() as db:
        stu = _me(db, user)
        acad = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
            AcademicStudent.is_deleted.is_(False))).first()
        if not acad:
            result = {"items": [], "total": 0, "note": "暂无学业台账，无清考记录"}
            if page is not None:
                result.update({"page": page, "pageSize": page_size, "hasMore": False})
            return result
        filters = (
            AcademicMakeup.tenant_id == _tid(),
            AcademicMakeup.acad_student_id == acad.id,
            AcademicMakeup.kind == "CLEARANCE",
            AcademicMakeup.is_deleted.is_(False),
        )
        query = select(AcademicMakeup).where(*filters).order_by(AcademicMakeup.id.desc())
        total = None
        if page is None:
            rows = db.scalars(query).all()
        else:
            total = int(db.scalar(select(func.count()).select_from(AcademicMakeup).where(*filters)) or 0)
            rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
        batch_ids = {r.batch_id for r in rows if r.batch_id}
        batches = {}
        if batch_ids:
            batches = {b.id: b for b in db.scalars(select(AaMakeupBatch).where(
                AaMakeupBatch.tenant_id == _tid(),
                AaMakeupBatch.id.in_(list(batch_ids)),
                AaMakeupBatch.is_deleted.is_(False))).all()}
        published_ids = {
            r.id for r in rows
            if r.status == "FINISHED" and r.record_status == "ACTIVE"
            and (b := batches.get(r.batch_id)) is not None
            and b.kind == "CLEARANCE" and b.status == "FINISHED"
        }
        grades, ambiguous_sources = {}, set()
        if published_ids:
            for grade in db.scalars(select(AcademicGrade).where(
                AcademicGrade.tenant_id == _tid(),
                AcademicGrade.acad_student_id == acad.id,
                AcademicGrade.source_biz_type == "CLEARANCE",
                AcademicGrade.source_biz_id.in_(list(published_ids)),
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            )).all():
                if grade.source_biz_id in grades:
                    ambiguous_sources.add(grade.source_biz_id)
                grades[grade.source_biz_id] = grade
        items = []
        for r in rows:
            b = batches.get(r.batch_id)
            grade = grades.get(r.id)
            # PUBLISHED only releases the arrangement. Raw final_score is not the
            # published CAP60 result; missing or ambiguous formal facts stay hidden.
            score = (grade.score if grade is not None and r.id not in ambiguous_sources
                     and r.course_id is not None and grade.course_id == r.course_id else None)
            items.append({
                "recordId": str(r.id), "batchId": str(r.batch_id or ""),
                "batchName": b.batch_name if b else "",
                "originGradeId": str(r.origin_grade_id or ""),
                "courseId": str(r.course_id or ""),
                "courseCode": r.course_code or "",
                "courseVersion": r.course_version,
                "attemptNo": r.attempt_no,
                "courseName": r.course_name, "termCode": r.term or "",
                "originScore": r.origin_score, "score": score,
                "status": r.status, "kind": "CLEARANCE",
            })
        result = {
            "items": items, "total": len(items) if total is None else total,
            "note": "清考由教务处按应届未通过课程圈定；此处仅查看结果，不可自助报名。"
            if items else "暂无清考安排",
        }
        if page is not None:
            result.update({"page": page, "pageSize": page_size, "hasMore": page * page_size < total})
        return result


# ═══════════ 准考证 / 异动申请表打印留痕 ═══════════

def exam_ticket_print_my(user, body=None) -> dict:
    from app.student_portal.services import common_service as common
    from app.modules.academic_affairs.services.mobile_academic_affairs_service import exam_my
    body = body or {}
    doc = exam_my(user)
    with session() as db:
        stu = _me(db, user)
        sno, name = stu.student_no, stu.real_name
    log = common.print_log(user, {
        "bizType": "EXAM_TICKET",
        "bizId": str(body.get("bizId") or sno or "self"),
        "docName": "准考证",
        "reason": str(body.get("reason") or "个人准考证"),
    })
    return {
        **log, "docName": "准考证", "printReason": body.get("reason") or "个人准考证",
        "document": {**doc, "studentNo": sno, "realName": name},
    }


def status_change_print_my(user, body=None) -> dict:
    from app.student_portal.services import common_service as common
    from app.modules.academic_affairs.services.mobile_academic_affairs_service import status_my
    body = body or {}
    st = status_my(user)
    with session() as db:
        stu = _me(db, user)
        sno, name = stu.student_no, stu.real_name
    log = common.print_log(user, {
        "bizType": "STATUS_CHANGE",
        "bizId": str(body.get("bizId") or body.get("changeType") or "self"),
        "docName": "学籍异动申请审批表",
        "reason": str(body.get("reason") or body.get("changeType") or "学籍异动"),
    })
    return {
        **log,
        "docName": "学籍异动申请审批表",
        "printReason": body.get("reason") or "",
        "document": {
            "studentNo": sno, "realName": name,
            "studentStatus": st.get("studentStatus"),
            "enrolled": st.get("enrolled"),
            "changeType": body.get("changeType"),
            "reason": body.get("reason"),
            "history": (st.get("changes") or [])[:5],
        },
    }

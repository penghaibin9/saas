"""选课域最终公开入口。

仅修正 canonical Service 静态复审确认的接口与事务问题：
- 发布批次和学生选课显式按 ORM 模型加行锁，禁止 ``type(query_result)`` 反查；
- CLOSED 补选资格只认本人真实 ``COURSE_CANCELLED`` 记录，不信任前端标志；
- 学生退课继续遵守既有 ``EnrollBody.selectionCourseId`` 请求契约；
- 学生可选课程保持 Router 既有 ``{"items": list}`` 返回契约；
- Stage C2：正式选课资格只消费选课动作生效时点的 ``StudentAcademicFact``，
  ``StudentProfile`` 仅继续提供姓名/学号等非学籍身份快照；
- Stage D：不重跑任何规则，仅把 canonical Service 已经做出的拒绝决定附加为
  deterministic ``DecisionTrace``，保留原 code/message/http 契约；
- B-W5：学生列表 projection 与 preflight 共用单一纯读 evaluator，客户端只消费
  ``allowedActions``，提交 Command 仍持锁重新校验，列表结果永不充当写授权。

其余业务函数显式委托 ``academic_affairs_selection_service``，不修改模块对象，
不依赖导入顺序安装 monkey patch。
"""
from __future__ import annotations

import importlib
from contextlib import contextmanager
from datetime import datetime
from threading import BoundedSemaphore, Lock
from time import monotonic
from types import SimpleNamespace

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_decision_trace as selection_trace
from . import academic_affairs_selection_preflight_service as batch_preflight_svc

_base = importlib.import_module(
    ".academic_affairs_selection_service",
    package=__package__,
)

# W6 peak admission is process-local backpressure, never the business authority.
# Each process owns its SQLAlchemy pool, so this gate preserves DB headroom for
# nested EffectiveGrade/read sessions. Cross-process correctness stays in MySQL.
from app.core.config import get_settings as _get_settings

_db_settings = _get_settings()
_selection_pool_total = max(
    1,
    int(_db_settings.DB_POOL_SIZE or 1) + int(_db_settings.DB_MAX_OVERFLOW or 0),
)
_selection_process_limit = max(
    1,
    min(
        int(_db_settings.DB_POOL_SIZE or 1),
        max(1, _selection_pool_total // 2),
    ),
)
_SELECTION_ENROLL_PROCESS_GATE = BoundedSemaphore(_selection_process_limit)
_SELECTION_ENROLL_STRIPES = tuple(Lock() for _ in range(64))
_SELECTION_ADMISSION_TIMEOUT_SECONDS = max(
    10.0,
    min(30.0, float(_db_settings.DB_POOL_TIMEOUT or 5) * 6.0),
)


@contextmanager
def _selection_course_admission(selection_course_id: int):
    """Bound hot-key fan-in before DB checkout; MySQL remains final authority."""
    course_id = int(selection_course_id)
    stripe = _SELECTION_ENROLL_STRIPES[course_id % len(_SELECTION_ENROLL_STRIPES)]
    deadline = monotonic() + _SELECTION_ADMISSION_TIMEOUT_SECONDS
    if not stripe.acquire(timeout=_SELECTION_ADMISSION_TIMEOUT_SECONDS):
        raise AppException(
            "RATE_LIMITED",
            "当前课程选课请求繁忙，请稍后重试",
            details={"businessCode": "SELECTION_BUSY", "selectionCourseId": str(course_id)},
            http_status=429,
        )
    process_acquired = False
    try:
        remaining = max(0.0, deadline - monotonic())
        process_acquired = _SELECTION_ENROLL_PROCESS_GATE.acquire(timeout=remaining)
        if not process_acquired:
            raise AppException(
                "RATE_LIMITED",
                "当前选课请求繁忙，请稍后重试",
                details={"businessCode": "SELECTION_BUSY", "selectionCourseId": str(course_id)},
                http_status=429,
            )
        yield
    finally:
        if process_acquired:
            _SELECTION_ENROLL_PROCESS_GATE.release()
        stripe.release()


def __getattr__(name):
    return getattr(_base, name)


def _selection_academic_identity(db, student, *, effective_at: datetime):
    """解析本次选课决定使用的权威学籍事实；缺失/重叠一律 fail-closed。"""
    from .academic_affairs_student_fact_service import resolve_student_academic_fact

    fact = resolve_student_academic_fact(
        db,
        int(student.id),
        as_of=effective_at,
        required=True,
    )
    identity = SimpleNamespace(
        id=int(student.id),
        student_status=fact.student_status,
        college_id=fact.college_id,
        major_id=fact.major_id,
        class_id=fact.class_id,
        grade=fact.grade,
    )
    return identity, fact


def _normalized_record_status(record) -> str:
    if not record:
        return ""
    raw = str(getattr(record, "status", "") or "").upper()
    return {
        str(_base._REC_PENDING).upper(): "PENDING_LOTTERY",
        str(_base._REC_LOST).upper(): "LOTTERY_LOST",
    }.get(raw, raw)


def _status_label(status: str) -> str:
    return {
        "OPEN": "可选",
        "BLOCKED": "不可选",
        "SELECTED": "已选",
        "PENDING_LOTTERY": "待抽签",
        "LOTTERY_LOST": "未中签",
        "COURSE_CANCELLED": "课程已取消",
        "DROPPED": "已退课",
        "LOCKED": "名单已锁定",
    }.get(str(status or "").upper(), str(status or "待确认"))


def _first_resolution(trace) -> str:
    if not isinstance(trace, dict):
        return ""
    rows = trace.get("availableResolutions") or trace.get("available_resolutions") or []
    if not rows:
        return ""
    first = rows[0] or {}
    return str(first.get("label") or first.get("message") or "")


def _configured_round_batch_ids(db, batch_ids) -> set[int]:
    """Return tenant-scoped batches that have any persisted Selection round."""
    from app.models import AaSelectionRound

    normalized = sorted({int(value) for value in (batch_ids or [])})
    if not normalized:
        return set()
    rows = db.query(AaSelectionRound.batch_id).filter(
        AaSelectionRound.tenant_id == _base._core._tid(),
        AaSelectionRound.batch_id.in_(normalized),
        AaSelectionRound.is_deleted.is_(False),
    ).distinct().all()
    return {int(row[0]) for row in rows}


def _evaluate_student_course(
    db,
    *,
    student,
    academic_identity,
    academic_fact,
    batch,
    course,
    my_records,
    active_round,
    evaluated_at,
    round_configured=False,
) -> dict:
    """单一纯读学生课程决策器；preflight/list 共用，绝不 commit/写审计。"""
    record = next(
        (
            row for row in my_records
            if int(getattr(row, "selection_course_id", 0) or 0) == int(course.id)
        ),
        None,
    )
    record_status = _normalized_record_status(record)
    allow_reselect_closed = (
        str(batch.status or "").upper() == _base._BATCH_CLOSED
        and any(row.status == _base._REC_COURSE_CANCELLED for row in my_records)
    )
    lottery_mode = bool(active_round and str(active_round.mode or "").upper() == "LOTTERY")
    phase = (
        "LOTTERY" if str(batch.status or "").upper() == _base._BATCH_OPEN and lottery_mode
        else "SELECTION" if str(batch.status or "").upper() == _base._BATCH_OPEN
        else "RESELECT" if allow_reselect_closed
        else str(batch.status or "").upper() or "UNKNOWN"
    )

    allowed_actions = ["VIEW"]
    reason = ""
    how_to_resolve = ""
    decision_trace = None
    code = ""
    enroll_allowed = False

    try:
        _base._guard_batch_writable(db, batch)
        if course.status != _base._COURSE_OPEN:
            raise _base._core._invalid("课程已取消或不可选")

        if record_status in {"SELECTED", "PENDING_LOTTERY", "LOCKED"}:
            reason = {
                "SELECTED": "当前课程已有有效选课记录",
                "PENDING_LOTTERY": "当前课程已登记抽签志愿，等待结果",
                "LOCKED": "当前课程名单已锁定",
            }[record_status]
        else:
            if (
                str(batch.status or "").upper() == _base._BATCH_OPEN
                and round_configured
                and active_round is None
            ):
                raise _base._core._invalid("当前没有开放选课轮次")
            if active_round and not active_round.allow_enroll:
                raise _base._core._invalid("当前轮次不允许选课")
            _base._validate_enroll(
                db,
                batch,
                course,
                academic_identity,
                my_records,
                float(course.credit or 0),
                allow_reselect_closed=allow_reselect_closed,
            )
            enroll_allowed = True
            allowed_actions.append("ENROLL")

        if (
            record
            and record.status in {_base._REC_SELECTED, _base._REC_PENDING}
            and str(batch.status or "").upper() == _base._BATCH_OPEN
            and (not active_round or bool(active_round.allow_drop))
        ):
            allowed_actions.append("DROP")
    except AppException as exc:
        traced = selection_trace.attach_selection_trace(
            exc,
            db=db,
            student=student,
            course=course,
            evaluated_at=evaluated_at,
        )
        code = str(getattr(exc, "code", "") or "DATA_CONFLICT")
        reason = str(getattr(exc, "message", "") or str(exc))
        decision_trace = getattr(traced, "decision_trace", None)
        how_to_resolve = _first_resolution(decision_trace)

    status = record_status or ("OPEN" if enroll_allowed else "BLOCKED")
    if record_status == "LOTTERY_LOST" and enroll_allowed:
        status = "LOTTERY_LOST"
    if record_status == "COURSE_CANCELLED" and enroll_allowed:
        status = "COURSE_CANCELLED"

    if not how_to_resolve:
        if "ENROLL" in allowed_actions:
            how_to_resolve = "可直接提交选课；提交时服务器会再次持锁校验"
        elif "DROP" in allowed_actions:
            how_to_resolve = "可在当前退课窗口办理退课"
        elif record_status == "PENDING_LOTTERY":
            how_to_resolve = "等待本轮抽签结果"
        elif record_status == "LOCKED":
            how_to_resolve = "名单已锁定，如需调整请联系教务老师"
        elif not reason:
            how_to_resolve = "查看当前选课批次状态或联系教务老师"

    if not reason:
        if record_status == "SELECTED":
            reason = "当前课程已选"
        elif record_status == "PENDING_LOTTERY":
            reason = "抽签志愿已登记"
        elif record_status == "LOCKED":
            reason = "正式名单已锁定"
        elif enroll_allowed:
            reason = "当前课程通过服务器资格预检"

    return {
        "allowed": "ENROLL" in allowed_actions,
        "selectionCourseId": str(course.id),
        "courseName": course.course_name,
        "code": code,
        "message": reason,
        "decisionTrace": decision_trace,
        "mode": "LOTTERY" if lottery_mode else "FCFS",
        "academicFactId": str(academic_fact.id),
        "academicFactVersion": academic_fact.version_no,
        "evaluatedAt": evaluated_at.isoformat(),
        "status": status,
        "statusLabel": _status_label(status),
        "phase": phase,
        "eligibility": "ELIGIBLE" if "ENROLL" in allowed_actions else "INELIGIBLE",
        "allowedActions": allowed_actions,
        "reason": reason,
        "howToResolve": how_to_resolve,
        "window": {
            "startAt": getattr(batch, "select_start_at", None).isoformat() if getattr(batch, "select_start_at", None) else None,
            "endAt": getattr(batch, "select_end_at", None).isoformat() if getattr(batch, "select_end_at", None) else None,
            "batchStatus": str(batch.status or ""),
        },
        "lottery": {
            "mode": "LOTTERY" if lottery_mode else "FCFS",
            "roundNo": getattr(active_round, "round_no", None) if active_round else None,
            "allowEnroll": (
                bool(getattr(active_round, "allow_enroll", True))
                if active_round
                else not (
                    str(batch.status or "").upper() == _base._BATCH_OPEN
                    and round_configured
                )
            ),
            "allowDrop": bool(getattr(active_round, "allow_drop", True)) if active_round else True,
        },
        "reselect": allow_reselect_closed,
    }


def student_courses(user, batch_id=None):
    """B-C3：同一 session 聚合服务器动作 projection；不逐课调用 public preflight。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        evaluated_at = datetime.utcnow()
        academic_identity, academic_fact = _selection_academic_identity(
            db, student, effective_at=evaluated_at
        )

        q = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        )
        if batch_id:
            q = q.filter(AaSelectionBatch.id == int(batch_id))
        else:
            q = q.filter(AaSelectionBatch.status.in_([
                _base._BATCH_OPEN,
                _base._BATCH_CLOSED,
            ]))
        batches = q.order_by(AaSelectionBatch.id.desc()).all()
        if not batches:
            return []

        batch_ids = [int(batch.id) for batch in batches]
        configured_round_batch_ids = _configured_round_batch_ids(db, batch_ids)
        course_rows = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.batch_id.in_(batch_ids),
            AaSelectionCourse.is_deleted.is_(False),
        ).order_by(AaSelectionCourse.batch_id, AaSelectionCourse.id).all()
        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id.in_(batch_ids),
            AaSelectionRecord.is_deleted.is_(False),
        ).all()

        courses_by_batch = {}
        records_by_batch = {}
        for course in course_rows:
            courses_by_batch.setdefault(int(course.batch_id), []).append(course)
        for record in my_records:
            records_by_batch.setdefault(int(record.batch_id), []).append(record)

        out = []
        for batch in batches:
            bid = int(batch.id)
            batch_records = records_by_batch.get(bid, [])
            has_reselect = any(
                row.status == _base._REC_COURSE_CANCELLED for row in batch_records
            )
            if not batch_id and batch.status == _base._BATCH_CLOSED and not has_reselect:
                continue
            active_round = _base._active_round(db, bid)
            projected_courses = []
            for course in courses_by_batch.get(bid, []):
                projection = _evaluate_student_course(
                    db,
                    student=student,
                    academic_identity=academic_identity,
                    academic_fact=academic_fact,
                    batch=batch,
                    course=course,
                    my_records=batch_records,
                    active_round=active_round,
                    evaluated_at=evaluated_at,
                    round_configured=bid in configured_round_batch_ids,
                )
                allowed_actions = list(projection.get("allowedActions") or [])
                if "VIEW" not in allowed_actions:
                    allowed_actions.insert(0, "VIEW")
                projected_courses.append({
                    **_base._core._course_dto(course),
                    "status": projection["status"],
                    "statusLabel": projection["statusLabel"],
                    "phase": projection["phase"],
                    "eligibility": projection["eligibility"],
                    "allowedActions": allowed_actions,
                    "reason": projection["reason"],
                    "howToResolve": projection["howToResolve"],
                    "window": projection["window"],
                    "lottery": projection["lottery"],
                    "reselect": projection["reselect"],
                    "decisionTrace": projection.get("decisionTrace"),
                    "evaluatedAt": projection["evaluatedAt"],
                })

            out.append({
                "batch": _base._core._batch_dto(batch),
                "round": {
                    "roundNo": getattr(active_round, "round_no", None),
                    "mode": getattr(active_round, "mode", None),
                    "allowEnroll": bool(getattr(active_round, "allow_enroll", True)),
                    "allowDrop": bool(getattr(active_round, "allow_drop", True)),
                } if active_round else None,
                "courses": projected_courses,
            })
        return out


def batch_preflight(user, batch_id, action: str) -> dict:
    """Admin-visible pure lifecycle preflight; archived-term/config failures become blockers, not writes."""
    from app.models import AaSelectionBatch

    with _base._core.session() as db:
        _base._core._ctx(user, db)
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("选课批次不存在")
        result = batch_preflight_svc.evaluate_batch(db, batch, action)
        try:
            _base._guard_batch_writable(db, batch)
        except AppException as exc:
            result["blockers"].insert(0, {
                "code": str(getattr(exc, "code", "") or "SELECTION_TERM_NOT_WRITABLE"),
                "message": str(getattr(exc, "message", "") or str(exc)),
                "ownerRole": "ACADEMIC_ADMIN",
                "howToResolve": "处理学期归档/只读状态后重新预检",
            })
            result["allowed"] = False
            result["allowedActions"] = ["VIEW"]
        return batch_preflight_svc.public_result(result)


def open_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch
    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        batch_preflight_svc.require_batch_action(db, batch, "OPEN")
        batch.status = _base._BATCH_OPEN
        _base._core._audit(db, batch.id, "SELECTION_BATCH_OPEN", "开选；preflight=PASS")
        db.commit()
        return _base._core._batch_dto(batch)


def close_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch
    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        batch_preflight_svc.require_batch_action(db, batch, "CLOSE")
        batch.status = _base._BATCH_CLOSED
        _base._core._audit(db, batch.id, "SELECTION_BATCH_CLOSE", "截止选课；preflight=PASS")
        db.commit()
        return _base._core._batch_dto(batch)


def publish_batch(user, batch_id) -> dict:
    from app.models import AaSelectionBatch, AaSelectionCourse

    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        batch_preflight_svc.require_batch_action(db, batch, "PUBLISH")
        if batch.status != _base._BATCH_DRAFT:
            raise _base._core._invalid(f"仅 DRAFT 批次可发布，当前 {batch.status}")

        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.status == _base._COURSE_OPEN,
            AaSelectionCourse.is_deleted.is_(False),
        ).all()
        if not courses:
            raise AppException("VALIDATION_ERROR", "批次未配置任何有效可选课程，不可发布")
        invalid = [
            row for row in courses
            if int(row.capacity or 0) <= 0
            or int(row.min_capacity or 0) < 0
            or int(row.min_capacity or 0) > int(row.capacity or 0)
        ]
        if invalid:
            raise AppException(
                "DATA_CONFLICT",
                f"有 {len(invalid)} 门课程容量或开班下限配置无效",
                details={"selectionCourseIds": [str(row.id) for row in invalid]},
                http_status=409,
            )

        batch.status = _base._BATCH_PUBLISHED
        _base._core._audit(
            db,
            batch.id,
            "SELECTION_BATCH_PUBLISH",
            f"发布批次；课程{len(courses)}门",
        )
        db.commit()
        return _base._core._batch_dto(batch)


def student_preflight(user, body):
    """SelectionPreflight：与列表共用 evaluator；纯读且不写容量、记录或审计。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        evaluated_at = datetime.utcnow()
        academic_identity, academic_fact = _selection_academic_identity(
            db, student, effective_at=evaluated_at
        )
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(body.selectionCourseId),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("可选课程供给项不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(course.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("选课批次不存在")
        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        active_round = _base._active_round(db, batch.id)
        round_configured = bool(_configured_round_batch_ids(db, [batch.id]))
        return _evaluate_student_course(
            db,
            student=student,
            academic_identity=academic_identity,
            academic_fact=academic_fact,
            batch=batch,
            course=course,
            my_records=my_records,
            active_round=active_round,
            evaluated_at=evaluated_at,
            round_configured=round_configured,
        )


def student_enroll(user, body):
    """Peak-safe public command; admission happens before any DB checkout."""
    selection_course_id = int(body.selectionCourseId)
    with _selection_course_admission(selection_course_id):
        return _student_enroll_guarded(user, body)


def _student_enroll_guarded(user, body):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        selection_effective_at = datetime.utcnow()
        academic_identity, academic_fact = _selection_academic_identity(
            db,
            student,
            effective_at=selection_effective_at,
        )
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(body.selectionCourseId),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("可选课程供给项不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(course.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        try:
            _base._guard_batch_writable(db, batch)
        except AppException as exc:
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
            ) from exc
        if course.status != _base._COURSE_OPEN:
            exc = _base._core._invalid("课程已取消或不可选")
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
                rule_code="SELECTION_LOCKED",
            )

        my_records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        active_round = _base._active_round(db, batch.id)
        round_configured = bool(_configured_round_batch_ids(db, [batch.id]))
        if (
            batch.status == _base._BATCH_OPEN
            and round_configured
            and active_round is None
        ):
            exc = _base._core._invalid("当前没有开放选课轮次")
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
                rule_code="SELECTION_LOCKED",
            )
        if active_round and not active_round.allow_enroll:
            exc = _base._core._invalid("当前轮次不允许选课")
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
                rule_code="SELECTION_LOCKED",
            )

        has_reselect_qualification = any(
            record.status == _base._REC_COURSE_CANCELLED
            for record in my_records
        )
        allow_reselect_closed = (
            batch.status == _base._BATCH_CLOSED
            and has_reselect_qualification
        )
        try:
            _base._validate_enroll(
                db,
                batch,
                course,
                academic_identity,
                my_records,
                float(course.credit or 0),
                allow_reselect_closed=allow_reselect_closed,
            )
        except AppException as exc:
            message = str(getattr(exc, "message", "") or str(exc))
            if "上课时间冲突" in message:
                _base._core._record_conflict_reject(db, batch, course, student, message)
                db.commit()
            raise selection_trace.attach_selection_trace(
                exc,
                db=db,
                student=student,
                course=course,
                evaluated_at=selection_effective_at,
            ) from exc

        lottery = bool(
            batch.status == _base._BATCH_OPEN
            and active_round
            and active_round.mode == "LOTTERY"
        )
        next_status = _base._REC_PENDING if lottery else _base._REC_SELECTED
        if not lottery:
            updated = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.id == course.id,
                AaSelectionCourse.tenant_id == _base._core._tid(),
                AaSelectionCourse.status == _base._COURSE_OPEN,
                AaSelectionCourse.selected_count < AaSelectionCourse.capacity,
            ).update({
                AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + 1,
            }, synchronize_session=False)
            if not updated:
                exc = _base._core._conflict("课程容量已满")
                raise selection_trace.attach_selection_trace(
                    exc,
                    db=db,
                    student=student,
                    course=course,
                    evaluated_at=selection_effective_at,
                    rule_code="COURSE_FULL",
                )

        existing = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if existing:
            if existing.status not in {
                _base._REC_DROPPED,
                _base._REC_LOST,
                _base._REC_COURSE_CANCELLED,
            }:
                exc = _base._core._conflict("已存在有效选课记录")
                raise selection_trace.attach_selection_trace(
                    exc,
                    db=db,
                    student=student,
                    course=course,
                    evaluated_at=selection_effective_at,
                    rule_code="ALREADY_SELECTED",
                )
            existing.status = next_status
            existing.round_id = active_round.id if active_round else None
            existing.enrolled_at = selection_effective_at if next_status == _base._REC_SELECTED else None
            existing.dropped_at = None
            existing.drop_reason = None
            existing.adjust_reason = None
            record = existing
        else:
            record = AaSelectionRecord(
                tenant_id=_base._core._tid(),
                batch_id=batch.id,
                selection_course_id=course.id,
                student_id=student.id,
                student_no=student.student_no,
                student_name=student.real_name,
                course_id=course.course_id,
                course_name=course.course_name,
                credit=course.credit,
                round_id=active_round.id if active_round else None,
                status=next_status,
                enrolled_at=selection_effective_at if next_status == _base._REC_SELECTED else None,
            )
            db.add(record)

        db.flush()
        _base._core._audit(
            db,
            record.id,
            "SELECTION_ENROLL",
            (
                f"studentNo={student.student_no} course={course.course_name} "
                f"status={next_status};reselect={allow_reselect_closed};"
                f"academicFactId={academic_fact.id};academicFactVersion={academic_fact.version_no};"
                f"selectionEffectiveAt={selection_effective_at.isoformat()}"
            ),
        )
        db.commit()
        return _base._core._record_dto(record)


def student_drop(user, body):
    """兼容既有 EnrollBody：按 selectionCourseId 定位本人记录；锁序统一 course→batch→record。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    with _base._core.session() as db:
        student = _base._load_student(db)
        course_id = int(body.selectionCourseId)

        # Preserve the existing record-not-found rejection precedence without taking a row lock.
        record_hint = db.query(
            AaSelectionRecord.id,
            AaSelectionRecord.batch_id,
        ).filter(
            AaSelectionRecord.selection_course_id == course_id,
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).first()
        if not record_hint:
            raise not_found("选课记录不存在")

        # Canonical Selection write lock order: course -> batch -> record.
        # lock_batch owns batch -> record and never needs the course row, so a concurrent
        # CLOSED->LOCKED transition can finish before DROP revalidates the batch state.
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course_id,
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise AppException(
                "DATA_CONFLICT",
                "选课课程不存在，退课已取消，请联系教务处",
                http_status=409,
            )

        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(record_hint.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_OPEN:
            raise _base._core._invalid("当前不在退课窗口")
        active_round = _base._active_round(db, batch.id)
        if active_round and not active_round.allow_drop:
            raise _base._core._invalid("当前轮次不允许退课")

        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_hint.id),
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.batch_id == batch.id,
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status not in {_base._REC_SELECTED, _base._REC_PENDING}:
            raise _base._core._invalid("当前记录不可退课")

        previous = record.status
        record.status = _base._REC_DROPPED
        record.dropped_at = datetime.utcnow()
        if previous == _base._REC_SELECTED:
            selected_count = int(course.selected_count or 0)
            if selected_count <= 0:
                raise AppException(
                    "DATA_CONFLICT",
                    "课程人数计数异常，退课已取消，请联系教务处",
                    http_status=409,
                )
            course.selected_count = selected_count - 1

        _base._core._audit(
            db,
            record.id,
            "SELECTION_DROP",
            f"studentNo={student.student_no};from={previous}",
        )
        db.commit()
        return _base._core._record_dto(record)

def lock_batch(user, batch_id):
    """CLOSED→LOCKED 使用当前正式名单投影合同，并对批次行加锁。"""
    from app.models import AaSelectionBatch
    from .academic_affairs_teaching_roster_service import (
        apply_locked_roster_projection,
        validate_selection_lock,
    )

    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_CLOSED:
            raise _base._core._invalid("仅已关闭选课批次可锁定名单")
        preflight = batch_preflight_svc.require_batch_action(db, batch, "LOCK")
        validation = preflight.get("_rosterValidation") or validate_selection_lock(db, batch)
        if not validation.get("valid"):
            raise AppException(
                "DATA_CONFLICT",
                "选课名单校验未通过",
                details={"issues": list(validation.get("issues") or [])},
                http_status=409,
            )
        apply_locked_roster_projection(db, validation)
        batch.status = _base._BATCH_LOCKED
        batch.locked_at = datetime.utcnow()
        _base._core._audit(
            db,
            batch.id,
            "SELECTION_LOCK",
            "锁定选课名单并生成教学班名单版本",
        )
        db.commit()
        db.refresh(batch)
        return _base._core._batch_dto(batch)


def adjust_record(user, record_id, reason):
    """LOCKED 后人工退课：只改 Selection Final 事实，并在同事务重建 TeachingRoster 版本。"""
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord
    from .academic_affairs_roster_consumer_service import consumer_counts
    from . import academic_affairs_selection_roster_projection_service as roster_projection

    with _base._core.session() as db:
        _base._core._require_manage_scope(_base._core._ctx(user, db))
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")

        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_id),
            AaSelectionRecord.tenant_id == _base._core._tid(),
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status != _base._REC_LOCKED:
            raise _base._core._invalid("仅 LOCKED 记录可人工调整")

        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(record.selection_course_id),
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("选课课程不存在")
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(record.batch_id),
            AaSelectionBatch.tenant_id == _base._core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("选课批次不存在")
        _base._guard_batch_writable(db, batch)
        if batch.status != _base._BATCH_LOCKED:
            raise _base._core._invalid("仅已锁定选课批次可人工调整正式名单")
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "选课课程未绑定教学任务，无法调整正式名单", http_status=409)

        counts = consumer_counts(db, teaching_task_id=int(course.teaching_task_id))
        if int(counts.get("TOTAL") or 0) > 0:
            raise _base._core._invalid("该教学任务已冻结考勤、考务或成绩名单，不可直接调整正式名单")

        record.status = _base._REC_DROPPED
        record.dropped_at = datetime.utcnow()
        record.adjust_reason = reason
        updated = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course.id,
            AaSelectionCourse.tenant_id == _base._core._tid(),
            AaSelectionCourse.selected_count > 0,
        ).update({
            AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1,
        }, synchronize_session=False)
        if not updated:
            raise AppException(
                "DATA_CONFLICT",
                "课程人数计数异常，人工退课已取消，请联系教务处",
                http_status=409,
            )

        db.flush()
        projection = roster_projection.project_selection_course_locked(
            db,
            int(course.id),
            reason=f"LOCKED 名单人工调整：{reason}",
        )
        _base._core._audit(
            db,
            record.id,
            "SELECTION_RECORD_ADJUST",
            f"人工调整退课：{reason};rosterVersionId={projection['rosterVersionId']}",
        )
        db.commit()
        return {"recordId": str(record.id), "status": _base._REC_DROPPED}

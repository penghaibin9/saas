"""岗位实习 · 成绩申诉领域闭环。

复用 CsWorkOrder 作为承载，不复刻第二套工单表；但申诉的创建、裁决、成绩撤回、
归档保护与数据范围全部由 internship 域负责。这样校园服务队列只是可选入口，
不会再出现“工单办结了、正式成绩完全没变化”的死胡同。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    CsServiceStudent,
    CsWorkOrder,
    InternshipArchive,
    InternshipAuditTrail,
    InternshipFinalScore,
    InternshipRecord,
    StudentProfile,
)
from app.modules.internship.services.internship_version import extract_expected_version, versioned_update
from app.services.db_service import _as_id, _iso, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

APPEAL_KEY = "INTERNSHIP_SCORE_APPEAL"
META_KIND = "INTERNSHIP_SCORE_APPEAL_META"
ACTIVE_WORK_ORDER_STATUSES = ("PENDING_HANDLE", "PROCESSING")


def _operator(user: dict | None) -> str:
    return str((user or {}).get("realName") or "系统")


def _meta(work_order: CsWorkOrder) -> dict:
    for item in work_order.trail_json or []:
        if isinstance(item, dict) and item.get("kind") == META_KIND:
            return item
    raise AppException("DATA_CONFLICT", "该成绩申诉缺少冻结快照，已阻止继续处理")


def _record_and_student(db, meta: dict):
    record = db.get(InternshipRecord, _as_id(meta.get("internshipId")))
    student = db.get(StudentProfile, _as_id(meta.get("studentId")))
    if (
        not record
        or record.is_deleted
        or record.tenant_id != _tid()
        or not student
        or student.is_deleted
        or student.tenant_id != _tid()
        or record.student_id != student.id
    ):
        raise not_found("成绩申诉对应的实习记录不存在")
    return record, student


def _assert_scope(db, user: dict, record: InternshipRecord, student: StudentProfile) -> None:
    from app.modules.internship.services.internship_score_service import _scope_ctx

    scope, in_scope = _scope_ctx(user)
    if not in_scope(scope, db, record, student):
        raise no_permission("该成绩申诉不在你的数据范围内")


def _assert_final_reviewer(user: dict) -> None:
    from app.modules.internship.services.internship_score_service import _assert_reviewer

    _assert_reviewer(user, final=True)


def _score_for_meta(db, meta: dict, *, lock: bool = False) -> InternshipFinalScore:
    query = select(InternshipFinalScore).where(
        InternshipFinalScore.id == _as_id(meta.get("scoreId")),
        InternshipFinalScore.tenant_id == _tid(),
        InternshipFinalScore.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    score = db.scalars(query).first()
    if not score or str(score.internship_id) != str(meta.get("internshipId")):
        raise AppException("DATA_CONFLICT", "申诉对应的成绩记录已不存在或归属发生变化")
    return score


def _archive_locked(db, internship_id: int):
    return db.scalars(
        select(InternshipArchive)
        .where(
            InternshipArchive.tenant_id == _tid(),
            InternshipArchive.internship_id == internship_id,
            InternshipArchive.is_deleted.is_(False),
        )
        .with_for_update()
    ).first()


def _derived_status(work_order: CsWorkOrder, score: InternshipFinalScore | None, meta: dict) -> tuple[str, str]:
    if work_order.status == "CLOSED":
        return "REJECTED", "已驳回"
    if work_order.status in ACTIVE_WORK_ORDER_STATUSES:
        return "PENDING", "待处理"
    if work_order.status == "COMPLETED":
        frozen_version = int(meta.get("scoreVersion") or 0)
        if score and score.status == "PUBLISHED" and int(score.version or 0) > frozen_version:
            return "CLOSED", "已重新发布"
        return "APPROVED_RECALCULATING", "已受理，待重新核算并发布"
    return work_order.status, work_order.status


def _row(db, work_order: CsWorkOrder, *, record=None, student=None) -> dict:
    meta = _meta(work_order)
    if record is None or student is None:
        record, student = _record_and_student(db, meta)
    score = _score_for_meta(db, meta)
    effective_status, effective_label = _derived_status(work_order, score, meta)
    return {
        "id": str(work_order.id),
        "workOrderId": str(work_order.id),
        "version": int(work_order.version or 0),
        "status": effective_status,
        "statusLabel": effective_label,
        "workOrderStatus": work_order.status,
        "studentId": str(student.id),
        "studentNo": student.student_no or "",
        "studentName": student.real_name or "",
        "internshipId": str(record.id),
        "batchId": str(record.batch_id or ""),
        "reason": work_order.detail or "",
        "handler": work_order.handler or "",
        "scoreSnapshot": {
            "scoreId": str(meta.get("scoreId") or ""),
            "scoreVersion": int(meta.get("scoreVersion") or 0),
            "totalScore": meta.get("scoreTotal"),
            "publishedAt": meta.get("scorePublishedAt") or "",
        },
        "currentScore": {
            "id": str(score.id),
            "version": int(score.version or 0),
            "status": score.status,
            "totalScore": score.total_score,
            "publishedAt": _iso(score.published_at) or "",
        },
        "trail": list(work_order.trail_json or []),
        "createdAt": _iso(work_order.created_at) or "",
        "updatedAt": _iso(work_order.updated_at) or "",
    }


def _service_student(db, student: StudentProfile) -> CsServiceStudent:
    row = db.scalars(
        select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(),
            CsServiceStudent.student_id == student.id,
            CsServiceStudent.is_deleted.is_(False),
        )
    ).first()
    if row:
        return row
    row = CsServiceStudent(
        tenant_id=_tid(),
        student_id=student.id,
        student_no=student.student_no,
        name=student.real_name or student.student_no or "学生",
        college_name=getattr(student, "college_name", None),
        major_name=getattr(student, "major_name", None),
        class_id=str(getattr(student, "class_id", "") or "") or None,
        class_name=getattr(student, "class_name", None),
        grade=getattr(student, "grade", None),
    )
    db.add(row)
    db.flush()
    return row


def create(user: dict, body: dict | None) -> dict:
    _require_student(user)
    b = body or {}
    reason = str(b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 个字")

    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise not_found("未找到当前学生档案")

        from app.modules.internship.services.internship_record_resolver import resolve_student_internship_context

        ctx = resolve_student_internship_context(
            db,
            student=student,
            batch_id=b.get("batchId"),
            for_write=False,
        )
        record = ctx.record
        explicit_internship_id = str(b.get("internshipId") or "").strip()
        if explicit_internship_id:
            direct = db.get(InternshipRecord, _as_id(explicit_internship_id))
            if (
                not direct
                or direct.is_deleted
                or direct.tenant_id != _tid()
                or direct.student_id != student.id
            ):
                raise not_found("该实习记录不存在或不属于当前学生")
            if b.get("batchId") and str(direct.batch_id or "") != str(b.get("batchId")):
                raise AppException("DATA_CONFLICT", "实习记录与所选批次不一致，请刷新后重试")
            record = direct
        if not record:
            if ctx.mode == "need_select":
                raise AppException(
                    "NEED_SELECT",
                    "你有多条实习记录，请先选择批次后再提交成绩申诉",
                    details={"candidates": ctx.candidates},
                )
            raise not_found("当前没有可申诉的实习记录")
        if record.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "实习已最终归档，成绩异议请走档案更正流程")

        archive = _archive_locked(db, record.id)
        if archive and archive.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "该实习已形成最终归档，成绩异议请走档案更正流程")

        score = db.scalars(
            select(InternshipFinalScore)
            .where(
                InternshipFinalScore.tenant_id == _tid(),
                InternshipFinalScore.internship_id == record.id,
                InternshipFinalScore.student_id == student.id,
                InternshipFinalScore.status == "PUBLISHED",
                InternshipFinalScore.is_deleted.is_(False),
            )
            .with_for_update()
        ).first()
        if not score:
            raise AppException("DATA_CONFLICT", "当前没有已发布成绩，暂不能发起成绩申诉")

        cs_student = _service_student(db, student)
        active = db.scalars(
            select(CsWorkOrder)
            .where(
                CsWorkOrder.tenant_id == _tid(),
                CsWorkOrder.cs_student_id == cs_student.id,
                CsWorkOrder.title == APPEAL_KEY,
                CsWorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
                CsWorkOrder.is_deleted.is_(False),
            )
            .with_for_update()
        ).all()
        for item in active:
            try:
                item_meta = _meta(item)
            except AppException as exc:
                raise AppException(
                    "DATA_CONFLICT",
                    "存在未迁移的历史成绩申诉工单，请先由管理员核对后再提交",
                ) from exc
            if str(item_meta.get("internshipId")) == str(record.id):
                raise AppException("DATA_CONFLICT", "该实习已有待处理的成绩申诉，请勿重复提交")

        now = datetime.utcnow()
        meta = {
            "kind": META_KIND,
            "internshipId": str(record.id),
            "studentId": str(student.id),
            "batchId": str(record.batch_id or ""),
            "scoreId": str(score.id),
            "scoreVersion": int(score.version or 0),
            "scoreTotal": score.total_score,
            "scorePublishedAt": _iso(score.published_at) or "",
        }
        work_order = CsWorkOrder(
            tenant_id=_tid(),
            cs_student_id=cs_student.id,
            title=APPEAL_KEY,
            wo_type="COMPLAINT",
            priority="HIGH",
            status="PENDING_HANDLE",
            detail=reason,
            trail_json=[
                {"at": now.isoformat(), "action": "SUBMIT", "note": reason, "operator": student.real_name or "学生"},
                meta,
            ],
        )
        db.add(work_order)
        db.flush()
        db.add(
            InternshipAuditTrail(
                tenant_id=_tid(),
                target_id=record.id,
                target_type="SCORE_APPEAL",
                action="SUBMIT",
                operator_name=student.real_name or "学生",
                detail_json={
                    "workOrderId": str(work_order.id),
                    "scoreId": str(score.id),
                    "scoreVersion": int(score.version or 0),
                    "reason": reason,
                },
                occurred_at=now,
            )
        )
        db.commit()
        return {
            "id": str(work_order.id),
            "status": "PENDING",
            "statusLabel": "待处理",
            "version": int(work_order.version or 0),
            "internshipId": str(record.id),
            "scoreId": str(score.id),
            "scoreVersion": int(score.version or 0),
            "message": "成绩申诉已提交，学校处理时将校验原成绩版本",
        }


def list_appeals(user: dict, *, page: int = 1, page_size: int = 20, status: str | None = None,
                 batch_id: str | None = None) -> tuple[list[dict], int]:
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    with session() as db:
        query = select(CsWorkOrder).where(
            CsWorkOrder.tenant_id == _tid(),
            CsWorkOrder.title == APPEAL_KEY,
            CsWorkOrder.is_deleted.is_(False),
        ).order_by(CsWorkOrder.id.desc())
        candidates = list(db.scalars(query).all())
        visible = []
        for work_order in candidates:
            try:
                meta = _meta(work_order)
                record, student = _record_and_student(db, meta)
                _assert_scope(db, user, record, student)
                if batch_id and str(record.batch_id or "") != str(batch_id):
                    continue
                row = _row(db, work_order, record=record, student=student)
                if status and row["status"] != status:
                    continue
                visible.append(row)
            except AppException as exc:
                if exc.code == "NO_PERMISSION":
                    continue
                raise
        total = len(visible)
        start = (page - 1) * page_size
        return visible[start:start + page_size], total


def get_appeal(user: dict, appeal_id) -> dict:
    with session() as db:
        work_order = db.get(CsWorkOrder, _as_id(appeal_id))
        if (
            not work_order
            or work_order.is_deleted
            or work_order.tenant_id != _tid()
            or work_order.title != APPEAL_KEY
        ):
            raise not_found("成绩申诉不存在")
        record, student = _record_and_student(db, _meta(work_order))
        _assert_scope(db, user, record, student)
        return _row(db, work_order, record=record, student=student)


def decide(user: dict, appeal_id, body: dict | None, *, approve: bool) -> dict:
    from app.core.permissions import enforce_permission

    enforce_permission(user or {}, "internship.score.publish")
    _assert_final_reviewer(user)
    b = body or {}
    note = str(b.get("reason") or b.get("note") or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "处理意见不少于 5 个字")
    expected_version = extract_expected_version(b)

    with session() as db:
        work_order = db.scalars(
            select(CsWorkOrder)
            .where(
                CsWorkOrder.id == _as_id(appeal_id),
                CsWorkOrder.tenant_id == _tid(),
                CsWorkOrder.title == APPEAL_KEY,
                CsWorkOrder.is_deleted.is_(False),
            )
            .with_for_update()
        ).first()
        if not work_order:
            raise not_found("成绩申诉不存在")
        if work_order.status not in ACTIVE_WORK_ORDER_STATUSES:
            raise AppException("DATA_CONFLICT", "该成绩申诉已处理，请刷新后重试")

        meta = _meta(work_order)
        record, student = _record_and_student(db, meta)
        _assert_scope(db, user, record, student)
        now = datetime.utcnow()
        trail = list(work_order.trail_json or [])

        if approve:
            archive = _archive_locked(db, record.id)
            if record.status == "ARCHIVED" or (archive and archive.status == "ARCHIVED"):
                raise AppException("DATA_CONFLICT", "该实习已最终归档，不能通过普通申诉撤回成绩")

            score = _score_for_meta(db, meta, lock=True)
            frozen_score_version = int(meta.get("scoreVersion") or 0)
            if score.status != "PUBLISHED":
                raise AppException("DATA_CONFLICT", "原成绩已不是已发布状态，请刷新申诉后重新判断")
            if int(score.version or 0) != frozen_score_version:
                raise AppException("DATA_CONFLICT", "原成绩在申诉期间已发生变化，请重新核对后处理")

            score_version = versioned_update(
                db,
                InternshipFinalScore,
                entity_id=score.id,
                tenant_id=_tid(),
                expected_version=frozen_score_version,
                expected_status="PUBLISHED",
                values={"status": "WITHDRAWN"},
            )
            from app.modules.internship.services.internship_score_service import _trail as score_trail

            score_trail(
                db,
                score.id,
                "WITHDRAW",
                {
                    "reason": note,
                    "source": "SCORE_APPEAL",
                    "workOrderId": str(work_order.id),
                    "actorUserId": str((user or {}).get("userId") or ""),
                    "actorRole": str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or ""),
                },
                operator=_operator(user),
            )
            trail.append({
                "at": now.isoformat(),
                "action": "APPROVE",
                "note": note,
                "operator": _operator(user),
                "scoreStatus": "WITHDRAWN",
                "scoreVersion": score_version,
            })
            new_work_order_version = versioned_update(
                db,
                CsWorkOrder,
                entity_id=work_order.id,
                tenant_id=_tid(),
                expected_version=expected_version,
                values={
                    "status": "COMPLETED",
                    "handler": _operator(user),
                    "close_time": now,
                    "trail_json": trail,
                },
                extra_where=(CsWorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),),
            )
            audit_action = "APPROVE_WITHDRAW_SCORE"
            message = "申诉已受理，原已发布成绩已撤回；请重新核算、复核并发布"
        else:
            trail.append({
                "at": now.isoformat(),
                "action": "REJECT",
                "note": note,
                "operator": _operator(user),
            })
            new_work_order_version = versioned_update(
                db,
                CsWorkOrder,
                entity_id=work_order.id,
                tenant_id=_tid(),
                expected_version=expected_version,
                values={
                    "status": "CLOSED",
                    "handler": _operator(user),
                    "close_time": now,
                    "trail_json": trail,
                },
                extra_where=(CsWorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),),
            )
            audit_action = "REJECT"
            message = "成绩申诉已驳回，原成绩保持不变"

        db.add(
            InternshipAuditTrail(
                tenant_id=_tid(),
                target_id=record.id,
                target_type="SCORE_APPEAL",
                action=audit_action,
                operator_name=_operator(user),
                detail_json={
                    "workOrderId": str(work_order.id),
                    "scoreId": str(meta.get("scoreId") or ""),
                    "frozenScoreVersion": int(meta.get("scoreVersion") or 0),
                    "reason": note,
                },
                occurred_at=now,
            )
        )
        db.commit()
        return {
            "id": str(work_order.id),
            "version": new_work_order_version,
            "status": "APPROVED_RECALCULATING" if approve else "REJECTED",
            "message": message,
            "internshipId": str(record.id),
            "scoreId": str(meta.get("scoreId") or ""),
        }


def is_score_appeal(work_order: CsWorkOrder | None) -> bool:
    return bool(work_order and work_order.title == APPEAL_KEY and not work_order.is_deleted)

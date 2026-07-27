"""任务书旧实现收口：并发锁、批次统计、正式 PDF 水印和状态统一。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import GraduationStudent, GraduationTaskBook, GraduationTemplate
from app.modules.graduation.policies import taskbook_policy
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access
from app.services.db_service import _iso, _tid, session

_INSTALLED = False


def taskbook_stats(batch_id=None) -> dict:
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.is_deleted.is_(False),
            GraduationTaskBook.gd_student_id.in_(scope_ids or [-1]),
        ]
        from app.modules.graduation.services import graduation_taskbook_service as svc
        total = int(db.scalar(select(func.count()).select_from(GraduationTaskBook).where(*base)) or 0)
        by_status = [{
            "status": status, "label": svc.STATUS_LABEL[status],
            "count": int(db.scalar(select(func.count()).select_from(GraduationTaskBook).where(
                *base, GraduationTaskBook.status == status,
            )) or 0),
        } for status in svc.STATUS_LABEL]
        eligible = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.mentor_id.is_not(None), GraduationStudent.stage != "TOPIC_SELECTING",
            GraduationStudent.id.in_(scope_ids or [-1]),
        )) or 0)
        return {"batchId": str(batch_id), "total": total, "byStatus": by_status,
                "noTaskbookYet": max(0, eligible - total)}


def issue_taskbook(gd_student_id, body: dict) -> dict:
    from app.modules.graduation.services import graduation_taskbook_service as svc
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id), GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "taskbook.issue")
        if not student.mentor_id:
            raise AppException("DATA_CONFLICT", "该生尚未绑定稳定导师，无法下达任务书")
        existing = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(),
            GraduationTaskBook.gd_student_id == student.id,
            GraduationTaskBook.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            raise AppException("DATA_CONFLICT", "该生已有任务书，如需调整请使用变更")
        operator, _ = svc._op()
        row = GraduationTaskBook(
            tenant_id=_tid(), gd_student_id=student.id, mentor_id=student.mentor_id,
            objective=body.get("objective"), content=body.get("content"),
            progress_plan=body.get("progressPlan"), outcome_requirement=body.get("outcomeRequirement"),
            taskbook_version=1, status="PENDING_CONFIRM", issued_by=operator,
            issued_at=datetime.now(timezone.utc), history_json=[],
        )
        db.add(row)
        db.flush()
        svc._audit(db, row.id, "下达任务书", detail=f"{student.name} v1")
        db.commit()
        return svc._row(row, student)


def change_taskbook(gd_student_id, body: dict) -> dict:
    from app.modules.graduation.services import graduation_taskbook_service as svc
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id), GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "taskbook.update")
        row = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(),
            GraduationTaskBook.gd_student_id == student.id,
            GraduationTaskBook.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("尚未下达任务书")
        if row.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅已确认任务书可发起变更")
        history = list(row.history_json or [])
        history.append({
            "version": row.taskbook_version, "objective": row.objective, "content": row.content,
            "progressPlan": row.progress_plan, "outcomeRequirement": row.outcome_requirement,
            "confirmedAt": _iso(row.confirmed_at),
        })
        row.history_json = history
        for source, column in (
            ("objective", "objective"), ("content", "content"),
            ("progressPlan", "progress_plan"), ("outcomeRequirement", "outcome_requirement"),
        ):
            if body.get(source) is not None:
                setattr(row, column, body[source])
        row.taskbook_version = int(row.taskbook_version or 1) + 1
        row.status = "CHANGE_PENDING"
        row.change_reason = reason
        row.confirmed_at = None
        svc._audit(db, row.id, "变更任务书（待重新确认）", reason, "CONFIRMED", "CHANGE_PENDING")
        db.commit()
        return svc._row(row, student)


def confirm_taskbook(gd_student_id, proxy_reason: str | None = None) -> dict:
    """学校端代确认：鉴权、原因、学生与任务书锁、状态推进均在同一事务。"""
    from app.modules.graduation.services import graduation_taskbook_service as svc

    user = get_current_user_ctx() or {}
    role = str(user.get("currentRoleCode") or "").strip().upper()
    user_type = str(user.get("userType") or "").strip().upper()
    if user_type == "STUDENT" or role == "STUDENT":
        raise no_permission("学生本人须通过带版本校验的电子确认入口")
    reason = str(proxy_reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "管理员代确认须填写原因（不少于 5 字）")

    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "taskbook.confirmOnBehalf")
        taskbook_policy.authorize(db, student, "confirmOnBehalf")
        row = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(),
            GraduationTaskBook.gd_student_id == student.id,
            GraduationTaskBook.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("尚未下达任务书")
        if row.status == "CONFIRMED":
            raise AppException("DATA_CONFLICT", "任务书已确认，无需重复确认")
        if row.status not in ("PENDING_CONFIRM", "CHANGE_PENDING"):
            raise AppException("DATA_CONFLICT", "当前任务书状态不允许代确认")
        before = row.status
        row.status = "CONFIRMED"
        row.confirmed_at = datetime.now(timezone.utc)
        if student.stage == "TASKBOOK_CONFIRM":
            student.stage = "GUIDING"
            student.version = int(student.version or 0) + 1
        svc._audit(db, row.id, "管理员代确认任务书", reason, before, "CONFIRMED")
        from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
        notify_risk_rescan(db, student.id)
        db.commit()
        return svc._row(row, student)


def confirm_taskbook_in_session(db, gd_student_id) -> dict:
    from app.modules.graduation.services import graduation_taskbook_service as svc
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(gd_student_id),
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    ).with_for_update()).first()
    if not student:
        raise not_found("毕设学生不存在")
    assert_student_access(db, student, "taskbook.confirm")
    row = db.scalars(select(GraduationTaskBook).where(
        GraduationTaskBook.tenant_id == _tid(),
        GraduationTaskBook.gd_student_id == student.id,
        GraduationTaskBook.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("尚未下达任务书")
    if row.status == "CONFIRMED":
        raise AppException("DATA_CONFLICT", "任务书已确认，无需重复确认")
    if row.status not in ("PENDING_CONFIRM", "CHANGE_PENDING"):
        raise AppException("DATA_CONFLICT", "当前任务书状态不允许确认")
    before = row.status
    row.status = "CONFIRMED"
    row.confirmed_at = datetime.now(timezone.utc)
    if student.stage == "TASKBOOK_CONFIRM":
        student.stage = "GUIDING"
        student.version = int(student.version or 0) + 1
    svc._audit(db, row.id, "学生确认任务书", before=before, after="CONFIRMED")
    db.flush()
    return svc._row(row, student)


def export_taskbook_pdf(gd_student_id, template_id: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_taskbook_service as svc
    from app.services.pdf_util import build_text_pdf, pack_pdf_result

    with svc.session() as db:
        student = svc._stu(db, gd_student_id)
        if not student or student.is_deleted or student.tenant_id != svc._tid():
            raise not_found("毕设学生不存在")
        from sqlalchemy.orm import Session as _OrmSession
        if isinstance(db, _OrmSession):
            assert_student_access(db, student, "taskbook.export")
        row = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == svc._tid(), GraduationTaskBook.gd_student_id == student.id,
            GraduationTaskBook.is_deleted.is_(False),
        )).first()
        if not row:
            raise AppException("DATA_CONFLICT", "该生尚未下达任务书，无法导出 PDF")
        template = None
        if template_id:
            template = db.get(GraduationTemplate, int(template_id))
            if (not template or template.is_deleted or template.tenant_id != svc._tid()
                    or template.template_type != "TASKBOOK" or template.status != "ENABLED"):
                raise AppException("VALIDATION_ERROR", "指定的任务书模板不存在或未启用")
        else:
            template = db.scalars(select(GraduationTemplate).where(
                GraduationTemplate.tenant_id == svc._tid(), GraduationTemplate.template_type == "TASKBOOK",
                GraduationTemplate.status == "ENABLED", GraduationTemplate.is_deleted.is_(False),
            ).order_by(GraduationTemplate.is_default.desc(), GraduationTemplate.id.desc())).first()
        variables = svc._taskbook_print_vars(student, row)
        if template and (template.content or "").strip():
            body = svc._fill_template(template.content, variables)
            if "{" not in (template.content or ""):
                body += "\n\n——\n" + svc._builtin_taskbook_body(variables)
            title = template.name or "毕业设计任务书"
            source = f"template:{template.id}"
        else:
            body = svc._builtin_taskbook_body(variables)
            title, source = "毕业设计任务书", "builtin"
        operator, _ = svc._op()
        watermark = f"导出人：{operator} · 毕业设计任务书正式套打 · {datetime.now():%Y-%m-%d %H:%M}"
        pdf_bytes = build_text_pdf(title, body, watermark=watermark)
        svc._audit(db, row.id, "导出任务书PDF", detail=f"{student.name} v{row.taskbook_version} · {source}")
        db.commit()
        safe_no = (student.student_no or str(student.id)).replace("/", "_")
        packed = pack_pdf_result(pdf_bytes, f"任务书_{student.name}_{safe_no}.pdf")
        packed.update({"templateSource": source, "gdStudentId": str(student.id), "taskbookId": str(row.id)})
        return packed


def install_taskbook_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    from app.modules.graduation.services import graduation_taskbook_service as svc
    svc.taskbook_stats = taskbook_stats
    svc.issue_taskbook = issue_taskbook
    svc.change_taskbook = change_taskbook
    svc.confirm_taskbook = confirm_taskbook
    svc.confirm_taskbook_in_session = confirm_taskbook_in_session
    svc.export_taskbook_pdf = export_taskbook_pdf

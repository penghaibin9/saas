"""V9.2 U5/M8 · 毕设学生列表只读模型。

列表只在 SQL 侧完成 dataScope 收窄、关键词/材料条件、COUNT、排序与分页。
材料完整性严格取“该生最新未删除开题 + 最新未删除成果”两条事实；历史曾通过不能冒充当前最新版本通过。
正式写链继续由 graduation_student_service 负责。
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.models import GraduationBatch, GraduationFinal, GraduationProposal, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, has_full_scope
from app.services.db_service import _tid, session


def _latest_status(model):
    return (
        select(model.status)
        .where(
            model.tenant_id == _tid(),
            model.gd_student_id == GraduationStudent.id,
            model.is_deleted.is_(False),
        )
        .order_by(model.id.desc())
        .limit(1)
        .correlate(GraduationStudent)
        .scalar_subquery()
    )


def _material_snapshot(proposal_status, final_status) -> dict:
    from app.modules.graduation.services import graduation_student_service as svc

    proposal_status = proposal_status or "NOT_SUBMITTED"
    final_status = final_status or "NOT_SUBMITTED"
    gaps = []
    if proposal_status != "APPROVED":
        gaps.append("开题")
    if final_status != "APPROVED":
        gaps.append("成果")
    return {
        "proposalStatus": proposal_status,
        "proposalStatusLabel": svc.MAT_LABEL.get(proposal_status, proposal_status),
        "finalStatus": final_status,
        "finalStatusLabel": svc.MAT_LABEL.get(final_status, final_status),
        "materialGap": "、".join(gaps) if gaps else "齐全",
        "materialComplete": not gaps,
    }


def list_students(
    page: int,
    page_size: int,
    keyword=None,
    class_id=None,
    batch_id=None,
    stage=None,
    risk_level=None,
    advisor_name=None,
    has_topic=None,
    eligibility=None,
    student_group=None,
    has_defense_group=None,
    grad_qual_status=None,
    material_complete=None,
    archive_view=None,
) -> tuple[list[dict], int]:
    from app.modules.graduation.services import graduation_student_service as svc

    tenant_id = _tid()
    proposal_status = _latest_status(GraduationProposal)
    final_status = _latest_status(GraduationFinal)
    proposal_current = func.coalesce(proposal_status, "NOT_SUBMITTED")
    final_current = func.coalesce(final_status, "NOT_SUBMITTED")

    filters = [
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    ]
    if class_id:
        filters.append(GraduationStudent.class_id == class_id)
    if batch_id:
        filters.append(GraduationStudent.batch_id == int(batch_id))
    if stage:
        filters.append(GraduationStudent.stage == stage)
    if risk_level:
        filters.append(GraduationStudent.risk_level == risk_level)
    if advisor_name:
        filters.append(GraduationStudent.advisor_name == advisor_name)
    if has_topic is True:
        filters.append(GraduationStudent.topic_id.is_not(None))
    elif has_topic is False:
        filters.append(GraduationStudent.topic_id.is_(None))
    if eligibility:
        filters.append(GraduationStudent.eligibility_status == eligibility)
    if student_group:
        filters.append(GraduationStudent.student_group == student_group)
    if has_defense_group is True:
        filters.append(GraduationStudent.defense_group_id.is_not(None))
    elif has_defense_group is False:
        filters.append(GraduationStudent.defense_group_id.is_(None))
    if grad_qual_status:
        filters.append(GraduationStudent.grad_qual_status == grad_qual_status)
    if archive_view == "archived":
        filters.append(GraduationStudent.stage == "ARCHIVED")
    elif archive_view == "candidates":
        filters.append(GraduationStudent.stage != "ARCHIVED")

    value = str(keyword or "").strip()
    if value:
        filters.append(or_(
            GraduationStudent.name.contains(value),
            GraduationStudent.student_no.contains(value),
            GraduationStudent.topic_title.contains(value),
        ))

    if material_complete is True:
        filters.extend((proposal_current == "APPROVED", final_current == "APPROVED"))
    elif material_complete is False:
        filters.append(or_(proposal_current != "APPROVED", final_current != "APPROVED"))

    with session() as db:
        if not has_full_scope():
            scope_ids = accessible_student_ids(db, tenant_id, batch_id=batch_id)
            filters.append(GraduationStudent.id.in_(scope_ids or [-1]))

        total = int(db.scalar(
            select(func.count()).select_from(GraduationStudent).where(*filters)
        ) or 0)

        batch_on = and_(
            GraduationBatch.id == GraduationStudent.batch_id,
            GraduationBatch.tenant_id == tenant_id,
            GraduationBatch.is_deleted.is_(False),
        )
        rows = db.execute(
            select(
                GraduationStudent,
                GraduationBatch,
                proposal_status.label("proposal_status"),
                final_status.label("final_status"),
            )
            .outerjoin(GraduationBatch, batch_on)
            .where(*filters)
            .order_by(GraduationStudent.id.desc())
            .offset((max(1, page) - 1) * page_size)
            .limit(page_size)
        ).all()

        return [
            svc._row(student, batch, _material_snapshot(prop_status, fin_status))
            for student, batch, prop_status, fin_status in rows
        ], total

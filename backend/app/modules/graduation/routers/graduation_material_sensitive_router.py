"""开题、成果、答辩编排与审计的学校端批次安全接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.models import (
    GraduationAuditTrail,
    GraduationDefenseGroup,
    GraduationFinal,
    GraduationProposal,
    GraduationStudent,
)
from app.modules.graduation.schemas.graduation import AssignStudentsBody, DefenseGroupBody, RemindBody, ReviewBody
from app.modules.graduation.materials import query_service as material_queries
from app.modules.graduation.materials import record_service as material_records
from app.modules.graduation.schemas.graduation_extra import ProposalDefenseBody
from app.modules.graduation.services import graduation_service as svc
from app.modules.graduation.services import graduation_student_service as student_svc
from app.modules.graduation.services.graduation_batch_context import assert_student_batch, load_student_in_batch, require_batch_id
from app.modules.graduation.services.graduation_response_mapper import _normalize_members
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _iso, _tid, session

router = APIRouter(prefix="/graduation", tags=["毕业设计-材料与答辩批次安全"])


def _record_student(model, record_id, batch_id) -> GraduationStudent:
    with session() as db:
        record = db.scalars(select(model).where(
            model.id == int(record_id), model.tenant_id == _tid(), model.is_deleted.is_(False),
        )).first()
        if not record:
            raise not_found("毕业设计材料不存在")
        student = db.get(GraduationStudent, int(record.gd_student_id))
        assert_student_batch(student, batch_id)
        return student


def _group(group_id, batch_id) -> GraduationDefenseGroup:
    with session() as db:
        group = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.id == int(group_id),
            GraduationDefenseGroup.tenant_id == _tid(),
            GraduationDefenseGroup.is_deleted.is_(False),
        )).first()
        if not group:
            raise not_found("答辩组不存在")
        if int(group.batch_id or 0) != require_batch_id(batch_id):
            raise AppException("DATA_CONFLICT", "当前页面批次与答辩组批次不一致，请刷新")
        return group


def _normalize_group(value):
    if isinstance(value, list):
        return [_normalize_members(item) for item in value]
    return _normalize_members(value)


@router.get("/dashboard", summary="毕业设计工作台（当前批次）")
def dashboard(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(svc.get_dashboard(batch_id=require_batch_id(batchId)))


@router.get("/students", summary="毕业设计学生概览（当前批次）")
def legacy_students(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, classId: Optional[str] = None,
    stage: Optional[str] = None, riskLevel: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = student_svc.list_students(
        page, pageSize, keyword=keyword, class_id=classId, batch_id=batchId,
        stage=stage, risk_level=riskLevel,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/students/{student_id}", summary="毕业设计学生详情（当前批次）")
def legacy_student_detail(
    student_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, student_id, batchId)
    return success(svc.get_student_detail(student_id))


@router.get("/proposals/stats")
def proposal_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(svc.proposal_stats(batch_id=batchId))


@router.get("/proposals")
def proposals(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = svc.list_proposals(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.get("/proposals/{proposal_id}")
def proposal_detail(
    proposal_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId)
    return success(material_queries.proposal_detail(int(proposal_id), user))


@router.post("/proposals/{proposal_id}/review")
def proposal_review(
    proposal_id: str, body: ReviewBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId)
    return success(material_records.review_proposal(
        int(proposal_id), body.action, body.comment, user,
        expected_version=body.expectedVersion, expected_file_version_id=body.fileVersionId,
    ), message="已批阅")


@router.post("/proposals/{proposal_id}/defense")
def proposal_defense(
    proposal_id: str, body: ProposalDefenseBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId)
    return success(svc.hold_proposal_defense(proposal_id, body.result, body.comment), message="开题答辩结果已保存")


@router.post("/proposals/remind")
def proposal_remind(
    body: RemindBody, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, body.gdStudentId, batchId)
    result = svc.remind_proposal(body.gdStudentId, body.channel or "站内消息")
    return success(result, message="真实站内消息已创建")


@router.post("/proposals/export")
def proposal_export(
    status: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_proposals_xlsx(status=status, keyword=keyword, batch_id=batchId))


@router.get("/finals/stats")
def final_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(svc.final_stats(batch_id=batchId))


@router.get("/finals")
def finals(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = svc.list_finals(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.get("/finals/{final_id}")
def final_detail(
    final_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_student(GraduationFinal, final_id, batchId)
    return success(material_queries.final_detail(int(final_id), user))


@router.post("/finals/{final_id}/review")
def final_review(
    final_id: str, body: ReviewBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_student(GraduationFinal, final_id, batchId)
    return success(material_records.review_final(
        int(final_id), body.action, body.comment, user,
        expected_version=body.expectedVersion, expected_file_version_id=body.fileVersionId,
    ), message="已批阅")


@router.post("/finals/remind")
def final_remind(
    body: RemindBody, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, body.gdStudentId, batchId)
    result = svc.remind_final(body.gdStudentId, body.channel or "站内消息")
    return success(result, message="真实站内消息已创建")


@router.post("/finals/export")
def final_export(
    status: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_finals_xlsx(status=status, keyword=keyword, batch_id=batchId))


@router.get("/defense-groups")
def defense_groups(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    items, total = svc.list_defense_groups(page, pageSize, keyword=keyword, batch_id=batchId)
    return success(paginate(_normalize_group(items), total, page, pageSize))


@router.post("/defense-groups")
def defense_create(
    body: DefenseGroupBody, batchId: int | None = Query(default=None), user=Depends(get_current_user),
):
    expected = require_batch_id(batchId)
    if body.batchId not in (None, expected):
        raise AppException("DATA_CONFLICT", "请求体批次与页面批次不一致")
    result = svc.create_defense_group(
        body.groupName, body.defenseDate, body.location, body.chair, body.members, body.secretary,
        batch_id=expected, chair_mentor_id=body.chairMentorId,
        secretary_mentor_id=body.secretaryMentorId, member_mentor_ids=body.memberMentorIds,
    )
    return success(_normalize_group(result), message="已创建")


@router.get("/defense-groups/eligible-students")
def defense_eligible(
    gid: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    batch_id = require_batch_id(batchId)
    group_id = int(gid) if gid else None
    if group_id:
        _group(group_id, batch_id)
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        query = select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == batch_id,
            GraduationStudent.id.in_(scope_ids or [-1]), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.stage.in_(("FINAL_CHECK", "DEFENSE", "COMPLETED")),
        ).order_by(GraduationStudent.id)
        rows = db.scalars(query).all()
        result = []
        for student in rows:
            if keyword and keyword.strip() not in (student.name or ""):
                continue
            approved_final = db.scalars(select(GraduationFinal.id).where(
                GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
                GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
                GraduationFinal.is_deleted.is_(False),
            ).limit(1)).first()
            if not approved_final:
                continue
            result.append({
                "id": str(student.id), "name": student.name,
                "className": student.class_name or "", "topicTitle": student.topic_title or "",
                "advisorName": student.advisor_name or "", "batchId": str(student.batch_id),
                "currentGroup": student.defense_group or "",
                "assignedHere": student.defense_group_id == group_id if group_id else False,
                "assignedElsewhere": bool(student.defense_group_id) and student.defense_group_id != group_id,
            })
        return success(result)


@router.get("/defense-groups/{group_id}")
def defense_detail(
    group_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId)
    return success(_normalize_group(svc.get_defense_group_detail(group_id)))


@router.put("/defense-groups/{group_id}")
def defense_update(
    group_id: str, body: DefenseGroupBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId)
    result = svc.update_defense_group(
        group_id, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds, batch_id=batchId,
    )
    return success(_normalize_group(result), message="已保存")


@router.post("/defense-groups/{group_id}/assign")
def defense_assign(
    group_id: str, body: AssignStudentsBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId)
    return success(_normalize_group(svc.assign_defense_students(
        group_id, body.studentIds, batch_id=batchId,
    )), message="已分配")


@router.post("/defense-groups/{group_id}/unassign")
def defense_unassign(
    group_id: str, body: AssignStudentsBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId)
    return success(_normalize_group(svc.unassign_defense_students(
        group_id, body.studentIds, batch_id=batchId,
    )), message="已移出")


@router.post("/defense-groups/{group_id}/publish")
def defense_publish(
    group_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId)
    return success(svc.publish_defense(group_id, batch_id=batchId), message="已发布")


@router.post("/defense-groups/{group_id}/notify")
def defense_notify(
    group_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId)
    result = svc.notify_defense_group(group_id, user=user, batch_id=batchId)
    return success(result, message=result.get("message") or "通知已进入发送队列")


@router.post("/defense-groups/export")
def defense_export(
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_defense_xlsx(batch_id=batchId))


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    bizType: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    with session() as db:
        query = select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.batch_id == int(batchId),
        )
        if bizType:
            query = query.where(GraduationAuditTrail.biz_type == bizType)
        rows = db.scalars(query.order_by(GraduationAuditTrail.id.desc())).all()
        if keyword:
            value = keyword.strip()
            rows = [row for row in rows if value in (row.action or "") or value in (row.detail or "")]
        total = len(rows)
        start = (page - 1) * pageSize
        items = [{
            "id": str(row.id), "time": _iso(row.occurred_at),
            "operator": row.actor_name_snapshot or row.operator or "",
            "operatorAccount": str(row.actor_user_id or ""),
            "roleName": row.role_code or row.role_name or "",
            "permissionCode": row.permission_code or "", "batchId": str(row.batch_id or ""),
            "dataScope": row.data_scope_snapshot or {}, "bizType": row.biz_type,
            "bizId": row.biz_id or "", "action": row.action, "detail": row.detail or "",
            "before": row.before_val or "", "after": row.after_val or "",
            "requestId": row.request_id or "", "traceId": row.request_id or "",
            "requestPath": row.request_path or "", "clientIp": row.client_ip or "",
        } for row in rows[start:start + pageSize]]
        return success(paginate(items, total, page, pageSize))

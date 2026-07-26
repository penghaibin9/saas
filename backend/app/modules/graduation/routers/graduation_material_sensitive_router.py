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
from app.modules.graduation.schemas.graduation import (
    AssignStudentsBody,
    DefenseGroupBody,
    RemindBody,
    ReviewBody,
)
from app.modules.graduation.schemas.graduation_extra import ProposalDefenseBody
from app.modules.graduation.services import graduation_service as svc
from app.modules.graduation.services import graduation_student_service as student_svc
from app.modules.graduation.services.graduation_batch_context import (
    assert_student_batch,
    load_student_in_batch,
    require_batch_id,
)
from app.modules.graduation.services.graduation_contract_bridge import _normalize_members
from app.modules.graduation.services.graduation_material_consistency import install_material_consistency
from app.services.db_service import _iso, _tid, session

install_material_consistency()
router = APIRouter(prefix="/graduation", tags=["毕业设计-材料与答辩批次安全"])


def _record_student(model, record_id, batch_id, *, lock=False) -> GraduationStudent:
    with session() as db:
        query = select(model).where(
            model.id == int(record_id), model.tenant_id == _tid(), model.is_deleted.is_(False),
        )
        if lock:
            query = query.with_for_update()
        record = db.scalars(query).first()
        if not record:
            raise not_found("毕业设计材料不存在")
        student = db.get(GraduationStudent, int(record.gd_student_id))
        assert_student_batch(student, batch_id)
        return student


def _group(group_id, batch_id, *, lock=False) -> GraduationDefenseGroup:
    with session() as db:
        query = select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.id == int(group_id),
            GraduationDefenseGroup.tenant_id == _tid(),
            GraduationDefenseGroup.is_deleted.is_(False),
        )
        if lock:
            query = query.with_for_update()
        group = db.scalars(query).first()
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
    student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    load_student_in_batch(session().__enter__(), student_id, batchId)  # pragma: no cover - replaced below


# 上面的上下文管理器不能跨函数返回，重新绑定成显式安全实现。
router.routes.pop()


@router.get("/students/{student_id}", summary="毕业设计学生详情（当前批次）")
def legacy_student_detail_safe(
    student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, student_id, batchId)
    return success(svc.get_student_detail(student_id))


# ── 开题 ──
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
    proposal_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId)
    return success(svc.get_proposal_detail(proposal_id))


@router.post("/proposals/{proposal_id}/review")
def proposal_review(
    proposal_id: str, body: ReviewBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId, lock=True)
    return success(svc.review_proposal(proposal_id, body.action, body.comment), message="已批阅")


@router.post("/proposals/{proposal_id}/defense")
def proposal_defense(
    proposal_id: str, body: ProposalDefenseBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_student(GraduationProposal, proposal_id, batchId, lock=True)
    return success(svc.hold_proposal_defense(proposal_id, body.result, body.comment), message="开题答辩结果已保存")


@router.post("/proposals/remind")
def proposal_remind(
    body: RemindBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, body.gdStudentId, batchId, for_update=True)
    result = svc.remind_proposal(body.gdStudentId, body.channel or "站内消息")
    return success(result, message="真实站内消息已创建")


@router.post("/proposals/export")
def proposal_export(
    status: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_proposals_xlsx(status=status, keyword=keyword, batch_id=batchId))


# ── 成果 ──
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
    final_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_student(GraduationFinal, final_id, batchId)
    return success(svc.get_final_detail(final_id))


@router.post("/finals/{final_id}/review")
def final_review(
    final_id: str, body: ReviewBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_student(GraduationFinal, final_id, batchId, lock=True)
    return success(svc.review_final(final_id, body.action, body.comment), message="已批阅")


@router.post("/finals/remind")
def final_remind(
    body: RemindBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    with session() as db:
        load_student_in_batch(db, body.gdStudentId, batchId, for_update=True)
    result = svc.remind_final(body.gdStudentId, body.channel or "站内消息")
    return success(result, message="真实站内消息已创建")


@router.post("/finals/export")
def final_export(
    status: Optional[str] = None, keyword: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_finals_xlsx(status=status, keyword=keyword, batch_id=batchId))


# ── 答辩组 ──
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
    body: DefenseGroupBody, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
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
    if gid:
        _group(gid, batchId)
    rows = svc.list_defense_eligible_students(gid=gid, keyword=keyword)
    # gid 为空时仍限制当前批次，禁止候选人跨批出现。
    return success([row for row in rows if str(row.get("batchId") or batchId) == str(batchId)])


@router.get("/defense-groups/{group_id}")
def defense_detail(
    group_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId)
    return success(_normalize_group(svc.get_defense_group_detail(group_id)))


@router.put("/defense-groups/{group_id}")
def defense_update(
    group_id: str, body: DefenseGroupBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId, lock=True)
    result = svc.update_defense_group(
        group_id, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds, batch_id=batchId,
    )
    return success(_normalize_group(result), message="已保存")


@router.post("/defense-groups/{group_id}/assign")
def defense_assign(
    group_id: str, body: AssignStudentsBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId, lock=True)
    return success(_normalize_group(svc.assign_defense_students(
        group_id, body.studentIds, batch_id=batchId,
    )), message="已分配")


@router.post("/defense-groups/{group_id}/unassign")
def defense_unassign(
    group_id: str, body: AssignStudentsBody,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _group(group_id, batchId, lock=True)
    return success(_normalize_group(svc.unassign_defense_students(
        group_id, body.studentIds, batch_id=batchId,
    )), message="已移出")


@router.post("/defense-groups/{group_id}/publish")
def defense_publish(
    group_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId, lock=True)
    return success(svc.publish_defense(group_id, batch_id=batchId), message="已发布")


@router.post("/defense-groups/{group_id}/notify")
def defense_notify(
    group_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _group(group_id, batchId, lock=True)
    result = svc.notify_defense_group(group_id, user=user, batch_id=batchId)
    return success(result, message=result.get("message") or "通知已进入发送队列")


@router.post("/defense-groups/export")
def defense_export(
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(svc.export_defense_xlsx(batch_id=batchId))


# ── 审计：按批次筛选，不再将同一学生跨届操作混在一起 ──
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

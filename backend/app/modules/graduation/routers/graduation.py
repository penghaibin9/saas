"""毕业设计域 API（/api/v1/graduation/*）。真实走库；批阅/发布落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation import (AssignStudentsBody, DefenseGroupBody,  # noqa: F401
                                    ProposalSubmitBody, RemindBody, ReviewBody)
from app.services import audit_log
from app.modules.graduation.services import graduation_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计"])


def _p(i, t, page, ps):
    return success(paginate(i, t, page, ps))


@router.get("/dashboard", summary="毕设看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard())


@router.get("/students", summary="毕设学生列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             stage: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(get_current_user)):
    i, t = svc.list_students(page, pageSize, keyword=keyword, class_id=classId, stage=stage,
                             risk_level=riskLevel)
    return _p(i, t, page, pageSize)


@router.get("/students/{sid}", summary="毕设学生详情")
def student_detail(sid: str, user=Depends(get_current_user)):
    return success(svc.get_student_detail(sid))


@router.get("/topics", summary="选题列表")
def topics(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           user=Depends(get_current_user)):
    i, t = svc.list_topics(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/proposals", summary="开题材料列表")
def proposals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(get_current_user)):
    i, t = svc.list_proposals(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/proposals/stats", summary="开题统计（状态分布+未提交）")
def proposal_stats(user=Depends(get_current_user)):
    return success(svc.proposal_stats())


@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    return success(svc.get_proposal_detail(pid))


@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(get_current_user)):
    return success(svc.review_proposal(pid, body.action, body.comment), message="已批阅")


@router.post("/proposals/{pid}/defense", summary="开题答辩（现场·PASS/FAIL，须书面已通过）")
def proposal_defense(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.hold_proposal_defense(pid, str(body.get("result") or "").upper(), body.get("comment")),
                   message="已录入开题答辩")


@router.get("/finals/stats", summary="成果统计（状态分布+查重超标）")
def final_stats(user=Depends(get_current_user)):
    return success(svc.final_stats())


@router.post("/proposals/remind", summary="开题催交（未提交学生留痕催办）")
def proposal_remind(body: RemindBody, user=Depends(get_current_user)):
    return success(svc.remind_proposal(body.gdStudentId, body.channel or "站内消息"), message="已催交")


@router.post("/proposals/export", summary="导出开题材料台账 Excel（写审计）")
def proposal_export(status: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_proposals_xlsx(status=status)
    audit_log.record("导出开题材料台账", "graduation-proposal:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/finals", summary="成果提交列表")
def finals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           user=Depends(get_current_user)):
    i, t = svc.list_finals(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.post("/finals/{fid}/review", summary="批阅成果（退回原因≥5字；查重超标 GD-R09 不可直接通过）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    return success(svc.review_final(fid, body.action, body.comment), message="已批阅")


@router.post("/finals/remind", summary="成果催交（未提交学生留痕催办）")
def final_remind(body: RemindBody, user=Depends(get_current_user)):
    return success(svc.remind_final(body.gdStudentId, body.channel or "站内消息"), message="已催交")


@router.post("/finals/export", summary="导出成果提交台账 Excel（写审计）")
def final_export(status: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_finals_xlsx(status=status)
    audit_log.record("导出成果提交台账", "graduation-final:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/defense-groups", summary="答辩安排列表")
def defense_groups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_defense_groups(page, pageSize, keyword=keyword)
    return _p(i, t, page, pageSize)


@router.post("/defense-groups", summary="新建答辩组")
def defense_create(body: DefenseGroupBody, user=Depends(get_current_user)):
    return success(svc.create_defense_group(body.groupName, body.defenseDate, body.location,
                   body.chair, body.members, body.secretary), message="已创建")


@router.get("/defense-groups/eligible-students", summary="可分配到答辩组的学生")
def defense_eligible(gid: Optional[str] = None, keyword: Optional[str] = None,
                     user=Depends(get_current_user)):
    return success({"items": svc.list_defense_eligible_students(gid=gid, keyword=keyword)})


@router.get("/defense-groups/{gid}", summary="答辩组详情（含已分配学生）")
def defense_detail(gid: str, user=Depends(get_current_user)):
    return success(svc.get_defense_group_detail(gid))


@router.put("/defense-groups/{gid}", summary="编辑答辩组（编辑后撤回发布，需重新发布）")
def defense_update(gid: str, body: DefenseGroupBody, user=Depends(get_current_user)):
    return success(svc.update_defense_group(gid, body.groupName, body.defenseDate, body.location,
                   body.chair, body.members, body.secretary), message="已保存")


@router.post("/defense-groups/{gid}/assign", summary="分配学生进答辩组（≤30人，评委回避自动检测）")
def defense_assign(gid: str, body: AssignStudentsBody, user=Depends(get_current_user)):
    return success(svc.assign_defense_students(gid, body.studentIds), message="已分配")


@router.post("/defense-groups/{gid}/unassign", summary="移出答辩组学生")
def defense_unassign(gid: str, body: AssignStudentsBody, user=Depends(get_current_user)):
    return success(svc.unassign_defense_students(gid, body.studentIds), message="已移出")


@router.post("/defense-groups/{gid}/publish", summary="发布答辩安排（冲突/未安排完整/无学生则拒绝）")
def defense_publish(gid: str, user=Depends(get_current_user)):
    return success(svc.publish_defense(gid), message="已发布")


@router.post("/defense-groups/export", summary="导出答辩安排台账 Excel（写审计）")
def defense_export(user=Depends(get_current_user)):
    data = svc.export_defense_xlsx()
    audit_log.record("导出答辩安排台账", "graduation-defense:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/audit-logs", summary="毕设域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)

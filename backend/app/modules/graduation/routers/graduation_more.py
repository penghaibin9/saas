"""毕业设计中心 · Batch 7/8：成果互查整改 / 答辩专家库 / 成绩更正申诉 API。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log
from app.modules.graduation.services import graduation_more_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-互查/专家/申诉"])


# ── 成果互查整改 ──
@router.get("/gd-peer-reviews", summary="互查记录列表")
def peer_list(gdStudentId: Optional[str] = None, status: Optional[str] = None, user=Depends(get_current_user)):
    return success({"items": svc.list_peer(gd_student_id=gdStudentId, status=status)})


@router.get("/gd-peer-reviews/stats", summary="互查统计")
def peer_stats(user=Depends(get_current_user)):
    return success(svc.peer_stats())


@router.post("/gd-peer-reviews/assign", summary="分配互查（互查学生≠本人）")
def peer_assign(body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.assign_peer(body.get("gdStudentId"), body.get("reviewerGdStudentId"))
    audit_log.record("分配成果互查", f"graduation-peer:{result['id']}")
    return success(result, message="已分配互查")


@router.post("/gd-peer-reviews/{pid}/submit", summary="提交互查意见（≥5字）")
def peer_submit(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.submit_peer(pid, body.get("opinion")), message="已提交互查")


@router.post("/gd-peer-reviews/{pid}/rectify", summary="被评学生提交整改（≥5字）")
def peer_rectify(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.rectify_peer(pid, body.get("note")), message="已提交整改")


# ── 答辩专家库 ──
@router.get("/gd-defense-experts", summary="答辩专家列表")
def expert_list(status: Optional[str] = None, keyword: Optional[str] = None, user=Depends(get_current_user)):
    return success({"items": svc.list_experts(status=status, keyword=keyword)})


@router.post("/gd-defense-experts", summary="新增答辩专家")
def expert_create(body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.create_expert(body.get("expertName"), body.get("title"), body.get("collegeName"),
                               body.get("isExternal"), body.get("avoidNote"))
    audit_log.record("新增答辩专家", f"graduation-expert:{result['id']}")
    return success(result, message="已新增")


@router.post("/gd-defense-experts/{eid}/status", summary="启用/停用答辩专家")
def expert_status(eid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.set_expert_status(eid, str(body.get("action") or "").upper()), message="已更新")


# ── 成绩更正申诉 ──
@router.get("/gd-grade-appeals", summary="成绩申诉列表")
def appeal_list(status: Optional[str] = None, user=Depends(get_current_user)):
    return success({"items": svc.list_appeals(status=status)})


@router.post("/gd-grade-appeals/{aid}/review", summary="复核申诉（受理→撤回成绩重核 / 驳回≥5字）")
def appeal_review(aid: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.review_appeal(aid, str(body.get("action") or "").upper(), body.get("comment"))
    audit_log.record("复核成绩申诉", f"graduation-grade-appeal:{aid}", detail={"action": body.get("action")})
    return success(result, message="已复核")


# ── 答辩通知（对已发布答辩组批量通知，留痕） ──
@router.post("/gd-defense-notify", summary="答辩通知（对已发布答辩组学生发送通知，留痕）")
def defense_notify(body: dict = Body(...), user=Depends(get_current_user)):
    from app.modules.graduation.services import graduation_service as gd_svc
    gid = body.get("defenseGroupId")
    detail = gd_svc.get_defense_group_detail(gid)
    if not detail.get("published"):
        return success({"notified": 0}, message="该答辩组未发布，暂不能通知")
    count = len(detail.get("students") or [])
    audit_log.record("发送答辩通知", f"graduation-defense-notify:{gid}", detail={"count": count})
    return success({"notified": count, "groupName": detail.get("groupName")},
                   message=f"已向 {count} 名学生发送答辩通知")

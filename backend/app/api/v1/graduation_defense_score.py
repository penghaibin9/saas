"""毕业设计中心 · 答辩评分 API（/api/v1/graduation/gd-defense-scores/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation_defense_score import DefenseScoreEntryRequest, SecondDefenseRequest
from app.services import audit_log
from app.services import graduation_defense_score_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-答辩评分"])


@router.get("/gd-defense-scores/stats", summary="答辩评分统计")
def gd_defense_score_stats(user=Depends(get_current_user)):
    return success(svc.defense_score_stats())


@router.get("/gd-defense-scores", summary="答辩评分列表")
def gd_defense_score_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                          gdStudentId: Optional[str] = None, judgeName: Optional[str] = None,
                          roundNo: Optional[int] = None, user=Depends(get_current_user)):
    items, total = svc.list_scores(page, pageSize, gd_student_id=gdStudentId, judge_name=judgeName,
                                   round_no=roundNo)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-defense-scores/entry", summary="录入/更新评委评分（缺席须填原因）")
def gd_defense_score_entry(body: DefenseScoreEntryRequest, user=Depends(get_current_user)):
    result = svc.enter_score(body.gdStudentId, body.judgeName, body.score, body.comment, body.absent,
                             body.absentReason)
    audit_log.record("录入答辩评分", f"graduation-defense-score:{result['id']}")
    return success(result, message="已保存")


@router.post("/gd-defense-scores/{gd_student_id}/confirm", summary="确认该生本轮答辩成绩（须全部评委已评分）")
def gd_defense_score_confirm(gd_student_id: str, user=Depends(get_current_user)):
    result = svc.confirm_scores(gd_student_id)
    audit_log.record("确认答辩成绩", f"graduation-defense-score:{gd_student_id}")
    return success(result, message="已确认")


@router.post("/gd-defense-scores/{gd_student_id}/second-defense", summary="创建二次答辩（原因≥5字）")
def gd_defense_score_second(gd_student_id: str, body: SecondDefenseRequest, user=Depends(get_current_user)):
    result = svc.create_second_defense(gd_student_id, body.reason)
    audit_log.record("创建二次答辩", f"graduation-defense-score:{gd_student_id}", detail={"reason": body.reason})
    return success(result, message="已创建二次答辩")

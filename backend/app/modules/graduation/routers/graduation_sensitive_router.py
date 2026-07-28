"""毕业设计敏感接口的批次强校验与关键审计单入口。

本 Router 在旧 Router 之前注册：相同路径优先命中这里，要求学校端明确 batchId，
并避免业务 Service 已写域审计后 Router 再补一条 fire-and-forget 审计。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.models import (
    GraduationPlagiarismCheck,
    GraduationReview,
    GraduationStudent,
)
from app.modules.graduation.schemas.graduation_defense_score import (
    DefenseAbsenceRequest,
    DefenseConfirmationRevokeRequest,
    DefenseScoreEntryRequest,
    SecondDefenseRequest,
)
from app.modules.graduation.schemas.graduation_grade import (
    GradeCalculateRequest,
    GradeReviewRequest,
    GradeWithdrawRequest,
)
from app.modules.graduation.schemas.graduation_review import (
    PlagiarismDisputeRequest,
    PlagiarismDisputeReview,
    PlagiarismResultRequest,
    PlagiarismSubmitRequest,
    ReviewAssignRequest,
    ReviewReturnRequest,
    ReviewSubmitRequest,
)
from app.schemas.excel import ExcelImportRows
from app.modules.graduation.services import (
    graduation_archive_service as archive,
    graduation_defense_score_service as defense,
    graduation_grade_service as grade,
    graduation_review_service as review,
    graduation_stats_service as stats,
    graduation_student_service as students,
)
from app.modules.graduation.services.graduation_batch_context import (
    assert_student_batch,
    load_student_in_batch,
    require_batch_id,
)
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session

router = APIRouter(prefix="/graduation", tags=["毕业设计-批次安全接口"])


def _student_batch(gd_student_id, batch_id, *, for_update: bool = False) -> int:
    with session() as db:
        student = load_student_in_batch(db, gd_student_id, batch_id, for_update=for_update)
        return int(student.id)


def _record_batch(model, record_id, batch_id, *, student_field: str = "gd_student_id") -> int:
    with session() as db:
        row = db.get(model, int(record_id))
        if not row or getattr(row, "is_deleted", False) or row.tenant_id != _tid():
            from app.core.exceptions import not_found
            raise not_found("业务记录不存在")
        student = db.get(GraduationStudent, int(getattr(row, student_field)))
        assert_student_batch(student, batch_id)
        return int(student.id)


# ── 学生与总统计：禁止遗漏 batchId 后统计全租户 ──
@router.get("/gd-students/stats", summary="毕设学生统计（当前批次）")
def gd_student_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    batch_id = require_batch_id(batchId)
    with session() as db:
        from sqlalchemy import func, select
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.batch_id == batch_id,
            GraduationStudent.id.in_(scope_ids or [-1]),
        ]
        total = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(*base)) or 0)
        by_stage = [{
            "stage": state, "label": students.STAGE_LABEL[state],
            "count": int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
                *base, GraduationStudent.stage == state,
            )) or 0),
        } for state in students.STAGE_ORDER if state != "ARCHIVED"]
        with_topic = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.topic_id.is_not(None),
        )) or 0)
        high_risk = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.risk_level == "HIGH",
        )) or 0)
        archived_count = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.stage == "ARCHIVED",
        )) or 0)
        return success({
            "batchId": str(batch_id), "total": total, "byStage": by_stage,
            "withTopic": with_topic, "withoutTopic": total - with_topic,
            "highRisk": high_risk, "archived": archived_count,
        })


@router.get("/gd-stats/overview", summary="毕设总览统计（当前批次）")
def gd_stats_overview(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(stats.overview_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-stats/college-comparison", summary="学院对比统计（当前批次）")
def gd_stats_college(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(stats.college_comparison(batch_id=require_batch_id(batchId)))


# ── 查重 ──
@router.get("/gd-plagiarism/stats")
def plagiarism_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(review.plagiarism_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-plagiarism")
def plagiarism_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    gdStudentId: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    if gdStudentId:
        _student_batch(gdStudentId, batchId)
    items, total = review.list_plagiarism(
        page, pageSize, gd_student_id=gdStudentId, status=status, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-plagiarism/{gd_student_id}/submit")
def plagiarism_submit(
    gd_student_id: str, body: PlagiarismSubmitRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(review.submit_plagiarism(gd_student_id, body.gdFinalId), message="已提交检测")


@router.post("/gd-plagiarism/{pid}/result")
def plagiarism_result(
    pid: str, body: PlagiarismResultRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_batch(GraduationPlagiarismCheck, pid, batchId)
    return success(review.set_plagiarism_result(pid, body.rate, body.reportUrl), message="已回填")


@router.post("/gd-plagiarism/{pid}/dispute")
def plagiarism_dispute(
    pid: str, body: PlagiarismDisputeRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_batch(GraduationPlagiarismCheck, pid, batchId)
    return success(review.dispute_plagiarism(pid, body.reason), message="已提交复查申请")


@router.post("/gd-plagiarism/{pid}/dispute/review")
def plagiarism_dispute_review(
    pid: str, body: PlagiarismDisputeReview,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _record_batch(GraduationPlagiarismCheck, pid, batchId)
    return success(review.review_dispute(pid, body.action, body.comment), message="已审核")


# ── 评阅 ──
@router.get("/gd-reviews/stats")
def review_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(review.review_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-reviews")
def review_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    gdStudentId: Optional[str] = None, reviewerName: Optional[str] = None,
    status: Optional[str] = None, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    if gdStudentId:
        _student_batch(gdStudentId, batchId)
    items, total = review.list_reviews(
        page, pageSize, gd_student_id=gdStudentId, reviewer_name=reviewerName,
        status=status, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-reviews/assign")
def review_assign(
    body: ReviewAssignRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(body.gdStudentId, batchId, for_update=True)
    return success(review.assign_review(
        body.gdStudentId, body.reviewerName, body.gdFinalId,
        reviewer_mentor_id=body.reviewerMentorId,
    ), message="已分配")


@router.post("/gd-reviews/{rid}/submit")
def review_submit(
    rid: str, body: ReviewSubmitRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_batch(GraduationReview, rid, batchId)
    return success(review.submit_review(rid, body.score, body.opinion), message="已提交")


@router.post("/gd-reviews/{rid}/return")
def review_return(
    rid: str, body: ReviewReturnRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _record_batch(GraduationReview, rid, batchId)
    return success(review.return_review(rid, body.reason), message="已退回")


# ── 答辩评分 ──
@router.get("/gd-defense-scores/stats")
def defense_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(defense.defense_score_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-defense-scores")
def defense_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    gdStudentId: Optional[str] = None, judgeName: Optional[str] = None,
    roundNo: Optional[int] = None, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    if gdStudentId:
        _student_batch(gdStudentId, batchId)
    items, total = defense.list_scores(
        page, pageSize, gd_student_id=gdStudentId, judge_name=judgeName,
        round_no=roundNo, batch_id=batchId,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-defense-scores/entry")
def defense_entry(
    body: DefenseScoreEntryRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(body.gdStudentId, batchId, for_update=True)
    return success(defense.enter_score(
        body.gdStudentId, body.judgeName, body.score, body.comment, body.absent,
        body.absentReason, expert_id=body.expertId, judge_mentor_id=body.judgeMentorId,
    ), message="已保存")


@router.post("/gd-defense-scores/absence")
def defense_absence(
    body: DefenseAbsenceRequest, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(body.gdStudentId, batchId, for_update=True)
    return success(defense.enter_score(
        body.gdStudentId, body.judgeName, score=None, absent=True,
        absent_reason=body.absentReason, expert_id=body.expertId,
        judge_mentor_id=body.judgeMentorId, permission_action="scoreConfirm",
    ), message="已记录缺席")


@router.post("/gd-defense-scores/{gd_student_id}/confirm")
def defense_confirm(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(defense.confirm_scores(gd_student_id), message="已确认")


@router.post("/gd-defense-scores/{gd_student_id}/revoke-confirmation")
def defense_revoke(
    gd_student_id: str, body: DefenseConfirmationRevokeRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(defense.revoke_confirmation(gd_student_id, body.reason), message="已撤回确认")


@router.post("/gd-defense-scores/{gd_student_id}/second-defense")
def defense_second(
    gd_student_id: str, body: SecondDefenseRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(defense.create_second_defense(gd_student_id, body.reason), message="已创建二次答辩")


# ── 成绩：GET 只读，所有写操作必须与页面批次一致 ──
@router.get("/gd-grades/stats")
def grade_stats(batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    return success(grade.grade_stats(batch_id=require_batch_id(batchId)))


@router.get("/gd-grades")
def grade_list(
    page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None, status: Optional[str] = None,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    items, total = grade.list_grades(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-grades/{gd_student_id}", summary="按学生只读查询成绩")
def grade_detail(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId)
    return success(grade.get_grade(gd_student_id))


@router.post("/gd-grades/{gd_student_id}/calculate")
def grade_calculate(
    gd_student_id: str, body: GradeCalculateRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(grade.calculate_grade(
        gd_student_id, body.advisorScore, body.reviewerScore, body.defenseScore,
    ), message="已核算")


@router.post("/gd-grades/{gd_student_id}/review")
def grade_review(
    gd_student_id: str, body: GradeReviewRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(grade.review_grade(gd_student_id, body.action, body.comment), message="已复核")


@router.post("/gd-grades/{gd_student_id}/publish")
def grade_publish(
    gd_student_id: str, batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(grade.publish_grade(gd_student_id), message="已发布")


@router.post("/gd-grades/{gd_student_id}/withdraw")
def grade_withdraw(
    gd_student_id: str, body: GradeWithdrawRequest,
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    _student_batch(gd_student_id, batchId, for_update=True)
    return success(grade.withdraw_grade(gd_student_id, body.reason), message="已撤回")


# ── 归档：真实文件哈希 + 预览令牌 ──
@router.post("/gd-archives/batch-generate/preview")
def archive_generate_preview(
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(archive.preview_batch_generate(batch_id=batchId))


@router.post("/gd-archives/batch-generate")
def archive_generate_batch(
    batchId: int = Query(..., ge=1), body: dict = Body(...),
    user=Depends(get_current_user),
):
    result = archive.batch_generate_submit(
        batch_id=batchId, preview_token=(body or {}).get("previewToken"),
    )
    return success(result, message=f"已提交 {result['submitted']}，跳过 {result['skipped']}")


@router.post("/gd-archives/batch-file/preview")
def archive_file_preview(
    batchId: int = Query(..., ge=1), user=Depends(get_current_user),
):
    return success(archive.preview_batch_file(batch_id=batchId))


@router.post("/gd-archives/batch-file")
def archive_file_batch(
    batchId: int = Query(..., ge=1), body: dict = Body(...),
    user=Depends(get_current_user),
):
    result = archive.batch_file(
        (body or {}).get("archiveBatchNo"), batch_id=batchId,
        preview_token=(body or {}).get("previewToken"),
    )
    return success(result, message=f"已备案 {result['filed']} 份")


# ── 毕设学生导入确认：权限/令牌/业务写入/作业证据均由同一事务完成，不再补写泛化审计 ──
@router.post("/gd-students/import/confirm")
def student_import_confirm(body: ExcelImportRows, user=Depends(get_current_user)):
    result = students.import_confirm(body.rows, body.previewToken)
    return success(result, message="导入完成")

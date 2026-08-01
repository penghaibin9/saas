"""毕业设计域 API（/api/v1/graduation/*）。真实走库；批阅/发布落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.core.permissions import has_permission, require_permission
from app.modules.graduation.schemas.graduation import (AssignStudentsBody, DefenseGroupBody,  # noqa: F401
                                    ProposalSubmitBody, RemindBody, ReviewBody)
from app.services import audit_log
from app.modules.graduation.services import graduation_service as svc
from app.modules.graduation.services.graduation_scope_service import has_full_scope, org_scope_status

router = APIRouter(prefix="/graduation", tags=["毕业设计"])

# 前端按钮动作 → 后端真实 permissionCode（与 graduation_permissions.graduation_permission_for
# 的路径推导口径保持一致）。/context 把这份判定结果下发给前端，替代此前写死的静态权限矩阵。
_ACTION_PERMISSION_MAP = {
    "createBatch": "graduationDesign.batch.create",
    "importStudents": "graduationDesign.student.import",
    "exportStats": "graduationDesign.dashboard.view",
    "viewAuditLog": "graduationDesign.audit.view",
    "createProject": "graduationDesign.batch.create",
    "batchAssignAdvisor": "graduationDesign.student.manage",
    "batchRemind": "graduationDesign.proposal.remind",
    "batchArchive": "graduationDesign.archive.file",
    "editProject": "graduationDesign.batch.update",
    "voidProject": "graduationDesign.batch.close",
    "createTopic": "graduationDesign.topic.create",
    "importTopics": "graduationDesign.topic.create",
    "exportTopics": "graduationDesign.topic.export",
    "disableTopic": "graduationDesign.topic.review",
    "reviewProposal": "graduationDesign.proposal.review", "reviewFinal": "graduationDesign.final.review",
    "exportProposals": "graduationDesign.proposal.export",
    "manageDefense": "graduationDesign.defense.groupManage",
    "publishDefense": "graduationDesign.defense.publish",
    "exportDefense": "graduationDesign.defense.view",
    "exportTaskbookPdf": "graduationDesign.taskbook.export",
    "guideMidterm": "graduationDesign.midterm.review",
    "guideTaskbook": "graduationDesign.taskbook.update",
    "guideStudentEval": "graduationDesign.guidance.update",
    "guidePlanCheckin": "graduationDesign.guidance.create",
    "enterDefenseScore": "graduationDesign.defense.score",
    "submitPlagiarism": "graduationDesign.plagiarism.start",
    "setPlagiarismResult": "graduationDesign.plagiarism.result",
    "reviewPlagiarismDispute": "graduationDesign.plagiarism.disputeReview",
    "assignReview": "graduationDesign.review.assign",
    "submitReview": "graduationDesign.review.submit",
    "returnReview": "graduationDesign.review.return",
    "confirmDefenseScores": "graduationDesign.defense.scoreConfirm",
    "createSecondDefense": "graduationDesign.defense.secondRound",
    "manageGrade": "graduationDesign.grade.calculate",
    "reviewGrade": "graduationDesign.grade.review",
    "withdrawGrade": "graduationDesign.grade.withdraw",
    "reviewGradeAppeal": "graduationDesign.grade.appealReview",
    "publishGrade": "graduationDesign.grade.publish",
}


@router.get("/context", summary="毕设中心真实权限/范围上下文（供前端按钮门禁，替代静态假数据）")
def get_context(user=Depends(get_current_user)):
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    org = org_scope_status(user)
    return success({
        "roleCode": role,
        "fullScope": has_full_scope(),
        "permissionActions": {key: has_permission(user, code)
                              for key, code in _ACTION_PERMISSION_MAP.items()},
        **org,
    })


@router.get("/materials/{file_id}/download", summary="下载毕业设计材料（业务关系鉴权）")
def download_graduation_material(file_id: str, user=Depends(get_current_user)):
    from fastapi.responses import FileResponse
    from app.core.exceptions import not_found

    resolved = svc.resolve_material_download(file_id)
    if not resolved:
        raise not_found("毕业设计材料不存在或无权访问")
    path, filename = resolved
    audit_log.record("GRADUATION_MATERIAL_DOWNLOAD", f"graduation-file:{file_id}")
    return FileResponse(str(path), filename=filename)


def _p(i, t, page, ps):
    return success(paginate(i, t, page, ps))


@router.get("/dashboard", summary="毕设看板")
def dashboard(batchId: int | None = Query(default=None, ge=1),
              user=Depends(get_current_user)):
    return success(svc.get_dashboard(batch_id=batchId))


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
              batchId: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_proposals(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return _p(i, t, page, pageSize)


@router.get("/proposals/stats", summary="开题统计（状态分布+未提交）")
def proposal_stats(batchId: int | None = Query(default=None, ge=1),
                   user=Depends(get_current_user)):
    return success(svc.proposal_stats(batch_id=batchId))


@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    from app.modules.graduation.services import graduation_material_center_service as material_center
    return success(material_center.proposal_detail(int(pid)))


@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(require_permission("graduationDesign.proposal.review"))):
    from app.modules.graduation.services import graduation_material_catalog_service as material_catalog
    from app.modules.graduation.services import graduation_material_center_service as material_center
    result = material_center.review_proposal(int(pid), body.action, body.comment, user)
    material_catalog.sync_record("PROPOSAL", int(pid), user)
    return success(result, message="已批阅")


@router.post("/proposals/{pid}/defense", summary="开题答辩（现场·PASS/FAIL，须书面已通过）")
def proposal_defense(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.hold_proposal_defense(pid, str(body.get("result") or "").upper(), body.get("comment")),
                   message="已录入开题答辩")


@router.get("/finals/stats", summary="成果统计（状态分布+查重超标）")
def final_stats(batchId: int | None = Query(default=None, ge=1),
                user=Depends(get_current_user)):
    return success(svc.final_stats(batch_id=batchId))


@router.post("/proposals/remind", summary="开题催交（未提交学生留痕催办）")
def proposal_remind(body: RemindBody, user=Depends(get_current_user)):
    return success(svc.remind_proposal(body.gdStudentId, body.channel or "站内消息"), message="已催交")


@router.post("/proposals/export", summary="导出开题材料台账 Excel（写审计）")
def proposal_export(status: Optional[str] = None, keyword: Optional[str] = None,
                    batchId: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_proposals_xlsx(status=status, keyword=keyword, batch_id=batchId)
    audit_log.record("导出开题材料台账", "graduation-proposal:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId, "status": status})
    return success(data)


@router.get("/finals", summary="成果提交列表")
def finals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           batchId: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_finals(page, pageSize, keyword=keyword, status=status, batch_id=batchId)
    return _p(i, t, page, pageSize)


@router.post("/finals/{fid}/review", summary="批阅成果（退回原因≥5字；查重超标 GD-R09 不可直接通过）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    from app.modules.graduation.services import graduation_material_catalog_service as material_catalog
    from app.modules.graduation.services import graduation_material_center_service as material_center
    result = material_center.review_final(int(fid), body.action, body.comment, user)
    material_catalog.sync_record("FINAL", int(fid), user)
    return success(result, message="已批阅")


@router.post("/finals/remind", summary="成果催交（未提交学生留痕催办）")
def final_remind(body: RemindBody, user=Depends(get_current_user)):
    return success(svc.remind_final(body.gdStudentId, body.channel or "站内消息"), message="已催交")


@router.post("/finals/export", summary="导出成果提交台账 Excel（写审计）")
def final_export(status: Optional[str] = None, keyword: Optional[str] = None,
                 batchId: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_finals_xlsx(status=status, keyword=keyword, batch_id=batchId)
    audit_log.record("导出成果提交台账", "graduation-final:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId, "status": status})
    return success(data)


@router.get("/defense-groups", summary="答辩安排列表")
def defense_groups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None,
                   batchId: int | None = Query(default=None, ge=1),
                   user=Depends(get_current_user)):
    i, t = svc.list_defense_groups(page, pageSize, keyword=keyword, batch_id=batchId)
    return _p(i, t, page, pageSize)


@router.post("/defense-groups", summary="新建答辩组")
def defense_create(body: DefenseGroupBody, user=Depends(get_current_user)):
    result = svc.create_defense_group(
        body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary, batch_id=body.batchId,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds)
    return success(_defense_member_contract(result), message="已创建")


@router.get("/defense-groups/eligible-students", summary="可分配到答辩组的学生")
def defense_eligible(gid: Optional[str] = None, keyword: Optional[str] = None,
                     user=Depends(get_current_user)):
    return success({"items": svc.list_defense_eligible_students(gid=gid, keyword=keyword)})


def _defense_member_contract(result: dict) -> dict:
    row = dict(result or {})
    row["memberDetails"] = list(row.get("memberDetails") or row.get("members") or [])
    return row


@router.get("/defense-groups/{gid}", summary="答辩组详情（含已分配学生）")
def defense_detail(gid: str, user=Depends(get_current_user)):
    return success(_defense_member_contract(svc.get_defense_group_detail(gid)))


@router.put("/defense-groups/{gid}", summary="编辑答辩组（编辑后撤回发布，需重新发布）")
def defense_update(gid: str, body: DefenseGroupBody, user=Depends(get_current_user)):
    result = svc.update_defense_group(
        gid, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds)
    return success(_defense_member_contract(result), message="已保存")


@router.post("/defense-groups/{gid}/assign", summary="分配学生进答辩组（≤30人，评委回避自动检测）")
def defense_assign(gid: str, body: AssignStudentsBody, user=Depends(get_current_user)):
    return success(svc.assign_defense_students(gid, body.studentIds), message="已分配")


@router.post("/defense-groups/{gid}/unassign", summary="移出答辩组学生")
def defense_unassign(gid: str, body: AssignStudentsBody, user=Depends(get_current_user)):
    return success(svc.unassign_defense_students(gid, body.studentIds), message="已移出")


@router.post("/defense-groups/{gid}/publish", summary="发布答辩安排（冲突/未安排完整/无学生则拒绝）")
def defense_publish(gid: str, user=Depends(require_permission("graduationDesign.defense.publish"))):
    return success(svc.publish_defense(gid), message="已发布")


@router.post("/defense-groups/export", summary="导出答辩安排台账 Excel（写审计）")
def defense_export(batchId: int | None = Query(default=None, ge=1),
                   user=Depends(get_current_user)):
    data = svc.export_defense_xlsx(batch_id=batchId)
    audit_log.record("导出答辩安排台账", "graduation-defense:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId})
    return success(data)


@router.get("/audit-logs", summary="毕设域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)

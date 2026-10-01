"""毕业设计域 API（/api/v1/graduation/*）。真实走库；批阅/发布落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.exceptions import no_permission
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.core.permissions import permission_decisions, require_permission
from app.modules.graduation.schemas.graduation import (AssignStudentsBody, DefenseGroupBody,  # noqa: F401
                                    ProposalSubmitBody, RemindBody, ReviewBody)
from app.modules.graduation.materials import record_service as material_records
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
    "enterAdvisorScore": "graduationDesign.grade.advisorScore",
    "reviewGradeAppeal": "graduationDesign.grade.appealReview",
    "publishGrade": "graduationDesign.grade.publish",
}


@router.get("/context", summary="毕设中心真实权限/范围上下文（供前端按钮门禁，替代静态假数据）")
def get_context(user=Depends(get_current_user)):
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    org = org_scope_status(user)
    decisions = permission_decisions(user, _ACTION_PERMISSION_MAP.values())
    return success({
        "roleCode": role,
        "fullScope": has_full_scope(),
        "permissionActions": {key: decisions[code] for key, code in _ACTION_PERMISSION_MAP.items()},
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


def _require_full_defense_group_scope() -> None:
    """Empty/new defense groups have no student relation, so only full-scope managers may mutate membership."""
    if not has_full_scope():
        raise no_permission("Only full-scope graduation managers can create or reassign defense groups")


@router.get("/students/{sid}", summary="毕设学生详情")
def student_detail(sid: str, user=Depends(get_current_user)):
    return success(svc.get_student_detail(sid))


@router.get("/topics", summary="选题列表")
def topics(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           user=Depends(get_current_user)):
    i, t = svc.list_topics(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    return success(material_records.proposal_detail(int(pid), user))


@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(require_permission("graduationDesign.proposal.review"))):
    result = material_records.review_proposal(
        int(pid), body.action, body.comment, user,
        expected_version=body.expectedVersion, expected_file_version_id=body.fileVersionId,
    )
    return success(result, message="已批阅")


@router.post("/proposals/{pid}/defense", summary="开题答辩（现场·PASS/FAIL，须书面已通过）")
def proposal_defense(pid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.hold_proposal_defense(pid, str(body.get("result") or "").upper(), body.get("comment")),
                   message="已录入开题答辩")


@router.post("/finals/{fid}/review", summary="批阅成果（退回原因≥5字；查重超标 GD-R09 不可直接通过）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    result = material_records.review_final(
        int(fid), body.action, body.comment, user,
        expected_version=body.expectedVersion, expected_file_version_id=body.fileVersionId,
    )
    return success(result, message="已批阅")


def _defense_member_contract(result: dict) -> dict:
    row = dict(result or {})
    row["memberDetails"] = list(row.get("memberDetails") or row.get("members") or [])
    return row


@router.get("/defense-groups/{gid}", summary="答辩组详情（含已分配学生）")
def defense_detail(gid: str, user=Depends(get_current_user)):
    return success(_defense_member_contract(svc.get_defense_group_detail(gid)))


@router.put("/defense-groups/{gid}", summary="编辑答辩组（编辑后撤回发布，需重新发布）")
def defense_update(gid: str, body: DefenseGroupBody, user=Depends(require_permission("graduationDesign.defense.groupManage"))):
    svc.get_defense_group_detail(gid)  # data-scope guard before mutation
    result = svc.update_defense_group(
        gid, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds)
    return success(_defense_member_contract(result), message="已保存")


@router.post("/defense-groups/{gid}/assign", summary="分配学生进答辩组（≤30人，评委回避自动检测）")
def defense_assign(gid: str, body: AssignStudentsBody, user=Depends(require_permission("graduationDesign.defense.groupManage"))):
    _require_full_defense_group_scope()
    return success(svc.assign_defense_students(gid, body.studentIds), message="已分配")


@router.post("/defense-groups/{gid}/unassign", summary="移出答辩组学生")
def defense_unassign(gid: str, body: AssignStudentsBody, user=Depends(require_permission("graduationDesign.defense.groupManage"))):
    _require_full_defense_group_scope()
    return success(svc.unassign_defense_students(gid, body.studentIds), message="已移出")


@router.post("/defense-groups/{gid}/publish", summary="发布答辩安排（冲突/未安排完整/无学生则拒绝）")
def defense_publish(gid: str, user=Depends(require_permission("graduationDesign.defense.publish"))):
    svc.get_defense_group_detail(gid)  # data-scope guard before mutation
    return success(svc.publish_defense(gid), message="已发布")



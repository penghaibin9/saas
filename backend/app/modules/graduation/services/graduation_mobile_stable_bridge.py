"""教师微信小程序毕业设计稳定身份桥接。

旧聚合 Service 曾在接口权限通过后再次用 advisor_name/reviewer_name 与 realName
做范围过滤，导致同名越权、改名后待办消失。这里在路由注册时替换这些函数，
统一使用 mentor_id/reviewer_mentor_id/答辩席位 stable id。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    GraduationAuditTrail,
    GraduationDefenseGroup,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTopic,
    GraduationTopicChangeRequest,
)
from app.modules.graduation.services.graduation_scope_service import (
    accessible_student_ids,
    assert_student_access,
    has_full_scope,
)
from app.services.db_service import _tid, session

_INSTALLED = False
_ADMIN_ROLES = {
    "PLATFORM_SUPER_ADMIN", "SAAS_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN",
    "GD_ADMIN", "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN", "COLLEGE_ADMIN", "GD_GRADE_ADMIN",
}


def _role(user: dict) -> str:
    return str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()


def _mentor(db):
    from app.modules.graduation.services import graduation_identity as gid
    return gid.current_user_mentor(db)


def _require_mentor(db, user: dict):
    mentor = _mentor(db)
    if mentor is None and _role(user) not in _ADMIN_ROLES:
        raise no_permission("当前账号未按工号绑定毕设导师台账")
    return mentor


def _student(db, gd_student_id, user: dict) -> GraduationStudent:
    student = db.get(GraduationStudent, int(gd_student_id))
    if not student or student.is_deleted or student.tenant_id != _tid():
        raise not_found("毕设学生不存在")
    return assert_student_access(db, student, "mobile.graduation")


def _my_students(user: dict) -> list:
    with session() as db:
        mentor = _require_mentor(db, user)
        query = select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        )
        if _role(user) not in _ADMIN_ROLES:
            query = query.where(GraduationStudent.mentor_id == mentor.id)
        rows = db.scalars(query.order_by(GraduationStudent.id.desc())).all()
        return [{
            "gdStudentId": str(row.id), "name": row.name,
            "studentNo": row.student_no or "", "className": row.class_name or "",
            "stage": row.stage, "topicTitle": row.topic_title or "（未选题）",
            "mentorId": str(row.mentor_id) if row.mentor_id else None,
            "batchId": str(row.batch_id) if row.batch_id else None,
        } for row in rows]


def _guidance_create(user: dict, gd_student_id: str, body: dict) -> dict:
    with session() as db:
        _student(db, gd_student_id, user)
    from app.modules.graduation.services import graduation_guidance_service as svc
    return svc.create_guidance(gd_student_id, body or {})


def _require_student_scope(user: dict, scope: dict, gd_student_id) -> dict:
    with session() as db:
        student = _student(db, gd_student_id, user)
        return {
            "id": student.id, "name": student.name, "className": student.class_name or "",
            "studentNo": student.student_no or "", "advisorName": student.advisor_name or "",
            "mentorId": str(student.mentor_id) if student.mentor_id else None,
            "batchId": str(student.batch_id) if student.batch_id else None,
        }


def _material_student(db, model, record_id, user: dict) -> GraduationStudent:
    row = db.get(model, int(record_id))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("毕业设计材料不存在")
    return _student(db, row.gd_student_id, user)


def _proposal_detail(user: dict, proposal_id: str) -> dict:
    with session() as db:
        _material_student(db, GraduationProposal, proposal_id, user)
    from app.modules.graduation.services import graduation_service as svc
    detail = svc.get_proposal_detail(proposal_id)
    content = detail.get("content") or {}
    return {
        "id": str(detail.get("id") or proposal_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "version": detail.get("version") or "", "isResubmit": bool(detail.get("isResubmit")),
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "background": content.get("background") or "",
        "plan": content.get("plan") or "", "outcome": content.get("outcome") or "",
        "reviewComment": detail.get("reviewComment") or "",
        "attachments": int(detail.get("attachments") or 0),
        "attachmentsList": detail.get("attachmentsList") or [], "versions": detail.get("versions") or [],
    }


def _proposal_review(user: dict, proposal_id: str, action: str, comment: str | None = None) -> dict:
    with session() as db:
        _material_student(db, GraduationProposal, proposal_id, user)
    from app.modules.graduation.services import graduation_service as svc
    return svc.review_proposal(proposal_id, action, comment)


def _final_detail(user: dict, final_id: str) -> dict:
    with session() as db:
        _material_student(db, GraduationFinal, final_id, user)
    from app.modules.graduation.services import graduation_service as svc
    detail = svc.get_final_detail(final_id)
    return {
        "id": str(detail.get("id") or final_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "type": detail.get("type") or "", "version": detail.get("version") or "",
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "plagiarismRate": detail.get("plagiarismRate") or "—",
        "plagiarismStatus": detail.get("plagiarismStatus") or "未检测",
        "plagiarismTone": detail.get("plagiarismTone") or "success",
        "reviewComment": detail.get("reviewComment") or "",
        "attachmentsList": detail.get("attachmentsList") or [], "versions": detail.get("versions") or [],
    }


def _final_review(user: dict, final_id: str, action: str, comment: str | None = None) -> dict:
    with session() as db:
        _material_student(db, GraduationFinal, final_id, user)
    from app.modules.graduation.services import graduation_service as svc
    return svc.review_final(final_id, action, comment)


def _choices_pending(user: dict) -> list:
    with session() as db:
        mentor = _require_mentor(db, user)
    from app.modules.graduation.services import graduation_topic_round_service as svc
    # Service internally resolves the current mentor again and filters advisor_mentor_id.
    return svc.list_pending_choices_for_advisor(mentor.teacher_name if mentor else "")


def _choice_review(user: dict, choice_id: str, action: str, reason: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_topic_round_service as svc
    svc.get_choice_detail(choice_id)  # stable topic advisor relationship is enforced inside.
    action = str(action or "").upper()
    if action == "CONFIRM":
        return svc.confirm_choice(choice_id, operator_name=user.get("realName") or user.get("loginName") or "教师")
    if action == "REJECT":
        return svc.reject_choice(choice_id, reason or "", operator_name=user.get("realName") or user.get("loginName") or "教师")
    raise AppException("VALIDATION_ERROR", "action 必须是 CONFIRM/REJECT")


def _topic_change_rows(user: dict) -> list:
    from app.modules.graduation.services import graduation_topic_change_service as svc
    with session() as db:
        mentor = _require_mentor(db, user)
        rows = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.is_deleted.is_(False),
            GraduationTopicChangeRequest.status == "PENDING",
        ).order_by(GraduationTopicChangeRequest.id.desc())).all()
        if _role(user) in _ADMIN_ROLES:
            return [svc._row_of(db, row) for row in rows]
        topic_ids = {row.old_topic_id for row in rows} | {row.new_topic_id for row in rows}
        owned = {topic.id for topic in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(),
            GraduationTopic.id.in_(topic_ids or [-1]),
            GraduationTopic.advisor_mentor_id == mentor.id,
            GraduationTopic.is_deleted.is_(False),
        )).all()}
        return [svc._row_of(db, row) for row in rows if row.old_topic_id in owned or row.new_topic_id in owned]


def _topic_change_review(user: dict, request_id: str, action: str, comment: str | None = None) -> dict:
    with session() as db:
        mentor = _require_mentor(db, user)
        row = db.get(GraduationTopicChangeRequest, int(request_id))
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("变更申请不存在")
        if _role(user) not in _ADMIN_ROLES:
            old_topic = db.get(GraduationTopic, row.old_topic_id)
            new_topic = db.get(GraduationTopic, row.new_topic_id)
            owner_ids = {
                int(topic.advisor_mentor_id) for topic in (old_topic, new_topic)
                if topic and topic.advisor_mentor_id
            }
            if int(mentor.id) not in owner_ids:
                raise no_permission("该变更申请不属于当前导师")
    from app.modules.graduation.services import graduation_topic_change_service as svc
    return svc.review_change(
        request_id, action, comment or "",
        reviewer_name=user.get("realName") or user.get("loginName") or "教师",
    )


def _review_tasks(user: dict) -> list:
    from app.modules.graduation.services import graduation_review_service as svc
    with session() as db:
        mentor = _require_mentor(db, user)
        query = select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(), GraduationReview.is_deleted.is_(False),
            GraduationReview.status.in_(("ASSIGNED", "REVIEWING", "RETURNED")),
        )
        if _role(user) not in _ADMIN_ROLES:
            query = query.where(GraduationReview.reviewer_mentor_id == mentor.id)
        rows = db.scalars(query.order_by(GraduationReview.id.desc())).all()
        return [svc._review_row(row, db.get(GraduationStudent, row.gd_student_id)) for row in rows]


def _review_submit(user: dict, review_id: str, score, opinion: str | None = None) -> dict:
    try:
        value = int(score)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "评分必须是 0-100 的整数") from None
    if value < 0 or value > 100:
        raise AppException("VALIDATION_ERROR", "评分必须在 0-100 之间")
    if not opinion or len(str(opinion).strip()) < 5:
        raise AppException("VALIDATION_ERROR", "评阅意见必填且不少于 5 字")
    from app.modules.graduation.services import graduation_review_service as svc
    return svc.submit_review(review_id, value, str(opinion).strip())


def _stable_judge_pending() -> list[dict]:
    from app.modules.graduation.services import graduation_defense_score_service as svc
    from app.modules.graduation.services import graduation_identity as gid
    user = get_current_user_ctx() or {}
    with session() as db:
        mentor = gid.current_user_mentor(db)
        expert_id = user.get("expertId")
        if mentor is None and expert_id in (None, ""):
            raise no_permission("当前账号未绑定稳定答辩评委身份")
        scope_ids = accessible_student_ids(db, _tid())
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id.in_(scope_ids or [-1]),
            GraduationStudent.defense_group_id.is_not(None),
            GraduationStudent.is_deleted.is_(False),
        )).all()
        result = []
        for student in students:
            group = db.get(GraduationDefenseGroup, student.defense_group_id)
            if not group or group.is_deleted or not group.published:
                continue
            seats = gid.judge_panel_seats(group)
            seat = next((item for item in seats if gid.user_matches_judge_seat(
                item, mentor=mentor, expert_id=expert_id,
            )), None)
            if not seat:
                continue
            round_no = svc._active_round_no(db, student.id)
            identity = f"MENTOR:{mentor.id}" if mentor else f"EXPERT:{int(expert_id)}"
            mine = db.scalars(select(GraduationDefenseScore).where(
                GraduationDefenseScore.tenant_id == _tid(),
                GraduationDefenseScore.gd_student_id == student.id,
                GraduationDefenseScore.round_no == round_no,
                GraduationDefenseScore.judge_identity == identity,
                GraduationDefenseScore.is_deleted.is_(False),
            )).first()
            status = mine.status if mine else "PENDING"
            result.append({
                "gdStudentId": str(student.id), "studentName": student.name,
                "studentNo": student.student_no or "", "topicTitle": student.topic_title or "（未选题）",
                "groupName": group.group_name, "defenseDate": group.defense_date or "待定",
                "location": group.location or "待定", "roundNo": round_no,
                "myScoreId": str(mine.id) if mine else "", "myScore": mine.score if mine else None,
                "myAbsent": bool(mine.absent) if mine else False,
                "myComment": mine.comment if mine else "", "myStatus": status,
                "myStatusLabel": svc.STATUS_LABEL.get(status, "待评分"),
            })
        return result


def _stable_topic_audit(db, biz_id, action, detail=""):
    user = get_current_user_ctx() or {}
    operator = user.get("realName") or user.get("loginName")
    if not operator:
        raise AppException("AUDIT_CONTEXT_MISSING", "关键动作缺少操作者上下文")
    db.add(GraduationAuditTrail(
        tenant_id=_tid(), biz_type="TOPIC_CHANGE", biz_id=str(biz_id), action=action,
        operator=operator, role_name=user.get("currentRoleCode") or user.get("userType"),
        detail=detail, occurred_at=datetime.now(timezone.utc),
    ))


def install_mobile_stable_bridge() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from app.services import mobile_teacher_service as mobile
    from app.modules.graduation.services import graduation_defense_score_service as defense
    from app.modules.graduation.services import graduation_topic_change_service as changes

    mobile.graduation_my_students = _my_students
    mobile.graduation_guidance_create = _guidance_create
    mobile._require_gd_student_scope = _require_student_scope
    mobile.proposal_detail = _proposal_detail
    mobile.proposal_review = _proposal_review
    mobile.final_detail = _final_detail
    mobile.final_review = _final_review
    mobile.graduation_choices_pending = _choices_pending
    mobile.graduation_choice_review = _choice_review
    mobile.graduation_change_requests_pending = _topic_change_rows
    mobile.graduation_change_request_review = _topic_change_review
    mobile.graduation_my_reviews = _review_tasks
    mobile.graduation_review_submit = _review_submit
    defense.judge_pending = _stable_judge_pending
    changes._audit = _stable_topic_audit

"""Graduation topic P0/P1/P2 object-scope, review and pagination hardening."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, cast, func, or_, select, String

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    GraduationArchiveRecord, GraduationAuditTrail, GraduationBatch, GraduationGrade,
    GraduationGradeAppeal, GraduationGuidance, GraduationGuidancePlan, GraduationMentor,
    GraduationMentorAssignment, GraduationStudent, GraduationTaskBook, GraduationTopic,
)
from app.services.db_service import _iso, _tid, session

from app.modules.graduation.services.graduation_release_hardening_common import (
    _claim_ids, _ctx, _full_scope, _strict_dt, _student_scope_select,
)


def _topic_scope_select(db, *, for_review: bool = False):
    from app.modules.graduation.services import graduation_scope_service as scope
    from app.modules.graduation.services import graduation_identity as identity

    user, role = _ctx()
    q = select(GraduationTopic.id).where(
        GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False)
    )
    if role in scope.FULL_SCOPE_ROLES:
        return q
    if role == "GD_MENTOR":
        mentor = identity.current_user_mentor(db)
        if not mentor:
            return q.where(GraduationTopic.id == -1)
        if for_review:
            college_id = str(getattr(mentor, "college_id", None) or "").strip()
            if not college_id:
                return q.where(GraduationTopic.id == -1)
            return q.where(
                GraduationTopic.college_id == college_id,
                or_(GraduationTopic.advisor_mentor_id.is_(None),
                    GraduationTopic.advisor_mentor_id != int(mentor.id)),
            )
        return q.where(GraduationTopic.advisor_mentor_id == int(mentor.id))
    if role in scope.COLLEGE_SCOPE_ROLES:
        ids = _claim_ids(user, "collegeId", "collegeIds")
        return q.where(GraduationTopic.college_id.in_(ids or {"__NONE__"}))
    if role in scope.MAJOR_SCOPE_ROLES:
        ids = _claim_ids(user, "majorId", "majorIds")
        return q.where(GraduationTopic.major_id.in_(ids or {"__NONE__"}))
    return q.where(GraduationTopic.id == -1)


def _topic_get_manage(db, topic_id, *, for_review: bool = False) -> GraduationTopic:
    t = db.scalars(select(GraduationTopic).where(
        GraduationTopic.id == int(topic_id),
        GraduationTopic.tenant_id == _tid(),
        GraduationTopic.is_deleted.is_(False),
        GraduationTopic.id.in_(_topic_scope_select(db, for_review=for_review)),
    ).with_for_update()).first()
    if not t:
        raise no_permission("题目不存在或不在当前管理数据范围内")
    return t


def _topic_bind_scope(db, t: GraduationTopic, body: dict) -> None:
    from app.modules.graduation.services import graduation_scope_service as scope
    from app.modules.graduation.services import graduation_identity as identity

    user, role = _ctx()
    if _full_scope(role):
        if body.get("collegeId") is not None:
            t.college_id = str(body.get("collegeId") or "").strip() or None
        if body.get("majorId") is not None:
            t.major_id = str(body.get("majorId") or "").strip() or None
        return
    if role == "GD_MENTOR":
        mentor = identity.current_user_mentor(db)
        if not mentor:
            raise no_permission("当前导师身份未绑定稳定导师工号")
        t.advisor_mentor_id = int(mentor.id)
        t.advisor_name = mentor.teacher_name
        if mentor.college_id:
            t.college_id = str(mentor.college_id)
        return
    if role in scope.COLLEGE_SCOPE_ROLES:
        ids = _claim_ids(user, "collegeId", "collegeIds")
        requested = str(body.get("collegeId") or "").strip()
        if not ids or (requested and requested not in ids):
            raise no_permission("题目学院不在当前学院数据范围内")
        t.college_id = requested or next(iter(ids))
        return
    if role in scope.MAJOR_SCOPE_ROLES:
        ids = _claim_ids(user, "majorId", "majorIds")
        requested = str(body.get("majorId") or "").strip()
        if not ids or (requested and requested not in ids):
            raise no_permission("题目专业不在当前专业数据范围内")
        t.major_id = requested or next(iter(ids))
        return
    raise no_permission("当前角色无题目管理对象范围")


def _install_topic_hardening() -> None:
    from app.modules.graduation.services import graduation_topic_service as svc
    from app.modules.graduation.services import graduation_scope_service as scope

    old_disable = svc.disable_topic
    old_enable = svc.enable_topic
    old_archive = svc.archive_topic

    def create_topic(body):
        data = body.model_dump() if hasattr(body, "model_dump") else dict(body)
        st = data.get("sourceType") or "TEACHER"
        if st not in svc.VALID_SOURCE:
            raise AppException("VALIDATION_ERROR", "非法题目来源类型")
        with session() as db:
            if data.get("batchId"):
                b = db.get(GraduationBatch, int(data["batchId"]))
                if not b or b.is_deleted or b.tenant_id != _tid():
                    raise not_found("毕设批次不存在")
            t = GraduationTopic(
                tenant_id=_tid(), title=data["title"].strip(), source_type=st,
                source=svc._source_label(st), review_status="DRAFT", status="PENDING_CONFIRM",
                capacity=int(data.get("capacity") or 1), selected=0,
            )
            svc._apply_body(t, data, create=True)
            _topic_bind_scope(db, t, data)
            db.add(t); db.flush()
            svc._audit(db, t.id, "CREATE", t.title)
            if data.get("submitReview"):
                from app.core.permissions import enforce_permission
                enforce_permission(get_current_user_ctx() or {}, "graduationDesign.topic.submit")
                t.review_status = "PENDING_REVIEW"
                svc._audit(db, t.id, "SUBMIT_REVIEW", "创建并提交审核")
            db.commit()
            return svc._row_of(db, t)

    def _assert_mutable_claims(t, data: dict):
        user, role = _ctx()
        if role in scope.COLLEGE_SCOPE_ROLES and "collegeId" in data:
            ids = _claim_ids(user, "collegeId", "collegeIds")
            if str(data.get("collegeId") or "").strip() not in ids:
                raise no_permission("不能把题目移动到当前学院范围之外")
        if role in scope.MAJOR_SCOPE_ROLES and "majorId" in data:
            ids = _claim_ids(user, "majorId", "majorIds")
            if str(data.get("majorId") or "").strip() not in ids:
                raise no_permission("不能把题目移动到当前专业范围之外")
        if role == "GD_MENTOR" and any(k in data for k in ("advisorMentorId", "collegeId", "majorId")):
            raise no_permission("导师不能改变题目归属对象范围")

    def update_topic(topic_id, body):
        data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else dict(body)
        review_sensitive = {
            "title", "topicNo", "batchId", "advisorMentorId", "collegeId", "majorId",
            "requirements", "outcome", "skills", "attachments", "category", "difficulty", "capacity",
        }
        with session() as db:
            t = _topic_get_manage(db, topic_id)
            svc._ensure_editable(t)
            _assert_mutable_claims(t, data)
            if data.get("batchId"):
                b = db.get(GraduationBatch, int(data["batchId"]))
                if not b or b.is_deleted or b.tenant_id != _tid():
                    raise not_found("毕设批次不存在")
            before_title = t.title
            before_sensitive = {
                "title": t.title, "topicNo": t.topic_no or "",
                "batchId": str(t.batch_id or ""),
                "advisorMentorId": str(t.advisor_mentor_id or ""),
                "collegeId": str(t.college_id or ""), "majorId": str(t.major_id or ""),
                "requirements": t.requirements or "", "outcome": t.outcome or "",
                "skills": t.skills or "", "attachments": list(t.attachments_json or []),
                "category": t.category or "", "difficulty": t.difficulty or "",
                "capacity": int(t.capacity or 1),
            }
            was_approved = t.review_status == "APPROVED"
            svc._apply_body(t, data)
            after_sensitive = {
                "title": t.title, "topicNo": t.topic_no or "",
                "batchId": str(t.batch_id or ""),
                "advisorMentorId": str(t.advisor_mentor_id or ""),
                "collegeId": str(t.college_id or ""), "majorId": str(t.major_id or ""),
                "requirements": t.requirements or "", "outcome": t.outcome or "",
                "skills": t.skills or "", "attachments": list(t.attachments_json or []),
                "category": t.category or "", "difficulty": t.difficulty or "",
                "capacity": int(t.capacity or 1),
            }
            changed_sensitive = any(
                key in data and before_sensitive[key] != after_sensitive[key]
                for key in review_sensitive
            )
            t.version = int(t.version or 0) + 1
            svc._audit(db, t.id, "UPDATE", t.title, before_title, t.title)
            if was_approved and changed_sensitive:
                t.review_status = "PENDING_REVIEW"
                t.status = "PENDING_CONFIRM"
                t.review_comment = None
                svc._audit(db, t.id, "REVIEW_INVALIDATED", "题目关键事实变化，原审核结论失效，需重新审核")
            db.commit()
            return svc._row_of(db, t)

    def submit_review(topic_id):
        with session() as db:
            t = _topic_get_manage(db, topic_id)
            if t.status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档不可提交审核")
            if t.review_status not in ("DRAFT", "REJECTED"):
                raise AppException("DATA_CONFLICT", "仅草稿/已驳回题目可提交审核")
            t.review_status = "PENDING_REVIEW"
            t.review_comment = None
            t.version = int(t.version or 0) + 1
            svc._audit(db, t.id, "SUBMIT_REVIEW", "提交审核")
            db.commit()
            return svc._row_of(db, t)

    def review_topic(topic_id, action: str, comment: str = ""):
        if action not in ("APPROVE", "REJECT"):
            raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
        if action == "REJECT" and (not comment or len(comment.strip()) < 5):
            raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
        with session() as db:
            t = _topic_get_manage(db, topic_id, for_review=True)
            if t.review_status != "PENDING_REVIEW":
                raise AppException("DATA_CONFLICT", "仅待审核题目可审核")
            _, role = _ctx()
            if role == "GD_MENTOR" and t.advisor_mentor_id:
                from app.modules.graduation.services import graduation_identity as identity
                me = identity.current_user_mentor(db)
                if me and int(me.id) == int(t.advisor_mentor_id):
                    raise no_permission("题目申报人与审核人必须职责分离")
            before = t.review_status
            if action == "APPROVE":
                t.review_status = "APPROVED"
                t.status = "CONFIRMED"
                t.review_comment = (comment or "").strip() or None
                svc._audit(db, t.id, "APPROVE", comment or "审核通过", before, "APPROVED")
            else:
                t.review_status = "REJECTED"
                t.status = "PENDING_CONFIRM"
                t.review_comment = comment.strip()
                svc._audit(db, t.id, "REJECT", comment, before, "REJECTED")
            t.version = int(t.version or 0) + 1
            db.commit()
            return svc._row_of(db, t)

    def update_attachments(topic_id, attachments):
        with session() as db:
            t = _topic_get_manage(db, topic_id)
            if t.status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档题目不可改附件")
            before = list(t.attachments_json or [])
            after = list(attachments or [])
            t.attachments_json = after
            t.version = int(t.version or 0) + 1
            svc._audit(db, t.id, "UPDATE_ATTACHMENTS", f"{len(before)}→{len(after)}", str(len(before)), str(len(after)))
            if t.review_status == "APPROVED" and before != after:
                t.review_status = "PENDING_REVIEW"
                t.status = "PENDING_CONFIRM"
                t.review_comment = None
                svc._audit(db, t.id, "REVIEW_INVALIDATED", "题目附件变化，原审核结论失效，需重新审核")
            db.commit()
            return svc._row_of(db, t)

    def _guarded(fn):
        def inner(topic_id, *args, **kwargs):
            with session() as db:
                _topic_get_manage(db, topic_id)
            return fn(topic_id, *args, **kwargs)
        return inner

    svc._get = lambda db, tid: _topic_get_manage(db, tid)
    svc.create_topic = create_topic
    svc.update_topic = update_topic
    svc.submit_review = submit_review
    svc.review_topic = review_topic
    svc.disable_topic = _guarded(old_disable)
    svc.enable_topic = _guarded(old_enable)
    svc.archive_topic = _guarded(old_archive)
    svc.update_attachments = update_attachments
    svc.update_capacity = lambda tid, capacity: update_topic(tid, {"capacity": capacity})

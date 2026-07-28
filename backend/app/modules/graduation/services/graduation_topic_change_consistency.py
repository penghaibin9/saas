"""选题变更申请并发收口。

学生行锁串行化“同生同时只能一条待审申请”；审核时同时锁定申请、学生、原/新题目，
容量释放与占用、学生题目迁移、待办完成、域审计在一个事务内完成。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationStudent,
    GraduationTopic,
    GraduationTopicChangeRequest,
)
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session

def request_change(gd_student_id, new_topic_id, reason: str, requested_by: str = "") -> dict:
    from app.modules.graduation.services import graduation_topic_change_service as svc

    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更理由至少 5 个字")
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "topic.change.create")
        if not student.topic_id:
            raise AppException("DATA_CONFLICT", "尚未分配选题，无需变更申请，请直接选题")
        new_id = int(new_topic_id)
        if new_id == int(student.topic_id):
            raise AppException("VALIDATION_ERROR", "新题目与当前题目相同")

        topic_ids = sorted({int(student.topic_id), new_id})
        locked = {row.id: row for row in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(),
            GraduationTopic.id.in_(topic_ids),
            GraduationTopic.is_deleted.is_(False),
        ).order_by(GraduationTopic.id).with_for_update()).all()}
        new_topic = locked.get(new_id)
        if not new_topic:
            raise not_found("目标题目不存在")
        if new_topic.review_status != "APPROVED" or new_topic.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", f"题目「{new_topic.title}」未入池，不可申请变更至此")
        if int(new_topic.selected or 0) >= int(new_topic.capacity or 0):
            raise AppException("DATA_CONFLICT", f"题目「{new_topic.title}」已满员，不能申请变更至此")

        pending = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.gd_student_id == student.id,
            GraduationTopicChangeRequest.is_deleted.is_(False),
            GraduationTopicChangeRequest.status == "PENDING",
        ).with_for_update()).first()
        if pending:
            raise AppException("DATA_CONFLICT", "已有变更申请正在审核中，请等待处理后再提交")

        now = datetime.now(timezone.utc)
        record = GraduationTopicChangeRequest(
            tenant_id=_tid(), gd_student_id=student.id,
            old_topic_id=int(student.topic_id), new_topic_id=new_id,
            reason=reason, status="PENDING",
            requested_by=requested_by or student.name, requested_at=now,
        )
        db.add(record)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppException("DATA_CONFLICT", "已有变更申请正在审核中，请刷新") from exc
        svc._audit(db, record.id, "REQUEST",
                   f"{student.name} 申请由「{student.topic_title}」变更至「{new_topic.title}」：{reason}")
        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.push_topic_change_todo(db, record, student)
        db.commit()
        return svc._row_of(db, record)


def review_change(request_id, action: str, comment: str = "", reviewer_name: str = "") -> dict:
    from app.modules.graduation.services import graduation_topic_change_service as svc

    action = (action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回须填写理由（至少 5 个字）")

    with session() as db:
        record = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.id == int(request_id),
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.is_deleted.is_(False),
        ).with_for_update()).first()
        if not record:
            raise not_found("变更申请不存在")
        if record.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该变更申请已被处理，请刷新")

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == record.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "topic.change.review")
        if not student or int(student.topic_id or 0) != int(record.old_topic_id):
            raise AppException("DATA_CONFLICT", "学生当前题目已变化，请驳回后引导重新发起")

        topic_ids = sorted({int(record.old_topic_id), int(record.new_topic_id)})
        locked = {row.id: row for row in db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(),
            GraduationTopic.id.in_(topic_ids),
            GraduationTopic.is_deleted.is_(False),
        ).order_by(GraduationTopic.id).with_for_update()).all()}
        old_topic = locked.get(int(record.old_topic_id))
        new_topic = locked.get(int(record.new_topic_id))
        actor = reviewer_name or (get_current_user_ctx() or {}).get("realName") or "教师"
        now = datetime.now(timezone.utc)

        if action == "REJECT":
            record.status = "REJECTED"
            record.review_comment = (comment or "").strip()
            record.reviewer_name = actor
            record.reviewed_at = now
            svc._audit(db, record.id, "REJECT", f"{actor}：{comment}")
        else:
            if not new_topic:
                raise not_found("目标题目不存在")
            if new_topic.status != "CONFIRMED" or new_topic.review_status != "APPROVED":
                raise AppException("DATA_CONFLICT", "目标题目已不可用，请驳回该申请")
            if int(new_topic.selected or 0) >= int(new_topic.capacity or 0):
                raise AppException("DATA_CONFLICT", "目标题目已满员，请驳回该申请")
            if old_topic and int(old_topic.selected or 0) > 0:
                old_topic.selected = int(old_topic.selected or 0) - 1
            new_topic.selected = int(new_topic.selected or 0) + 1
            student.topic_id = new_topic.id
            student.topic_title = new_topic.title
            student.topic_source = new_topic.source or ""
            student.mentor_id = new_topic.advisor_mentor_id
            student.advisor_name = new_topic.advisor_name
            record.status = "APPROVED"
            record.review_comment = (comment or "").strip()
            record.reviewer_name = actor
            record.reviewed_at = now
            svc._audit(db, record.id, "APPROVE",
                       f"{actor}：由「{old_topic.title if old_topic else record.old_topic_id}」变更至「{new_topic.title}」")

        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.todo_done(db, biz_id=record.id, todo_type=gd_todo.TODO_TOPIC_CHANGE)
        db.commit()
        return svc._row_of(db, record)

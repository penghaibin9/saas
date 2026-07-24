"""毕业设计中心 · 选题变更申请服务（获批题目已有学生后换题的独立复核流程）。

对齐商业毕设管理系统"课题信息变更"惯例：题目一旦分配（进入指导阶段），
不能直接改，必须提交变更申请，由教师/管理员重新审核，通过后才生效。
横切：租户隔离 + is_deleted 软删 + 审计到 t_gd_audit_trail(biz_type=TOPIC_CHANGE)。

隔离：只读写 t_gd_topic_change_request + 复用 GraduationStudent.topic_id 校验现状，
不直接改 GraduationTopic/GraduationTopicChoice 之外的表，不影响选题轮次/志愿主链路。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationStudent, GraduationTopic,
                        GraduationTopicChangeRequest)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

STATUS_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回", "CANCELLED": "已撤销"}
STATUS_TONE = {"PENDING": "warning", "APPROVED": "success", "REJECTED": "danger", "CANCELLED": "default"}


def _audit(db, biz_id, action, detail=""):
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TOPIC_CHANGE", biz_id=str(biz_id),
                                action=action, operator="系统", detail=detail, occurred_at=datetime.now(timezone.utc)))


def _row(r: GraduationTopicChangeRequest, stu: GraduationStudent | None = None,
        old_topic: GraduationTopic | None = None, new_topic: GraduationTopic | None = None) -> dict:
    return {
        "id": str(r.id), "gdStudentId": str(r.gd_student_id),
        "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
        "oldTopicId": str(r.old_topic_id), "oldTopicTitle": old_topic.title if old_topic else "",
        "oldAdvisorName": old_topic.advisor_name if old_topic else "",
        "newTopicId": str(r.new_topic_id), "newTopicTitle": new_topic.title if new_topic else "",
        "newAdvisorName": new_topic.advisor_name if new_topic else "",
        "reason": r.reason, "status": r.status,
        "statusLabel": STATUS_LABEL.get(r.status, r.status), "statusTone": STATUS_TONE.get(r.status, "default"),
        "reviewComment": r.review_comment or "", "reviewerName": r.reviewer_name or "",
        "requestedBy": r.requested_by or "", "requestedAt": _iso(r.requested_at),
        "reviewedAt": _iso(r.reviewed_at) if r.reviewed_at else "",
        "createdAt": _iso(r.created_at),
    }


def _row_of(db, r: GraduationTopicChangeRequest) -> dict:
    stu = db.get(GraduationStudent, r.gd_student_id)
    old_t = db.get(GraduationTopic, r.old_topic_id)
    new_t = db.get(GraduationTopic, r.new_topic_id)
    return _row(r, stu, old_t, new_t)


def _get(db, request_id) -> GraduationTopicChangeRequest:
    try:
        rid = int(request_id)
    except (TypeError, ValueError):
        raise not_found("变更申请不存在")
    r = db.get(GraduationTopicChangeRequest, rid)
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("变更申请不存在")
    return r


def list_change_requests(page: int = 1, page_size: int = 20, *, gd_student_id=None,
                         status=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.is_deleted.is_(False),
            GraduationTopicChangeRequest.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationTopicChangeRequest.gd_student_id == int(gd_student_id))
        if status:
            q = q.where(GraduationTopicChangeRequest.status == status)
        rows = db.scalars(q.order_by(GraduationTopicChangeRequest.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        page_rows = rows[start:start + page_size]
        return [_row_of(db, r) for r in page_rows], total


def get_change_request(request_id) -> dict:
    with session() as db:
        r = _get(db, request_id)
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "topic.change.detail")
        return _row_of(db, r)


def list_pending_for_advisor(advisor_name: str) -> list[dict]:
    """教师端·与本人相关（原题目或新题目导师为本人）的待审变更申请。"""
    if not advisor_name:
        return []
    with session() as db:
        rows = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.is_deleted.is_(False),
            GraduationTopicChangeRequest.status == "PENDING")
            .order_by(GraduationTopicChangeRequest.id.desc())).all()
        out = []
        for r in rows:
            data = _row_of(db, r)
            if data["oldAdvisorName"] == advisor_name or data["newAdvisorName"] == advisor_name:
                out.append(data)
        return out


def request_change(gd_student_id, new_topic_id, reason: str, requested_by: str = "") -> dict:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更理由至少 5 个字")
    with session() as db:
        stu = db.get(GraduationStudent, int(gd_student_id))
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("毕设学生不存在")
        assert_student_access(db, stu, "topic.change.create")
        if not stu.topic_id:
            raise AppException("DATA_CONFLICT", "尚未分配选题，无需变更申请，请直接选题")
        new_tid = int(new_topic_id)
        if new_tid == stu.topic_id:
            raise AppException("VALIDATION_ERROR", "新题目与当前题目相同")
        new_t = db.get(GraduationTopic, new_tid)
        if not new_t or new_t.is_deleted or new_t.tenant_id != _tid():
            raise not_found("目标题目不存在")
        if new_t.review_status != "APPROVED" or new_t.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", f"题目「{new_t.title}」未入池，不可申请变更至此")
        if new_t.selected >= new_t.capacity:
            raise AppException("DATA_CONFLICT", f"题目「{new_t.title}」已满员，不能申请变更至此")
        existing_pending = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.gd_student_id == int(gd_student_id),
            GraduationTopicChangeRequest.is_deleted.is_(False),
            GraduationTopicChangeRequest.status == "PENDING")).first()
        if existing_pending:
            raise AppException("DATA_CONFLICT", "已有变更申请正在审核中，请等待处理后再提交")
        now = datetime.now(timezone.utc)
        r = GraduationTopicChangeRequest(
            tenant_id=_tid(), gd_student_id=int(gd_student_id), old_topic_id=stu.topic_id,
            new_topic_id=new_tid, reason=reason, status="PENDING",
            requested_by=requested_by or stu.name, requested_at=now)
        db.add(r)
        db.flush()
        _audit(db, r.id, "REQUEST", f"{stu.name} 申请由「{stu.topic_title}」变更至「{new_t.title}」：{reason}")
        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.push_topic_change_todo(db, r, stu)
        db.commit()
        return _row_of(db, r)


def review_change(request_id, action: str, comment: str = "", reviewer_name: str = "") -> dict:
    action = (action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回须填写理由（至少 5 个字）")
    with session() as db:
        r = _get(db, request_id)
        if r.status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅待审核申请可处理（当前：{STATUS_LABEL.get(r.status, r.status)}）")
        stu = db.get(GraduationStudent, r.gd_student_id)
        assert_student_access(db, stu, "topic.change.review")
        if not stu or stu.topic_id != r.old_topic_id:
            raise AppException("DATA_CONFLICT", "学生当前题目已变化，请驳回后引导重新发起")
        if action == "REJECT":
            r.status = "REJECTED"
            r.review_comment = comment
            r.reviewer_name = reviewer_name or "教师"
            r.reviewed_at = datetime.now(timezone.utc)
            _audit(db, r.id, "REJECT", f"{r.reviewer_name}：{comment}")
            from app.modules.graduation.services import graduation_todo_helper as gd_todo
            gd_todo.todo_done(db, biz_id=r.id, todo_type=gd_todo.TODO_TOPIC_CHANGE)
            db.commit()
            return _row_of(db, r)
        # APPROVE：原题目释放名额 + 新题目容量复核 + 直接迁移（绕开 unassign_topic 的阶段限制，
        # 因为「已进入指导阶段不能直接退选」正是本变更流程存在的原因）
        new_t = db.get(GraduationTopic, r.new_topic_id)
        if not new_t or new_t.is_deleted:
            raise not_found("目标题目不存在")
        if new_t.status == "DISABLED" or new_t.review_status != "APPROVED" or new_t.status != "CONFIRMED":
            raise AppException("DATA_CONFLICT", "目标题目已不可用，请驳回该申请")
        if new_t.selected >= new_t.capacity:
            raise AppException("DATA_CONFLICT", "目标题目已满员，请驳回该申请")
        old_t = db.get(GraduationTopic, r.old_topic_id)
        if old_t and old_t.selected > 0:
            old_t.selected -= 1
        new_t.selected += 1
        stu.topic_id = new_t.id
        stu.topic_title = new_t.title
        stu.topic_source = new_t.source or ""
        r.status = "APPROVED"
        r.review_comment = comment
        r.reviewer_name = reviewer_name or "教师"
        r.reviewed_at = datetime.now(timezone.utc)
        _audit(db, r.id, "APPROVE",
              f"{r.reviewer_name}：由「{old_t.title if old_t else r.old_topic_id}」变更至「{new_t.title}」")
        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.todo_done(db, biz_id=r.id, todo_type=gd_todo.TODO_TOPIC_CHANGE)
        db.commit()
        return _row_of(db, r)

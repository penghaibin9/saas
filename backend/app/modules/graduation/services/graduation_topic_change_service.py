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
    from app.modules.graduation.services.graduation_mobile_teacher_service import (
        topic_audit,
    )
    return topic_audit(db, biz_id, action, detail)


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


from app.modules.graduation.services.graduation_topic_change_consistency import (
    request_change,
    review_change,
)

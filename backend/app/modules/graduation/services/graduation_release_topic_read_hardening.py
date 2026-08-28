"""Graduation topic SQL list/detail/public-pool/stat read model hardening."""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from app.core.context import get_current_user_ctx
from app.models import GraduationAuditTrail, GraduationBatch, GraduationStudent, GraduationTopic
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _student_scope_select
from app.modules.graduation.services.graduation_release_topic_core_hardening import _topic_get_manage, _topic_scope_select


def _install_topic_read_hardening() -> None:
    from app.modules.graduation.services import graduation_topic_service as svc
    from app.modules.graduation.services import graduation_service as legacy

    def public_pool(page, page_size, keyword=None, status=None, batch_id=None,
                    review_status=None, is_full=None):
        with session() as db:
            q = select(GraduationTopic).where(
                GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False), GraduationTopic.status != "ARCHIVED"
            )
            if batch_id not in (None, ""):
                q = q.where(GraduationTopic.batch_id == int(batch_id))
            if review_status:
                q = q.where(GraduationTopic.review_status == review_status)
            if status == "CONFIRMED":
                q = q.where(GraduationTopic.review_status == "APPROVED", GraduationTopic.status == "CONFIRMED")
            elif status == "PENDING_CONFIRM":
                q = q.where(GraduationTopic.status == "PENDING_CONFIRM")
            elif status:
                q = q.where(GraduationTopic.status == status)
            if is_full is True:
                q = q.where(GraduationTopic.selected >= GraduationTopic.capacity)
            elif is_full is False:
                q = q.where(GraduationTopic.selected < GraduationTopic.capacity)
            if keyword:
                like = f"%{str(keyword).strip()}%"
                q = q.where(or_(GraduationTopic.title.like(like), GraduationTopic.topic_no.like(like), GraduationTopic.advisor_name.like(like)))
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            size = min(200, max(1, int(page_size)))
            rows = db.scalars(q.order_by(GraduationTopic.id.desc()).offset((max(1, int(page)) - 1) * size).limit(size)).all()
            batch_ids = {int(t.batch_id) for t in rows if t.batch_id}
            batches = {b.id: b for b in db.scalars(select(GraduationBatch).where(GraduationBatch.id.in_(batch_ids or {-1}), GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}
            items = []
            for t in rows:
                row = svc._row(t, batches.get(t.batch_id))
                # Student/public pools intentionally expose no selected-student
                # identity, even when the underlying row keeps legacy snapshots.
                row.pop("studentNames", None)
                row.pop("students", None)
                row.pop("assignedStudents", None)
                items.append(row)
            return items, total

    def list_topics(page: int, page_size: int, keyword=None, batch_id=None, source_type=None,
                    category=None, review_status=None, status=None, is_full=None,
                    archive_view=None, has_requirements=None, has_attachments=None,
                    missing_category=None):
        # The student selectable-topic pool is intentionally broader than staff
        # management scope, but it uses a minimal projection with no student PII.
        user = get_current_user_ctx() or {}
        if str(user.get("userType") or "").upper() == "STUDENT":
            return public_pool(
                page, page_size, keyword=keyword, status=status, batch_id=batch_id,
                review_status=review_status, is_full=is_full,
            )
        with session() as db:
            q = select(GraduationTopic).where(
                GraduationTopic.id.in_(_topic_scope_select(db)),
                GraduationTopic.tenant_id == _tid(),
                GraduationTopic.is_deleted.is_(False),
            )
            if batch_id: q = q.where(GraduationTopic.batch_id == int(batch_id))
            if source_type: q = q.where(GraduationTopic.source_type == source_type)
            if category: q = q.where(GraduationTopic.category == category)
            if review_status: q = q.where(GraduationTopic.review_status == review_status)
            if status: q = q.where(GraduationTopic.status == status)
            if archive_view == "archived": q = q.where(GraduationTopic.status == "ARCHIVED")
            elif archive_view == "active": q = q.where(GraduationTopic.status != "ARCHIVED")
            if keyword:
                like = f"%{str(keyword).strip()}%"
                q = q.where(or_(GraduationTopic.title.like(like), GraduationTopic.topic_no.like(like), GraduationTopic.advisor_name.like(like)))
            if is_full is True: q = q.where(GraduationTopic.selected >= GraduationTopic.capacity)
            elif is_full is False: q = q.where(GraduationTopic.selected < GraduationTopic.capacity)
            if has_requirements is True: q = q.where(func.length(func.trim(func.coalesce(GraduationTopic.requirements, ""))) > 0)
            elif has_requirements is False: q = q.where(func.length(func.trim(func.coalesce(GraduationTopic.requirements, ""))) == 0)
            if has_attachments is True: q = q.where(func.json_length(GraduationTopic.attachments_json) > 0)
            elif has_attachments is False: q = q.where(or_(GraduationTopic.attachments_json.is_(None), func.json_length(GraduationTopic.attachments_json) == 0))
            if missing_category: q = q.where(func.length(func.trim(func.coalesce(GraduationTopic.category, ""))) == 0)
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            size = min(200, max(1, int(page_size)))
            rows = db.scalars(q.order_by(GraduationTopic.id.desc()).offset((max(1, int(page)) - 1) * size).limit(size)).all()
            batch_ids = {int(t.batch_id) for t in rows if t.batch_id}
            batches = {b.id: b for b in db.scalars(select(GraduationBatch).where(
                GraduationBatch.tenant_id == _tid(), GraduationBatch.id.in_(batch_ids or {-1}), GraduationBatch.is_deleted.is_(False)
            )).all()}
            names: dict[int, list[str]] = {}
            if rows:
                page_topic_ids = [int(t.id) for t in rows]
                scoped_students = _student_scope_select(db, _tid(), batch_id=batch_id)
                for sid, tid, name in db.execute(select(GraduationStudent.id, GraduationStudent.topic_id, GraduationStudent.name).where(
                    GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(scoped_students),
                    GraduationStudent.topic_id.in_(page_topic_ids), GraduationStudent.is_deleted.is_(False),
                    GraduationStudent.record_status == "ACTIVE",
                )).all():
                    names.setdefault(int(tid), []).append(name)
            items = []
            for t in rows:
                row = svc._row(t, batches.get(t.batch_id), student_names=names.get(int(t.id), []))
                row.pop("students", None)
                items.append(row)
            return items, total

    def get_topic(topic_id):
        with session() as db:
            t = _topic_get_manage(db, topic_id)
            batch = db.get(GraduationBatch, t.batch_id) if t.batch_id else None
            student_scope = _student_scope_select(db, _tid(), batch_id=t.batch_id)
            students = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id == t.id,
                GraduationStudent.id.in_(student_scope), GraduationStudent.is_deleted.is_(False),
                GraduationStudent.record_status == "ACTIVE",
            )).all()
            logs = db.scalars(select(GraduationAuditTrail).where(
                GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "TOPIC",
                GraduationAuditTrail.biz_id == str(t.id),
            ).order_by(GraduationAuditTrail.id.desc()).limit(30)).all()
            base = svc._row(t, batch if batch and not batch.is_deleted else None)
            base.pop("students", None)
            base.pop("studentNames", None)
            return {**base,
                    "assignedStudents": [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "", "className": s.class_name or "", "stage": s.stage} for s in students],
                    "auditTrail": [{"action": x.action, "operator": x.operator or "系统", "occurredAt": _iso(x.occurred_at), "detail": x.detail or ""} for x in logs]}

    def list_assigned_students(topic_id):
        return get_topic(topic_id).get("assignedStudents", [])

    def topic_stats(batch_id=None):
        with session() as db:
            q = select(GraduationTopic).where(GraduationTopic.id.in_(_topic_scope_select(db)), GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False), GraduationTopic.status != "ARCHIVED")
            if batch_id not in (None, ""): q = q.where(GraduationTopic.batch_id == int(batch_id))
            sq = q.subquery()
            total, pending, in_pool, full, available, req_gap, att_gap, uncategorized = db.execute(select(
                func.count(),
                func.sum(sq.c.review_status == "PENDING_REVIEW"),
                func.sum(and_(sq.c.review_status == "APPROVED", sq.c.status == "CONFIRMED")),
                func.sum(sq.c.selected >= sq.c.capacity),
                func.sum(and_(sq.c.review_status == "APPROVED", sq.c.status == "CONFIRMED", sq.c.selected < sq.c.capacity)),
                func.sum(func.length(func.trim(func.coalesce(sq.c.requirements, ""))) == 0),
                func.sum(or_(sq.c.attachments_json.is_(None), func.json_length(sq.c.attachments_json) == 0)),
                func.sum(func.length(func.trim(func.coalesce(sq.c.category, ""))) == 0),
            )).one()
            cat = []
            for category_name, count, pool_count, full_count in db.execute(select(
                func.coalesce(func.nullif(func.trim(sq.c.category), ""), "未分类"), func.count(),
                func.sum(and_(sq.c.review_status == "APPROVED", sq.c.status == "CONFIRMED")),
                func.sum(sq.c.selected >= sq.c.capacity),
            ).group_by(func.coalesce(func.nullif(func.trim(sq.c.category), ""), "未分类")).order_by(func.count().desc())).all():
                cat.append({"category": category_name, "count": int(count or 0), "inPool": int(pool_count or 0), "full": int(full_count or 0)})
            return {"total": int(total or 0), "pendingReview": int(pending or 0), "inPool": int(in_pool or 0), "fullCount": int(full or 0), "availableCount": int(available or 0), "requirementsGap": int(req_gap or 0), "attachmentsGap": int(att_gap or 0), "uncategorized": int(uncategorized or 0), "categoryStats": cat, "batchId": str(batch_id) if batch_id else None}

    svc.list_topics = list_topics
    svc.get_topic = get_topic
    svc.list_assigned_students = list_assigned_students
    svc.topic_stats = topic_stats
    svc.category_stats = lambda batch_id=None: topic_stats(batch_id).get("categoryStats", [])
    legacy.list_topics = public_pool

"""Graduation mentor object scope, PII and qualification write hardening."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, or_, select
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission
from app.models import GraduationAuditTrail, GraduationMentor, GraduationMentorAssignment, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _claim_ids, _ctx, _student_scope_select
from app.modules.graduation.services.graduation_release_mentor_common import _mentor_get_manage, _mentor_scope_select


def _install_mentor_manage_hardening() -> None:
    from app.modules.graduation.services import graduation_mentor_service as svc
    from app.modules.graduation.services import graduation_scope_service as scope
    old_list_evals = svc.list_evals
    def create_mentor(body: dict):
        user, role = _ctx()
        data = dict(body)
        if role in scope.COLLEGE_SCOPE_ROLES:
            allowed = _claim_ids(user, "collegeId", "collegeIds")
            requested = str(data.get("collegeId") or "").strip()
            if not allowed or (requested and requested not in allowed):
                raise no_permission("导师学院不在当前学院数据范围内")
            data["collegeId"] = requested or next(iter(allowed))
        elif role in scope.MAJOR_SCOPE_ROLES:
            raise no_permission("导师主档缺少稳定 majorId，专业管理员暂不可维护导师资格")
        no = str(data.get("teacherNo") or "").strip()
        name = str(data.get("teacherName") or "").strip()
        if not no or not name:
            raise AppException("VALIDATION_ERROR", "教师工号与姓名必填")
        with session() as db:
            dup = db.scalars(select(GraduationMentor.id).where(
                GraduationMentor.tenant_id == _tid(), GraduationMentor.teacher_no == no,
                GraduationMentor.is_deleted.is_(False),
            ).limit(1)).first()
            if dup:
                raise AppException("DATA_CONFLICT", f"该教师工号已在导师库：{no}")
            from app.core.field_crypto import encrypt_field
            m = GraduationMentor(
                tenant_id=_tid(), teacher_no=no, teacher_name=name,
                mentor_type=data.get("mentorType") or "INTERNAL", title=data.get("title"),
                college_id=str(data.get("collegeId") or "").strip() or None,
                college_name=data.get("collegeName"), major_name=data.get("majorName"),
                research_direction=data.get("researchDirection"),
                max_capacity=int(data.get("maxCapacity") or 8),
                phone_encrypted=encrypt_field(data.get("phone")), remark=data.get("remark"),
                qualification_status="PENDING_REVIEW",
            )
            db.add(m); db.flush()
            svc._audit(db, "MENTOR", m.id, "申报导师", detail=f"{name}/{no}")
            db.commit()
            return svc._mentor_row(m)

    def update_mentor(mentor_id, body: dict):
        data = dict(body)
        with session() as db:
            m = _mentor_get_manage(db, mentor_id, lock=True)
            if m.qualification_status in ("DISABLED", "ARCHIVED"):
                raise AppException("DATA_CONFLICT", f"「{svc.QUAL_LABEL.get(m.qualification_status)}」导师不可编辑")
            before = {"teacherName": m.teacher_name, "mentorType": m.mentor_type, "title": m.title, "collegeId": m.college_id}
            user, role = _ctx()
            if role in scope.COLLEGE_SCOPE_ROLES and "collegeId" in data:
                allowed = _claim_ids(user, "collegeId", "collegeIds")
                if str(data.get("collegeId") or "").strip() not in allowed:
                    raise no_permission("不能把导师移动到当前学院范围之外")
            for src, col in [("teacherName", "teacher_name"), ("mentorType", "mentor_type"),
                             ("title", "title"), ("collegeName", "college_name"),
                             ("majorName", "major_name"), ("researchDirection", "research_direction"),
                             ("remark", "remark")]:
                if src in data and data[src] is not None:
                    setattr(m, col, data[src])
            if "phone" in data and data["phone"] is not None:
                from app.core.field_crypto import encrypt_field
                m.phone_encrypted = encrypt_field(data["phone"])
            if "collegeId" in data:
                m.college_id = str(data.get("collegeId") or "").strip() or None
            if "maxCapacity" in data and data["maxCapacity"] is not None:
                cap = int(data["maxCapacity"])
                if cap < int(m.current_count or 0):
                    raise AppException("VALIDATION_ERROR", f"最大容量不可低于当前已指导人数（{m.current_count}）")
                m.max_capacity = cap
            sensitive_changed = any([
                "teacherName" in data and str(data.get("teacherName") or "") != str(before["teacherName"] or ""),
                "mentorType" in data and str(data.get("mentorType") or "") != str(before["mentorType"] or ""),
                "title" in data and str(data.get("title") or "") != str(before["title"] or ""),
                "collegeId" in data and str(data.get("collegeId") or "") != str(before["collegeId"] or ""),
            ])
            m.version = int(m.version or 0) + 1
            svc._audit(db, "MENTOR", m.id, "编辑导师信息")
            if sensitive_changed and m.qualification_status == "QUALIFIED":
                m.qualification_status = "PENDING_REVIEW"
                m.review_comment = None; m.reviewer_name = None; m.reviewed_at = None
                svc._audit(db, "MENTOR", m.id, "关键资格信息变更，资格重新待审")
            db.commit()
            return svc._mentor_row(m)

    def list_mentors(page: int, page_size: int, keyword=None, qualification_status=None, mentor_type=None, has_capacity=None):
        with session() as db:
            q = select(GraduationMentor).where(GraduationMentor.id.in_(_mentor_scope_select(db)), GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False))
            if keyword:
                like = f"%{str(keyword).strip()}%"
                q = q.where(or_(GraduationMentor.teacher_name.like(like), GraduationMentor.teacher_no.like(like), GraduationMentor.research_direction.like(like)))
            if qualification_status: q = q.where(GraduationMentor.qualification_status == qualification_status)
            if mentor_type: q = q.where(GraduationMentor.mentor_type == mentor_type)
            if has_capacity is not None:
                want = str(has_capacity).lower() in {"1", "true", "yes"}
                q = q.where(GraduationMentor.current_count < GraduationMentor.max_capacity) if want else q.where(GraduationMentor.current_count >= GraduationMentor.max_capacity)
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            size = min(200, max(1, int(page_size)))
            rows = db.scalars(q.order_by(GraduationMentor.id.desc()).offset((max(1, int(page))-1)*size).limit(size)).all()
            return [svc._mentor_row(m) for m in rows], total

    def get_mentor(mentor_id):
        with session() as db:
            m = _mentor_get_manage(db, mentor_id)
            student_scope = _student_scope_select(db, _tid())
            students = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.mentor_id == m.id,
                GraduationStudent.id.in_(student_scope), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE"
            )).all()
            trail = db.scalars(select(GraduationAuditTrail).where(GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "MENTOR", GraduationAuditTrail.biz_id == str(m.id)).order_by(GraduationAuditTrail.id.desc()).limit(30)).all()
            return {**svc._mentor_row(m), "latestEval": svc.latest_eval(db, m.id),
                    "students": [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "", "className": s.class_name or "", "topicTitle": s.topic_title or "", "stage": s.stage} for s in students],
                    "auditTrail": [{"action": a.action, "operator": a.operator or "", "roleName": a.role_name or "", "detail": a.detail or "", "occurredAt": _iso(a.occurred_at)} for a in trail]}

    def list_evals(mentor_id):
        with session() as db:
            _mentor_get_manage(db, mentor_id)
        return old_list_evals(mentor_id)

    svc.create_mentor = create_mentor
    svc.update_mentor = update_mentor
    svc.list_mentors = list_mentors
    svc.get_mentor = get_mentor
    svc.list_evals = list_evals

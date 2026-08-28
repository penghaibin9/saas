"""Graduation mentor assignment concurrency and streaming export hardening."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Iterable
from sqlalchemy import func, select
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import GraduationMentor, GraduationMentorAssignment, GraduationStudent
from app.services.db_service import _tid, session
from app.modules.graduation.services.graduation_release_mentor_common import _mentor_get_manage, _mentor_scope_select


def _install_mentor_assignment_hardening() -> None:
    from app.modules.graduation.services import graduation_mentor_service as svc
    from app.modules.graduation.services import graduation_scope_service as scope
    def _lock_student(db, sid):
        s = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(sid), GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE"
        ).with_for_update()).first()
        if not s: raise not_found("毕设学生不存在")
        return scope.assert_student_access(db, s, "mentor.assignment")

    def _lock_mentors(db, ids: Iterable[int]):
        ids = sorted({int(x) for x in ids if x})
        rows = db.scalars(select(GraduationMentor).where(
            GraduationMentor.tenant_id == _tid(), GraduationMentor.id.in_(ids or {-1}), GraduationMentor.is_deleted.is_(False)
        ).order_by(GraduationMentor.id).with_for_update()).all()
        by_id = {int(m.id): m for m in rows}
        for mid in ids:
            if mid not in by_id: raise not_found("导师不存在")
        return by_id

    def _active_count(db, mentor_id):
        return int(db.scalar(select(func.count()).select_from(GraduationMentorAssignment).where(
            GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.mentor_id == int(mentor_id),
            GraduationMentorAssignment.status == "ACTIVE", GraduationMentorAssignment.is_deleted.is_(False)
        )) or 0)

    def assign_mentor(gd_student_id, mentor_id, reason=None):
        with session() as db:
            stu = _lock_student(db, gd_student_id)
            active = db.scalars(select(GraduationMentorAssignment).where(
                GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.gd_student_id == stu.id,
                GraduationMentorAssignment.status == "ACTIVE", GraduationMentorAssignment.is_deleted.is_(False)
            ).with_for_update()).first()
            if active or stu.mentor_id: raise AppException("DATA_CONFLICT", "该生已有导师，如需更换请使用「调导师」")
            mentor = _lock_mentors(db, [mentor_id])[int(mentor_id)]
            if mentor.id not in set(db.scalars(_mentor_scope_select(db)).all()): raise no_permission("目标导师不在当前管理范围内")
            if mentor.qualification_status != "QUALIFIED": raise AppException("DATA_CONFLICT", "仅「已认证」导师可被分配学生")
            current = _active_count(db, mentor.id)
            mentor.current_count = current
            if current >= int(mentor.max_capacity): raise AppException("DATA_CONFLICT", f"该导师已满员（{current}/{mentor.max_capacity}）")
            n, _ = svc._op()
            a = GraduationMentorAssignment(tenant_id=_tid(), gd_student_id=stu.id, mentor_id=mentor.id, assign_source="MANUAL", assign_reason=str(reason or "").strip(), status="ACTIVE", assigned_by=n, assigned_at=datetime.now(timezone.utc))
            db.add(a); db.flush()
            stu.mentor_id = mentor.id; stu.advisor_name = mentor.teacher_name; mentor.current_count = current + 1
            svc._audit(db, "MENTOR_ASSIGN", a.id, "分配导师", detail=f"{stu.name}→{mentor.teacher_name}")
            db.commit()
            return {"id": str(a.id), "gdStudentId": str(stu.id), "mentorId": str(mentor.id), "mentorName": mentor.teacher_name, "status": "ACTIVE"}

    def change_mentor(gd_student_id, new_mentor_id, reason):
        reason = str(reason or "").strip()
        if len(reason) < 5: raise AppException("VALIDATION_ERROR", "调导师原因必填且不少于 5 字")
        with session() as db:
            stu = _lock_student(db, gd_student_id)
            active = db.scalars(select(GraduationMentorAssignment).where(
                GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.gd_student_id == stu.id,
                GraduationMentorAssignment.status == "ACTIVE", GraduationMentorAssignment.is_deleted.is_(False)
            ).with_for_update()).first()
            if not active or not stu.mentor_id: raise AppException("DATA_CONFLICT", "该生尚无导师，请使用「分配导师」")
            if int(stu.mentor_id) == int(new_mentor_id): raise AppException("DATA_CONFLICT", "新导师与当前导师相同")
            mentors = _lock_mentors(db, [int(stu.mentor_id), int(new_mentor_id)])
            old_m, new_m = mentors[int(stu.mentor_id)], mentors[int(new_mentor_id)]
            if new_m.id not in set(db.scalars(_mentor_scope_select(db)).all()): raise no_permission("目标导师不在当前管理范围内")
            if new_m.qualification_status != "QUALIFIED": raise AppException("DATA_CONFLICT", "仅「已认证」导师可被分配学生")
            new_count = _active_count(db, new_m.id)
            if new_count >= int(new_m.max_capacity): raise AppException("DATA_CONFLICT", f"该导师已满员（{new_count}/{new_m.max_capacity}）")
            old_count = _active_count(db, old_m.id)
            now = datetime.now(timezone.utc); active.status = "CHANGED"; active.ended_at = now
            n, _ = svc._op()
            a = GraduationMentorAssignment(tenant_id=_tid(), gd_student_id=stu.id, mentor_id=new_m.id, previous_mentor_id=old_m.id, assign_source="CHANGE", assign_reason=reason, status="ACTIVE", assigned_by=n, assigned_at=now)
            db.add(a); db.flush(); stu.mentor_id = new_m.id; stu.advisor_name = new_m.teacher_name
            old_m.current_count = max(0, old_count - 1); new_m.current_count = new_count + 1
            svc._audit(db, "MENTOR_ASSIGN", a.id, "调导师", reason, before=old_m.teacher_name, after=new_m.teacher_name)
            db.commit(); return {"id": str(a.id), "gdStudentId": str(stu.id), "mentorId": str(new_m.id), "mentorName": new_m.teacher_name, "status": "ACTIVE"}

    def cancel_assignment(assignment_id, reason):
        reason = str(reason or "").strip()
        if len(reason) < 5: raise AppException("VALIDATION_ERROR", "取消原因必填且不少于 5 字")
        with session() as db:
            probe = db.scalars(select(GraduationMentorAssignment).where(GraduationMentorAssignment.id == int(assignment_id), GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.is_deleted.is_(False))).first()
            if not probe: raise not_found("分配记录不存在")
            stu = _lock_student(db, probe.gd_student_id)
            a = db.scalars(select(GraduationMentorAssignment).where(GraduationMentorAssignment.id == int(assignment_id), GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.is_deleted.is_(False)).with_for_update()).first()
            if a.status != "ACTIVE": raise AppException("DATA_CONFLICT", "仅「生效中」分配可取消")
            mentor = _lock_mentors(db, [a.mentor_id])[int(a.mentor_id)]
            before = _active_count(db, mentor.id)
            a.status = "CANCELLED"; a.ended_at = datetime.now(timezone.utc)
            if stu.mentor_id == a.mentor_id: stu.mentor_id = None; stu.advisor_name = None
            mentor.current_count = max(0, before - 1)
            svc._audit(db, "MENTOR_ASSIGN", a.id, "取消分配", reason)
            db.commit(); return {"id": str(a.id), "status": "CANCELLED"}

    def export_mentors_xlsx(keyword=None, qualification_status=None, mentor_type=None):
        def rows():
            page = 1
            while True:
                items, _ = svc.list_mentors(page, 200, keyword=keyword, qualification_status=qualification_status, mentor_type=mentor_type)
                if not items: break
                for it in items:
                    yield [it.get("teacherNo", ""), it.get("teacherName", ""), it.get("mentorTypeLabel", ""), it.get("title", ""), it.get("collegeName", ""), it.get("majorName", ""), it.get("researchDirection", ""), it.get("capacityText", ""), it.get("qualificationLabel", ""), it.get("updatedAt", "")]
                if len(items) < 200: break
                page += 1
        from openpyxl import Workbook
        wb = Workbook(write_only=True); ws = wb.create_sheet("导师名单与工作量台账")
        headers = ["教师工号", "教师姓名", "导师类型", "职称", "学院", "专业", "指导方向", "工作量(已指导/上限)", "资格状态", "更新时间"]
        operator = str((get_current_user_ctx() or {}).get("realName") or "系统")
        ws.append([f"导师名单与工作量台账　导出时间：{datetime.now():%Y-%m-%d %H:%M}　导出人：{operator}"] + [""] * (len(headers)-1))
        ws.append(headers); row_count = 0
        for row in rows(): ws.append(row); row_count += 1
        buf = io.BytesIO(); wb.save(buf)
        return {"filename": f"导师名单与工作量台账_{datetime.now():%Y%m%d_%H%M}.xlsx", "contentBase64": base64.b64encode(buf.getvalue()).decode("ascii"), "rowCount": row_count, "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    svc._get_mentor = lambda db, mid: _mentor_get_manage(db, mid)
    svc.assign_mentor = assign_mentor
    svc.change_mentor = change_mentor
    svc.cancel_assignment = cancel_assignment
    from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export
    svc.export_mentors_xlsx = sanitize_xlsx_export(export_mentors_xlsx)

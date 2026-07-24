"""学生主档 → 业务投影同步。

原则：
- StudentProfile 是唯一身份真相；
- 业务表默认只存 student_id；
- CsServiceStudent / GraduationStudent 的姓名班级等为投影缓存，主档变更后异步/同步刷新；
- 敏感手机号/身份证不在投影表重复落密文（仅刷新非敏感展示字段）。
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.services.db_service import _tid, session

log = logging.getLogger("app.student_projection")


def sync_student_projections(student_id: int) -> dict:
    """按 student_id 刷新在校服务 / 毕设投影姓名班级等非敏感字段。"""
    from app.models import CsServiceStudent, GraduationStudent, StudentProfile
    from app.models.org import College, Major, SchoolClass

    updated = {"campus": 0, "graduation": 0}
    with session() as db:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not s:
            return updated

        college_name = ""
        major_name = ""
        class_name = ""
        if s.college_id:
            c = db.get(College, s.college_id)
            college_name = (c.name if c else "") or ""
        if s.major_id:
            m = db.get(Major, s.major_id)
            major_name = (m.name if m else "") or ""
        if s.class_id:
            cl = db.get(SchoolClass, s.class_id)
            class_name = (cl.name if cl else "") or ""

        for row in db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(),
            CsServiceStudent.student_id == s.id,
            CsServiceStudent.is_deleted.is_(False),
        )).all():
            row.name = s.real_name
            row.student_no = s.student_no
            row.class_id = str(s.class_id) if s.class_id else row.class_id
            row.class_name = class_name or row.class_name
            if hasattr(row, "college_name"):
                row.college_name = college_name
            if hasattr(row, "major_name"):
                row.major_name = major_name
            row.version = int(row.version or 0) + 1
            updated["campus"] += 1

        for row in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.student_id == s.id,
            GraduationStudent.is_deleted.is_(False),
        )).all():
            row.name = s.real_name
            row.student_no = s.student_no
            row.class_name = class_name or row.class_name
            if s.class_id:
                row.class_id = str(s.class_id)
            row.version = int(row.version or 0) + 1
            updated["graduation"] += 1

        db.commit()
    log.info("student projection synced student_id=%s %s", student_id, updated)
    return updated

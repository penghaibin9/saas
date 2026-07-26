"""学生主档 → 业务投影同步。

原则：
- StudentProfile 是唯一身份真相；
- 业务表默认只存 student_id；
- CsServiceStudent / GraduationStudent 的姓名班级等为投影缓存，主档变更后同步刷新；
- 敏感手机号/身份证不在投影表重复落密文（仅刷新非敏感展示字段）。

事务口径（学生主档统一整改 阶段 A）：
- 在线写路径必须用 `sync_student_projections_in_session(db, student)`，与主档同事务、
  在 commit 之前执行；投影失败则主档一起回滚，不再出现「主档已改、接口报错、用户重试」；
- `sync_student_projections(student_id)` 自开事务，只保留给维护脚本与补偿任务。
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.services.db_service import _tid, session

log = logging.getLogger("app.student_projection")


def _org_display_names(db, s) -> tuple[str, str, str]:
    """读取学院/专业/班级展示名。

    org 模型的列是 college_name / major_name / class_name；历史实现误写成 `.name`，
    只要主档带组织 ID 就会 AttributeError。
    """
    from app.models.org import College, Major, SchoolClass

    college_name = major_name = class_name = ""
    if s.college_id:
        c = db.get(College, s.college_id)
        college_name = (c.college_name if c else "") or ""
    if s.major_id:
        m = db.get(Major, s.major_id)
        major_name = (m.major_name if m else "") or ""
    if s.class_id:
        cl = db.get(SchoolClass, s.class_id)
        class_name = (cl.class_name if cl else "") or ""
    return college_name, major_name, class_name


def sync_student_projections_in_session(db, s) -> dict:
    """在调用方事务内刷新投影，**不 commit**。主档写路径的唯一正确入口。"""
    from app.models import CsServiceStudent, GraduationStudent

    updated = {"campus": 0, "graduation": 0}
    if s is None:
        return updated
    tenant_id = int(s.tenant_id)
    college_name, major_name, class_name = _org_display_names(db, s)

    for row in db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == tenant_id,
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
        GraduationStudent.tenant_id == tenant_id,
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

    # 旧域影子台账（学业/就业/迎新）同样按 student_id 跟随主档。
    # 这三张表的姓名/学号不只是展示：列表关键字搜索、导出、统计都直接查它们的列，
    # 只在接口渲染层做双读覆盖的话，「改了学籍后按新名字搜不到人」依旧存在。
    from app.models import AcademicStudent, EmpStudent, OrientationStudent

    for model, key in ((AcademicStudent, "academic"), (EmpStudent, "employment"),
                       (OrientationStudent, "orientation")):
        updated[key] = 0
        for row in db.scalars(select(model).where(
            model.tenant_id == tenant_id,
            model.student_id == s.id,
            model.is_deleted.is_(False),
        )).all():
            row.name = s.real_name
            if hasattr(row, "student_no"):
                row.student_no = s.student_no
            if s.class_id:
                row.class_id = str(s.class_id)
            row.class_name = class_name or row.class_name
            row.college_name = college_name or row.college_name
            row.major_name = major_name or row.major_name
            row.version = int(row.version or 0) + 1
            updated[key] += 1

    return updated


def sync_student_projections(student_id: int) -> dict:
    """独立事务版本：按 student_id 刷新投影。仅限维护脚本/补偿任务，在线写路径勿用。"""
    from app.models import StudentProfile

    updated = {"campus": 0, "graduation": 0}
    with session() as db:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not s:
            return updated
        updated = sync_student_projections_in_session(db, s)
        db.commit()
    log.info("student projection synced student_id=%s %s", student_id, updated)
    return updated

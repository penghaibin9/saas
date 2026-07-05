"""教师范围映射种子（t_teacher_student_scope 最小可用版，幂等）。
让演示教师账号从 TENANT_FALLBACK 收敛到 SCOPED：
- counselor01 王莉（辅导员）      → CLASS：软件2301班（张一鸣所在班）+ 软件2301/软件2302
- teacher01   李明（毕设/实习导师）→ STUDENT：2023100001；ADVISOR 别名映射：刘强（实习）/ 王芳（毕设）
  （历史种子数据导师姓名与演示账号姓名不一致，用 ADVISOR ref_value 做过渡映射，
   正式迁移方案：域表 advisor_name 改存 teacher_key 外键后删除别名行）
- employment01 刘芳（就业老师）    → CLASS：软件2301班 + 软件2301/软件2302
- academic01 / college_admin01 / school_admin01 → 管理类角色，代码内 ADMIN_TENANT，无需行
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import TeacherStudentScope

TID = 1000000000000000001

SCOPE_ROWS = [
    # teacher_key, teacher_name, role_code, scope_type, ref_value
    ("counselor01", "王莉", "COUNSELOR", "CLASS", "软件2301班"),
    ("counselor01", "王莉", "COUNSELOR", "CLASS", "软件2301"),
    ("counselor01", "王莉", "COUNSELOR", "CLASS", "软件2302"),
    ("teacher01", "李明", None, "STUDENT", "2023100001"),
    ("teacher01", "李明", "INTERN_MENTOR", "ADVISOR", "刘强"),
    ("teacher01", "李明", "GD_MENTOR", "ADVISOR", "王芳"),
    ("employment01", "刘芳", "EMPLOYMENT_TEACHER", "CLASS", "软件2301班"),
    ("employment01", "刘芳", "EMPLOYMENT_TEACHER", "CLASS", "软件2301"),
    ("employment01", "刘芳", "EMPLOYMENT_TEACHER", "CLASS", "软件2302"),
]


def seed_teacher_scope(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == tenant_id)).first():
        return {"skipped": True}
    for key, name, role, stype, ref in SCOPE_ROWS:
        db.add(TeacherStudentScope(tenant_id=tenant_id, teacher_key=key, teacher_name=name,
                                   role_code=role, scope_type=stype, ref_value=ref,
                                   status="ACTIVE"))
    db.commit()
    return {"rows": len(SCOPE_ROWS)}

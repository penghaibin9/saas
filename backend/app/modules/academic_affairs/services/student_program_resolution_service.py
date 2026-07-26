"""学生培养方案绑定解析器。

毕业审核、学分进度和学生自查必须使用同一确定规则，禁止按专业 ``first()`` 猜方案：
1. 班级特例绑定；
2. 专业 + 学生入学年级绑定；
3. 仅当该专业恰好只有一个有效绑定时兼容回退；
4. 多条候选无法唯一确定时返回 AMBIGUOUS，不擅自给出毕业结论。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select


@dataclass(frozen=True)
class ProgramResolution:
    program: object | None
    binding: object | None
    status: str
    rule: str
    message: str


def resolve_student_program(db, student, *, tenant_id: int) -> ProgramResolution:
    from app.models import AaProgram, AaProgramBinding

    if not student or not getattr(student, "major_id", None):
        return ProgramResolution(None, None, "MISSING", "NO_MAJOR", "学生未维护专业，无法解析培养方案")

    rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == int(tenant_id),
        AaProgramBinding.major_id == int(student.major_id),
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    ).order_by(AaProgramBinding.id.desc())).all()

    def enabled(binding):
        program = db.get(AaProgram, int(binding.program_id)) if binding.program_id else None
        if not program or program.is_deleted or program.tenant_id != int(tenant_id):
            return None
        if str(program.status or "").upper() != "ENABLED":
            return None
        return program

    # 班级特例优先；同一班级若多条有效绑定，属于数据冲突，不猜最新一条。
    if getattr(student, "class_id", None):
        class_rows = [r for r in rows if r.class_id and int(r.class_id) == int(student.class_id)]
        valid = [(r, enabled(r)) for r in class_rows]
        valid = [(r, p) for r, p in valid if p is not None]
        if len(valid) == 1:
            r, p = valid[0]
            return ProgramResolution(p, r, "RESOLVED", "CLASS_BINDING", "按学生行政班特例绑定解析")
        if len(valid) > 1:
            return ProgramResolution(None, None, "AMBIGUOUS", "CLASS_BINDING_CONFLICT",
                                     "该班级存在多条有效培养方案绑定，请先修复绑定数据")

    grade = str(getattr(student, "grade", None) or "").strip()
    if grade:
        grade_rows = [r for r in rows if str(r.grade_year or "").strip() == grade and not r.class_id]
        valid = [(r, enabled(r)) for r in grade_rows]
        valid = [(r, p) for r, p in valid if p is not None]
        if len(valid) == 1:
            r, p = valid[0]
            return ProgramResolution(p, r, "RESOLVED", "MAJOR_GRADE_BINDING", "按专业和入学年级绑定解析")
        if len(valid) > 1:
            return ProgramResolution(None, None, "AMBIGUOUS", "MAJOR_GRADE_CONFLICT",
                                     "该专业年级存在多条有效培养方案绑定，请先修复绑定数据")

    # 兼容历史：专业下只有一个有效、非班级绑定时才允许回退。
    generic = [(r, enabled(r)) for r in rows if not r.class_id]
    generic = [(r, p) for r, p in generic if p is not None]
    if len(generic) == 1:
        r, p = generic[0]
        return ProgramResolution(p, r, "RESOLVED", "UNIQUE_MAJOR_FALLBACK",
                                 "历史数据未按年级绑定，因专业仅一个有效方案而兼容解析")
    if len(generic) > 1:
        return ProgramResolution(None, None, "AMBIGUOUS", "MULTIPLE_MAJOR_BINDINGS",
                                 "专业存在多个年级方案，但学生年级未匹配，不能自动判断")
    return ProgramResolution(None, None, "MISSING", "NO_ACTIVE_BINDING", "未找到学生适用的有效培养方案")

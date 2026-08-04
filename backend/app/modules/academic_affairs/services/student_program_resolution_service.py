"""学生培养方案绑定解析器。

毕业审核、学分进度和学生自查必须使用同一确定规则，禁止按专业 ``first()`` 猜方案：
1. 班级当前绑定；
2. 专业 + 学生入学年级当前绑定；
3. 同一班级或专业年级范围内，按生效时间选择历史绑定；
4. 无法唯一证明时返回 MISSING/AMBIGUOUS，不擅自给出毕业结论。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import select


@dataclass(frozen=True)
class ProgramResolution:
    program: object | None
    binding: object | None
    status: str
    rule: str
    message: str


_EFFECTIVE_PROGRAM_STATUSES = {"PUBLISHED", "ENABLED", "FROZEN"}


def _naive_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _binding_time(binding) -> datetime | None:
    return _naive_utc(getattr(binding, "bound_at", None))


def resolve_student_program(db, student, *, tenant_id: int, as_of=None) -> ProgramResolution:
    from app.models import AaProgram, AaProgramBinding

    if not student or not getattr(student, "major_id", None):
        return ProgramResolution(None, None, "MISSING", "NO_MAJOR", "学生未维护专业，无法解析培养方案")

    resolved_at = _naive_utc(as_of) or datetime.utcnow()
    rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == int(tenant_id),
        AaProgramBinding.major_id == int(student.major_id),
        AaProgramBinding.status.in_(["ACTIVE", "SUPERSEDED"]),
        AaProgramBinding.is_deleted.is_(False),
    ).order_by(AaProgramBinding.id.desc())).all()

    def effective_program(binding):
        program = db.get(AaProgram, int(binding.program_id)) if binding.program_id else None
        if not program or program.is_deleted or program.tenant_id != int(tenant_id):
            return None
        if str(program.status or "").upper() not in _EFFECTIVE_PROGRAM_STATUSES:
            return None
        return program

    def choose(scope_rows, *, current_rule, history_rule, conflict_rule, invalid_rule, scope_label):
        if not scope_rows:
            return None
        candidates = [(row, effective_program(row)) for row in scope_rows]
        valid = [(row, program) for row, program in candidates if program is not None]
        current = [(row, program) for row, program in valid if str(row.status or "").upper() == "ACTIVE"]
        if len(current) == 1:
            row, program = current[0]
            return ProgramResolution(program, row, "RESOLVED", current_rule, f"按{scope_label}当前绑定解析")
        if len(current) > 1:
            return ProgramResolution(None, None, "AMBIGUOUS", conflict_rule,
                                     f"{scope_label}存在多条当前有效培养方案绑定，请先修复绑定数据")

        historical = [
            (row, program, _binding_time(row))
            for row, program in valid
            if str(row.status or "").upper() == "SUPERSEDED"
            and _binding_time(row) is not None
            and _binding_time(row) <= resolved_at
        ]
        if historical:
            latest_time = max(item[2] for item in historical)
            latest = [(row, program) for row, program, bound_at in historical if bound_at == latest_time]
            if len(latest) == 1:
                row, program = latest[0]
                return ProgramResolution(program, row, "RESOLVED", history_rule,
                                         f"按{scope_label}生效日期内历史绑定解析")
            return ProgramResolution(None, None, "AMBIGUOUS", conflict_rule,
                                     f"{scope_label}同一生效时点存在多条历史培养方案绑定")

        # 该范围已经明确配置过绑定，但方案不可用或历史绑定缺少可证明生效时间时，不得降级猜其它方案。
        return ProgramResolution(None, None, "MISSING", invalid_rule,
                                 f"{scope_label}绑定存在，但方案状态或生效时间不满足毕业审核要求")

    if getattr(student, "class_id", None):
        class_rows = [row for row in rows if row.class_id and int(row.class_id) == int(student.class_id)]
        picked = choose(
            class_rows,
            current_rule="CLASS_BINDING",
            history_rule="CLASS_HISTORICAL_EFFECTIVE",
            conflict_rule="CLASS_BINDING_CONFLICT",
            invalid_rule="CLASS_BINDING_INVALID",
            scope_label="学生行政班",
        )
        if picked is not None:
            return picked

    grade = str(getattr(student, "grade", None) or "").strip()
    if grade:
        grade_rows = [
            row for row in rows
            if not row.class_id and str(row.grade_year or "").strip() == grade
        ]
        picked = choose(
            grade_rows,
            current_rule="MAJOR_GRADE_BINDING",
            history_rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE",
            conflict_rule="MAJOR_GRADE_CONFLICT",
            invalid_rule="MAJOR_GRADE_BINDING_INVALID",
            scope_label="专业与入学年级",
        )
        if picked is not None:
            return picked

    return ProgramResolution(
        None,
        None,
        "MISSING",
        "NO_EFFECTIVE_BINDING",
        "未找到班级、专业年级或生效日期内历史培养方案绑定",
    )

def credit_requirement_payload(db, student, *, tenant_id: int, earned_credits=0, as_of=None) -> dict:
    """把培养方案解析结果转换为所有学分页面共用的正式合同。

    未解析时 ``requiredCredits`` / ``missingCredits`` 必须为 ``None``，
    禁止使用学校无依据的默认学分或把未知解释为通过。
    """
    resolution = resolve_student_program(
        db, student, tenant_id=int(tenant_id), as_of=as_of
    )
    earned = float(earned_credits or 0)
    program = resolution.program if resolution.status == "RESOLVED" else None
    required = (
        float(program.total_credits)
        if program is not None and getattr(program, "total_credits", None) is not None
        else None
    )
    resolved = required is not None
    return {
        "resolutionStatus": "RESOLVED" if resolved else "UNRESOLVED",
        "programId": str(program.id) if resolved else None,
        "programVersion": int(program.version) if resolved and getattr(program, "version", None) is not None else None,
        "requiredCredits": required if resolved else None,
        "earnedCredits": earned,
        "obtainedCredits": earned,
        "missingCredits": max(0.0, required - earned) if resolved else None,
        "canJudgeGraduation": bool(resolved),
        "blockingReason": None if resolved else resolution.message,
        "resolutionRule": resolution.rule,
    }

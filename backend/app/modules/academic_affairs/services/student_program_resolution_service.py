"""学生培养方案解析适配器。

学生学业进度、毕业审核和历史学籍事实不再维护自己的 Program 状态/绑定优先级；
当前与历史语义统一委托 A-W2 canonical Program activation resolver。

Stage C2：凡调用方要求 ``as_of`` 历史语义，必须先把 ``StudentProfile`` 转为该时点的
``StudentAcademicFact`` 再解析方案，禁止“方案绑定按历史、学生专业却读 current profile”的半历史状态。
"""
from __future__ import annotations

from .academic_affairs_program_activation_service import (
    ProgramActivationResolution as ProgramResolution,
    _naive_utc,
    resolve_program_for_scope,
)


def resolve_student_program(db, student, *, tenant_id: int, as_of=None) -> ProgramResolution:
    if not student or not getattr(student, "major_id", None):
        return ProgramResolution(None, None, "MISSING", "NO_MAJOR", "学生未维护专业，无法解析培养方案")

    return resolve_program_for_scope(
        db,
        tenant_id=int(tenant_id),
        major_id=int(student.major_id),
        grade_year=str(getattr(student, "grade", None) or "").strip(),
        class_id=(int(student.class_id) if getattr(student, "class_id", None) else None),
        as_of=as_of,
    )


def resolve_student_program_at(db, student, *, tenant_id: int, as_of) -> ProgramResolution:
    """按历史学籍事实解析培养方案；缺少可证明 AcademicFact 时 fail-closed 为 MISSING。

    ``StudentProfile`` 只作为稳定 student_id 入口。专业、班级、年级全部来自 ``as_of`` 时点的
    AcademicFact，避免今天转专业后把过去学期的方案也解释成新专业方案。
    """
    from .academic_affairs_student_fact_service import resolve_student_academic_fact

    if not student or not getattr(student, "id", None):
        return ProgramResolution(None, None, "MISSING", "NO_STUDENT", "学生不存在，无法解析培养方案")
    resolved_at = _naive_utc(as_of)
    if resolved_at is None:
        return ProgramResolution(
            None,
            None,
            "MISSING",
            "ACADEMIC_FACT_AS_OF_REQUIRED",
            "历史培养方案解析必须提供有效 as_of 时点",
        )
    fact = resolve_student_academic_fact(
        db,
        int(student.id),
        as_of=resolved_at,
        required=False,
    )
    if fact is None:
        return ProgramResolution(
            None,
            None,
            "MISSING",
            "ACADEMIC_FACT_MISSING",
            "该历史时点没有可证明的学生学籍事实，禁止按当前主档猜培养方案",
        )
    if int(getattr(fact, "tenant_id", 0) or 0) != int(tenant_id):
        return ProgramResolution(
            None,
            None,
            "MISSING",
            "ACADEMIC_FACT_TENANT_MISMATCH",
            "历史学籍事实不属于当前租户，禁止解析培养方案",
        )
    return resolve_student_program(
        db,
        fact,
        tenant_id=int(tenant_id),
        as_of=resolved_at,
    )


def credit_requirement_payload(db, student, *, tenant_id: int, earned_credits=0, as_of=None) -> dict:
    """把培养方案解析结果转换为所有学分页面共用的正式合同。

    未解析时 ``requiredCredits`` / ``missingCredits`` 必须为 ``None``，
    禁止使用学校无依据的默认学分或把未知解释为通过。
    历史 ``as_of`` 请求必须先消费 StudentAcademicFact。
    """
    if as_of is not None:
        resolution = resolve_student_program_at(
            db, student, tenant_id=int(tenant_id), as_of=as_of
        )
    else:
        resolution = resolve_student_program(
            db, student, tenant_id=int(tenant_id), as_of=None
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

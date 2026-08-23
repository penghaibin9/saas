"""就业去向核验的单一 domain 命令（V3 施工手册 TP-E02 / TP-E04）。

为什么需要这个模块
────────────────────────────────────────────────────────────
PR #183 之后，同一个 canonical 状态 `EmpStudent.verify_status = VERIFIED`
存在两条到达路径，证据门槛却完全不同：

- 教师小程序：独立核验命令，要求「已审核通过的材料 + 正式 FileBinding +
  安全扫描通过」，带 expectedVersion 乐观锁与审计。
- 教师 PC：只要材料审核通过就顺带置 VERIFIED，哪怕那份材料只有一个历史
  `file_name` 文本，没有任何正式文件、没有扫描记录。

同一所学校、同一名学生，老师用哪个端操作决定了证据强度——这正是端间事实
分叉。本模块把「核验的业务规则」收敛成唯一实现：状态机、证据门槛、乐观锁、
审计全部在这里，两个端共用。

授权边界（重要）
────────────────────────────────────────────────────────────
**本模块不做授权判定。** 教师 PC 与教师小程序各有自己的数据范围权威
（PC 走 `employment_runtime_service._assert_emp_student` → affairs context；
小程序走 `teacher_mobile_employment_service._scope_emp` →
`resolve_teacher_scope`），两套口径不能互相顶替——把其中一套套用到另一个端，
就会出现误放行或误拒绝。

所以调用方必须**先用本端自己的权威完成授权**，再把已授权的 `EmpStudent`
实例传进来。本模块只负责业务规则，不碰"这个人能不能看这条记录"。
"""
from __future__ import annotations

from typing import Any

from app.core.exceptions import AppException
from app.modules.employment.services import employment_material_evidence_service as evidence
from app.modules.employment.services import employment_service as base

VERIFY = "VERIFY"
RETURN = "RETURN"
_ACTIONS = frozenset({VERIFY, RETURN})

#: 核验退回必须给出可执行的补正意见，与 #183 教师端口径一致。
_MIN_RETURN_COMMENT = 5


def count_formal_approved_materials(db, emp) -> int:
    """该学生有多少份「已审核通过且构成正式证据」的材料。

    这是核验的证据门槛：材料 APPROVED 只说明老师看过并认可，
    正式证据还要求文件真实存在、完成正式绑定、安全扫描放行。
    """
    from sqlalchemy import select
    from app.models import EmpMaterial
    from app.services.db_service import _tid

    materials = db.scalars(select(EmpMaterial).where(
        EmpMaterial.tenant_id == _tid(),
        EmpMaterial.emp_student_id == emp.id,
        EmpMaterial.is_deleted.is_(False),
    )).all()
    facts = evidence.resolve_evidence(db, [m.id for m in materials])
    return sum(
        1 for m in materials
        if str(m.status or "").upper() == "APPROVED"
        and (facts.get(int(m.id)) or {}).get("formal")
    )


def material_is_formal_evidence(db, material) -> bool:
    """单份材料是否构成正式证据（供材料审核路径判断能否顺带完成核验）。"""
    fact = evidence.resolve_evidence(db, [material.id]).get(int(material.id)) or {}
    return bool(fact.get("formal"))


def assert_expected_version(emp, expected: Any) -> None:
    """去向核验的乐观锁；与 #183 教师端同一语义。"""
    if expected is None:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，去向核验必须携带版本号")
    try:
        expected_int = int(expected)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须为整数")
    if int(emp.version or 0) != expected_int:
        raise AppException("DATA_CONFLICT", "去向核验数据已变化，请刷新后重试", http_status=409)


def review(db, emp, *, action: str, comment: str = "", expected_version: Any = None) -> dict:
    """执行去向核验 / 退回补正。

    调用方必须传入**已由本端权威授权**的 `EmpStudent`（见模块 docstring），
    并自行负责事务提交——本函数只改内存态并写审计，不 commit，
    这样调用方可以把核验与其他写操作放进同一个事务。
    """
    action = str(action or "").upper()
    text = str(comment or "").strip()
    if action not in _ACTIONS:
        raise AppException("VALIDATION_ERROR", "非法核验动作")
    if action == RETURN and len(text) < _MIN_RETURN_COMMENT:
        raise AppException("VALIDATION_ERROR",
                           f"退回必须填写不少于 {_MIN_RETURN_COMMENT} 字的可执行补正意见")

    assert_expected_version(emp, expected_version)
    before = str(emp.verify_status or "PENDING_VERIFY").upper()

    if action == VERIFY:
        if str(emp.destination_type or "").upper() == "UNEMPLOYED":
            raise AppException("DATA_CONFLICT", "未就业学生没有可核验去向", http_status=409)
        if before == "VERIFIED":
            raise AppException("DATA_CONFLICT", "该去向已经核验通过，请刷新", http_status=409)
        if count_formal_approved_materials(db, emp) <= 0:
            raise AppException(
                "DATA_CONFLICT",
                "至少需要 1 份已审核通过且具有正式 FileBinding 的安全材料才能核验通过",
                http_status=409,
            )
        after = "VERIFIED"
    else:
        if before == "RETURNED":
            raise AppException("DATA_CONFLICT", "该去向已退回补正，请等待学生更新材料", http_status=409)
        after = "RETURNED"

    emp.verify_status = after
    emp.version = int(emp.version or 0) + 1
    base._audit(db, "VERIFICATION", emp.id,
                "去向核验通过" if action == VERIFY else "去向核验退回",
                text, before, after)
    return {
        "verificationId": str(emp.id),
        "status": after,
        "version": int(emp.version or 0),
    }

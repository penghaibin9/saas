"""
统一权限执行层（后端唯一入口）—— permissionCode / 超管判定 / 模块授权。
────────────────────────────────────────────────────────────
背景（见系统管理中心只读审查 P0-3 / P1-11）：
- 此前全后端约 913/926 端点仅有身份门禁（require_staff 只拦学生），无任何 permissionCode 级校验；
- "超级管理员/管理员" 判定散落在 ≥4 处、常量与机制各异；
- 唯一的 /authz/check 是"默认放行"装饰件。

本模块收敛为单一入口，默认拒绝（fail-closed）：
- is_super_admin(user)            集中式超管判定（替换散落判断）
- has_permission(user, code)      纯判定，不抛异常
- enforce_permission(user, code)  命令式校验（不嵌套 Depends，抛 403 + 写审计），供既有端点内联复用
- require_permission(code)         FastAPI 依赖工厂（供新端点声明式挂载）
- require_any_permission(*codes)   任一命中即放行
- require_module(module_key)       模块授权门禁（DB 模式 fail-closed）

角色→permissionCode 授予集当前为集中式内置表（替换散落硬编码，命名对齐 CLAUDE.md §10：
module.domain.action）。真实接库后 _granted() 优先查 t_role_permission，未命中再回落本表——
调用点与端点声明无需再改。
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Depends

from app.core.exceptions import no_permission
from app.core.security import get_current_user

PLATFORM_SUPER_ADMIN = "PLATFORM_SUPER_ADMIN"

# 角色 → 授予的 permissionCode 模式集合。支持三种模式：
#   "*"                              全部放行（平台超管 / 学校管理员本校全权；接库后按 t_role_permission 收敛）
#   "studentAffairs.*" / "audit.*"   前缀通配（"a.b.*" 命中 "a.b.xxx"）
#   "academicAffairs.grade.publish"  精确匹配
# 未登记的角色一律得到空集（默认拒绝）。数据范围（本人/班级/学院…）不在此裁定，由 scope 解析器另行收敛。
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "PLATFORM_SUPER_ADMIN": {"*"},
    "SCHOOL_ADMIN": {"*"},                       # 学校管理员：本校全权（接库后再按需收敛）
    "SYS_ADMIN": {"systemAdmin.*", "audit.*"},
    "SECURITY_AUDITOR": {"audit.*", "systemAdmin.audit.*", "campusService.audit.view"},
    "LEADER": {"audit.view", "*.view", "*.stat"},  # 校/院领导：只读驾驶舱（含 campusService.*.view）
    "COLLEGE_ADMIN": {"studentAffairs.*", "academicAffairs.*", "campusService.*", "audit.view"},  # 本院（范围另行收敛）
    "ACADEMIC_TEACHER": {"academicAffairs.*"},
    "STUDENT_AFFAIRS": {"studentAffairs.*", "campusService.*"},
    "STUDENT_AFFAIRS_ADMIN": {"studentAffairs.*", "campusService.*", "audit.view"},  # 学工处管理员：全校学工+在校服务（心理原始明细默认不可见，由风险/心理模块按角色遮蔽）
    "PSYCHOLOGY_TEACHER": {"studentAffairs.risk.*", "studentAffairs.talk.*", "studentAffairs.stats.view",
                           "studentAffairs.archive.psySensitive", "studentAffairs.student.view"},  # 心理老师：数据范围限授权学生(PSY_STUDENT)
    "DORM_MANAGER": {"studentAffairs.dorm.*", "campusService.dorm.*"},  # 宿管：仅宿舍域（数据范围限负责楼栋 DORM_BUILDING）；不得见学业/心理/困难/处分
    # 辅导员：数据范围限本人所带班级（服务层 _allowed_class_ids/scope 收敛，越权返回 NO_DATA_SCOPE）。
    # 本班范围内广读 + 操作 班级/请假/风险/谈话/家校；困难/资助/违纪的正式审批与登记归学工处/院，辅导员默认只读。
    "COUNSELOR": {
        "studentAffairs.dashboard.view",
        "studentAffairs.class.view", "studentAffairs.class.create", "studentAffairs.class.cadre.manage",
        "studentAffairs.student.view",
        "studentAffairs.leave.*", "studentAffairs.risk.*", "studentAffairs.talk.*",
        "studentAffairs.homeSchool.*",
        "studentAffairs.aid.view", "studentAffairs.funding.view", "studentAffairs.discipline.view",
        "studentAffairs.archive.view", "studentAffairs.stats.view",
        # 旧「在校服务」面：本班范围广读 + 请假审批；资助/违纪/工单/学生台账写操作归学工处/院
        "campusService.dashboard.view", "campusService.student.view", "campusService.leave.*",
        "campusService.dorm.view", "campusService.grant.view", "campusService.discipline.view",
        "campusService.workOrder.view",
    },
    "GD_MENTOR": {"graduationDesign.guide.*"},
    "INTERN_MENTOR": {"internship.guide.*"},
    "EMPLOYMENT_TEACHER": {"employment.*"},
    "STAFF": set(),      # 最小权限兜底（未分配角色的真实账号，对齐 P0-2 修复）
    "STUDENT": set(),    # 学生走移动端本人端点，不进 PC 管理端
}


def _role_of(user: dict) -> str:
    return (user.get("currentRoleCode") or user.get("userType") or "").strip()


def is_super_admin(user: dict) -> bool:
    """集中式平台超管判定（替换 platform.py / student_portal_admin.py 等散落判断）。"""
    return _role_of(user) == PLATFORM_SUPER_ADMIN or user.get("userType") == PLATFORM_SUPER_ADMIN


def _granted(role: str) -> set[str]:
    """角色授予的 permissionCode 集合。接库钩子：DB 模式可在此优先查 t_role_permission。"""
    return ROLE_PERMISSIONS.get(role, set())


def _match(code: str, patterns: Iterable[str]) -> bool:
    for p in patterns:
        if p == "*" or code == p:
            return True
        if p.endswith(".*") and (code == p[:-2] or code.startswith(p[:-1])):  # "a.b.*" → "a.b" / "a.b.x"
            return True
        if p.startswith("*.") and code.endswith(p[1:]):                        # "*.view" → "x.view"
            return True
    return False


def has_permission(user: dict, code: str) -> bool:
    """纯判定：当前身份是否拥有指定 permissionCode。默认拒绝。"""
    if is_super_admin(user):
        return True
    return _match(code, _granted(_role_of(user)))


def _audit_denied(user: dict, code: str) -> None:
    try:  # 审计绝不阻塞主流程
        from app.services import audit_log
        audit_log.record("PERMISSION_DENIED", f"perm:{code}",
                         detail={"role": _role_of(user), "userId": user.get("userId"), "code": code},
                         result="DENIED")
    except Exception:  # noqa: BLE001
        pass


def enforce_permission(user: dict, code: str) -> dict:
    """命令式校验（不嵌套 Depends）：无权限则 403 + 写拒绝审计。供既有端点在函数体内内联调用。"""
    if not has_permission(user, code):
        _audit_denied(user, code)
        raise no_permission(f"无权限执行该操作（{code}）")
    return user


def require_permission(code: str):
    """FastAPI 依赖工厂：新端点声明式挂载 —— Depends(require_permission("module.domain.action"))。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        return enforce_permission(user, code)
    return _dep


def require_any_permission(*codes: str):
    """任一 permissionCode 命中即放行。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if is_super_admin(user) or any(has_permission(user, c) for c in codes):
            return user
        _audit_denied(user, "|".join(codes))
        raise no_permission("无权限执行该操作")
    return _dep


def require_module(module_key: str):
    """模块授权门禁：DB 模式下未授权租户 fail-closed 403；DB 未启用（mock 演示态）不阻断。"""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        from app.db.session import db_enabled
        if not db_enabled():
            return user  # mock 演示态：模块授权 DB 未启用，不误伤演示
        if is_super_admin(user):
            return user
        from app.core.context import current_tenant_id
        from app.services.platform_service import feature_enabled
        tid = current_tenant_id()
        if tid and not feature_enabled(int(tid), module_key):
            try:
                from app.services import audit_log
                audit_log.record("MODULE_DENIED", f"module:{module_key}", result="DENIED")
            except Exception:  # noqa: BLE001
                pass
            raise no_permission(f"该模块未授权：{module_key}")
        return user
    return _dep

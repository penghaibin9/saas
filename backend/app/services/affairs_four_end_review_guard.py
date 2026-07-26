"""学工四端兼容层的二次安全门。

现有 ``affairs_four_end_contract`` 为避免大范围改动，通过运行时兼容层把移动端
请求接回既有核心服务。本文件收紧以下边界：

1. 服务函数已经显式收到 version 时，请求上下文不得偷换成数据库最新或其他值；
2. 教师移动端新增写接口未登记 permissionCode 时默认拒绝；
3. 心理统计、个体名单、个体明细权限严格分离；
4. 学生身份只在明确的本人宿舍房源 GET 路径中放开房源读取。
"""
from __future__ import annotations

from app.core.exceptions import AppException, no_permission

_INSTALLED = False


def _same_version(left, right) -> bool:
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def _expected_version(contract, explicit):
    path = contract.request_path()
    method = contract._REQUEST_METHOD.get()
    if contract._is_affairs_mobile_path(path) and method not in ("GET", "HEAD", "OPTIONS"):
        requested = contract.request_version()
        if explicit is None:
            return requested
        if requested is not None and not _same_version(explicit, requested):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "请求版本与业务参数不一致，请刷新后重新操作",
            )
    return explicit


def _install_version_guard(contract) -> None:
    from app.core import exceptions as exc_mod
    from app.core import optimistic_lock

    base_atomic = contract._ORIGINALS.get("atomic_claim_version")
    base_check = contract._ORIGINALS.get("check_version")
    if not base_atomic or not base_check:
        raise RuntimeError("学工四端乐观锁兼容层尚未初始化")

    def atomic_claim_version(db, entity, expected_version):
        return base_atomic(db, entity, _expected_version(contract, expected_version))

    def check_version(current_version, expected_version):
        return base_check(current_version, _expected_version(contract, expected_version))

    optimistic_lock.atomic_claim_version = atomic_claim_version
    exc_mod.check_version = check_version

    modules = (
        "affairs_leave_service", "affairs_aid_service", "affairs_funding_service",
        "affairs_discipline_service", "affairs_dorm_service", "affairs_risk_service",
        "affairs_mental_service", "affairs_talk_service", "affairs_activity_service",
        "affairs_club_service", "affairs_org_service", "affairs_league_service",
        "affairs_archive_service", "affairs_counselor_service",
    )
    for name in modules:
        module = __import__(f"app.services.{name}", fromlist=[name])
        if hasattr(module, "atomic_claim_version"):
            module.atomic_claim_version = atomic_claim_version
        if hasattr(module, "check_version"):
            module.check_version = check_version


def _install_permission_guard(contract) -> None:
    original = contract._teacher_permissions

    def teacher_permissions(path: str, method: str) -> tuple[str, ...]:
        method = method.upper()
        write = method not in ("GET", "HEAD", "OPTIONS")
        if path == "/api/v1/mobile/teacher/mental-stats":
            return ("studentAffairs.stats.view",)
        if path == "/api/v1/mobile/teacher/mental" or path.startswith("/api/v1/mobile/teacher/mental/"):
            if write:
                return ("studentAffairs.mental.manage",)
            return ("studentAffairs.risk.psyDetail.view",)

        required = original(path, method)
        if (
            write
            and path.startswith("/api/v1/mobile/teacher/affairs")
            and required == ("studentAffairs.dashboard.view",)
        ):
            # 未来新增教师移动写端点如果没有登记权限，不得继承总览查看权限。
            return ("__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__",)
        return required

    contract._teacher_permissions = teacher_permissions


def _install_student_dorm_guard(contract) -> None:
    from app.services import affairs_dorm_service as dorm

    original = contract._ORIGINALS.get("dorm_scope_building_ids")
    if not original:
        raise RuntimeError("学工宿舍范围兼容层尚未初始化")

    allowed_get_prefixes = (
        "/api/v1/mobile/affairs/dorm/select-options",
        "/api/v1/mobile/affairs/dorm/buildings/",
        "/api/v1/mobile/affairs/dorm/rooms/",
        "/api/v1/mobile/affairs/dorm/transfer-options",
        "/api/v1/mobile/affairs/dorm/transfer-buildings/",
        "/api/v1/mobile/affairs/dorm/transfer-rooms/",
    )

    def dorm_scope_building_ids(db, user):
        if (user or {}).get("userType", "").upper() != "STUDENT":
            return original(db, user)
        path = contract.request_path()
        method = contract._REQUEST_METHOD.get()
        if method == "GET" and any(path.startswith(prefix) for prefix in allowed_get_prefixes):
            return None
        raise no_permission("学生身份无权通过该入口读取宿舍管理范围")

    dorm._dorm_scope_building_ids = dorm_scope_building_ids


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_four_end_contract as contract

    _install_version_guard(contract)
    _install_permission_guard(contract)
    _install_student_dorm_guard(contract)
    _INSTALLED = True

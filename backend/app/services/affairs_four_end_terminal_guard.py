"""学工中心四端终态安全门。

该模块只收紧四端补充接线层，不修改教务、实习、毕设等业务：

1. 所有学生本人补充接口必须先验证 ``userType=STUDENT``，再解析本人主档；
2. 教师移动端除学工总览外，未知读写接口全部 fail-closed；
3. 启动时机械遍历教师学工、谈话、心理移动路由，校验权限码存在且写操作不借用查看权限；
4. 心理统计、个体名单和个体明细严格使用不同 permissionCode。

必须在其他学工四端兼容层全部安装后最后调用 ``install(api_router)``。
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.core.exceptions import no_permission
from app.core.student_affairs_permission_registry import (
    STUDENT_AFFAIRS_MOBILE_DIRECT_PERMISSIONS,
    STUDENT_AFFAIRS_PERMISSION_CODES,
)

_INSTALLED = False
_SENTINEL = "__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__"  # 兼容既有测试名，实际覆盖未知读写
_API_PREFIX = "/api/v1"
_DASHBOARD_PATHS = {
    "/api/v1/mobile/teacher/affairs",
    "/api/v1/mobile/teacher/affairs/",
}
_TEACHER_PREFIXES = (
    "/api/v1/mobile/teacher/affairs",
    "/api/v1/mobile/teacher/talk",
    "/api/v1/mobile/teacher/mental",
)

_MOBILE_CATALOG_CODES = STUDENT_AFFAIRS_PERMISSION_CODES


# 以下端点在自身 Depends/函数体内执行更精确的业务分支校验。这里记录其真实 PC 权限，
# 运行时先做同源预检，端点内再按 purpose/kind 做最终校验，禁止退化成 dashboard.view。
_DIRECT_PERMISSION_CODES = STUDENT_AFFAIRS_MOBILE_DIRECT_PERMISSIONS


def _strict_self_student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    student = resolve_student(db, current)
    if not student:
        raise no_permission("尚未建立你的学生档案")
    return student


def _install_student_identity_guard() -> None:
    from app.api.v1 import affairs_four_end

    affairs_four_end._self_student = _strict_self_student


def _is_teacher_mobile_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _TEACHER_PREFIXES)


def _is_read_only_code(code: str) -> bool:
    return code.endswith(".view") or code == "studentAffairs.stats.view"


def _path_template_matches(template: str, path: str) -> bool:
    """匹配 FastAPI 路由模板与真实请求路径，不把参数值误当成未登记接口。"""
    t_parts = str(template or "").strip("/").split("/")
    p_parts = str(path or "").strip("/").split("/")
    if len(t_parts) != len(p_parts):
        return False
    return all(
        (part.startswith("{") and part.endswith("}")) or part == actual
        for part, actual in zip(t_parts, p_parts)
    )


def _direct_permission_codes(path: str) -> tuple[str, ...] | None:
    for template, codes in _DIRECT_PERMISSION_CODES.items():
        if _path_template_matches(template, path):
            return codes
    return None


def _permission_problem(path: str, method: str, required: tuple[str, ...]) -> str | None:
    if not required or _SENTINEL in required:
        return "未登记权限"
    # dashboard.view 只允许两个总览路由使用。其他教师移动路径若仍回落到总览权限，
    # 说明新增接口没有登记真实业务权限；读写一律 fail-closed。
    if path not in _DASHBOARD_PATHS and required == ("studentAffairs.dashboard.view",):
        return "未登记权限"
    unknown = sorted(set(required) - _MOBILE_CATALOG_CODES)
    if unknown:
        return "权限码未进入PC目录:" + ",".join(unknown)
    write = method not in ("GET", "HEAD", "OPTIONS")
    if write and all(_is_read_only_code(code) for code in required):
        return "写操作错误复用查看权限"
    if path == "/api/v1/mobile/teacher/mental-stats" and required != (
        "studentAffairs.stats.view",
    ):
        return "心理统计权限不准确"
    if (
        (path == "/api/v1/mobile/teacher/mental" or path.startswith("/api/v1/mobile/teacher/mental/"))
        and method == "GET"
        and required != ("studentAffairs.risk.psyDetail.view",)
    ):
        return "心理个体明细权限不准确"
    return None


def _install_permission_fail_closed() -> None:
    from app.services import affairs_four_end_contract as contract

    previous = contract._teacher_permissions

    def teacher_permissions(path: str, method: str) -> tuple[str, ...]:
        required = tuple(previous(path, method) or ())
        if not _is_teacher_mobile_path(path):
            return required
        if path in _DASHBOARD_PATHS:
            return required
        direct = _direct_permission_codes(path)
        if direct is not None:
            return direct
        if _permission_problem(path, str(method or "GET").upper(), required):
            return (_SENTINEL,)
        return required

    contract._teacher_permissions = teacher_permissions


def _runtime_path(route_path: str) -> str:
    path = str(route_path or "")
    if path.startswith(_API_PREFIX + "/"):
        return path
    if path.startswith("/"):
        return _API_PREFIX + path
    return _API_PREFIX + "/" + path


def _assert_teacher_routes_registered(api_router) -> None:
    from app.services import affairs_four_end_contract as contract

    failures: list[str] = []
    seen_paths: set[str] = set()
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = _runtime_path(str(route.path))
        if not _is_teacher_mobile_path(path):
            continue
        seen_paths.add(path)
        for method in set(route.methods or ()):
            method = str(method).upper()
            if method in ("HEAD", "OPTIONS"):
                continue
            direct = _direct_permission_codes(path)
            required = direct if direct is not None else tuple(contract._teacher_permissions(path, method) or ())
            problem = _permission_problem(path, method, required)
            if problem:
                failures.append(f"{method} {path}: {problem}")

    stale = sorted(set(_DIRECT_PERMISSION_CODES) - seen_paths)
    failures.extend(f"STALE {path}: 直接权限登记无对应路由" for path in stale)

    if failures:
        raise RuntimeError("教师学工移动权限矩阵不一致: " + "; ".join(sorted(set(failures))))


def _assert_teacher_write_routes_registered(api_router) -> None:
    _assert_teacher_routes_registered(api_router)


def install(api_router) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _install_student_identity_guard()
    _install_permission_fail_closed()
    _assert_teacher_routes_registered(api_router)
    _INSTALLED = True

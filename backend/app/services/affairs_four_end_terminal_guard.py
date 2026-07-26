"""学工中心四端终态安全门。

该模块只收紧四端补充接线层，不修改教务、实习、毕设等业务：

1. 所有学生本人补充接口必须先验证 ``userType=STUDENT``，再解析本人主档；
2. 教师移动端除总览外，未知读写接口都必须 fail-closed；
3. 对全部教师学工移动路由做启动期机械检查，避免后续新增接口遗漏权限登记。

必须在其他学工四端兼容层全部安装后最后调用 ``install(api_router)``。
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.core.exceptions import no_permission

_INSTALLED = False
_SENTINEL = "__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__"
_API_PREFIX = "/api/v1"
_DASHBOARD_PATHS = {
    "/api/v1/mobile/teacher/affairs",
    "/api/v1/mobile/teacher/affairs/",
}
# 以下端点在自身 Depends/函数体内执行了明确、可审计的 permissionCode 校验，
# 因业务类型是动态 path 参数或要求多权限联合校验，不能由统一静态映射表达。
_DIRECT_PERMISSION_PATHS = {
    "/api/v1/mobile/teacher/affairs/student-candidates",
    "/api/v1/mobile/teacher/affairs/activities/ongoing",
    "/api/v1/mobile/teacher/affairs/activities/{activity_id}/checkin-token",
    "/api/v1/mobile/teacher/affairs/appeals/{kind}",
    "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review",
    "/api/v1/mobile/teacher/affairs/appeals/repair",
}


def _strict_self_student(db, user):
    """只允许当前登录学生解析本人主档，教师/管理员不得借绑定字段进入本人接口。"""
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    student = resolve_student(db, current)
    if not student:
        raise no_permission("尚未建立你的学生档案")
    return student


def _install_student_identity_guard() -> None:
    """覆盖四端新增 API 中唯一遗漏学生身份前置校验的 helper。"""
    from app.api.v1 import affairs_four_end

    affairs_four_end._self_student = _strict_self_student


def _install_permission_fail_closed() -> None:
    """未知教师学工移动路由不得退化成总览查看权限。"""
    from app.services import affairs_four_end_contract as contract

    previous = contract._teacher_permissions

    def teacher_permissions(path: str, method: str) -> tuple[str, ...]:
        required = previous(path, method)
        if path.startswith("/api/v1/mobile/teacher/affairs") and path not in _DASHBOARD_PATHS:
            if not required or required == ("studentAffairs.dashboard.view",):
                return (_SENTINEL,)
        return required

    contract._teacher_permissions = teacher_permissions


def _runtime_path(route_path: str) -> str:
    """把 ``api_router`` 内的子路由路径归一化成真实请求路径。"""
    path = str(route_path or "")
    if path.startswith(_API_PREFIX + "/"):
        return path
    if path.startswith("/"):
        return _API_PREFIX + path
    return _API_PREFIX + "/" + path


def _assert_teacher_routes_registered(api_router) -> None:
    """启动期检查全部教师学工移动路由（读写均覆盖）。

    端点自身已执行明确权限校验的路径列入有限白名单；其他路径必须由统一映射返回
    非总览的准确 permissionCode。未知路由直接阻止应用启动，避免静默越权上线。
    """
    from app.services import affairs_four_end_contract as contract

    failures: list[str] = []
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = _runtime_path(str(route.path))
        if not path.startswith("/api/v1/mobile/teacher/affairs"):
            continue
        if path in _DIRECT_PERMISSION_PATHS:
            continue
        for method in set(route.methods or ()):
            method = str(method).upper()
            if method in ("HEAD", "OPTIONS"):
                continue
            required = contract._teacher_permissions(path, method)
            if not required or _SENTINEL in required:
                failures.append(f"{method} {path}")
    if failures:
        joined = ", ".join(sorted(set(failures)))
        raise RuntimeError(f"教师学工移动接口缺少权限登记: {joined}")


def _assert_teacher_write_routes_registered(api_router) -> None:
    """兼容旧测试/调用名，实际已升级为全部读写路由检查。"""
    _assert_teacher_routes_registered(api_router)


def install(api_router) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _install_student_identity_guard()
    _install_permission_fail_closed()
    _assert_teacher_routes_registered(api_router)
    _INSTALLED = True

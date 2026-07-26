"""学工中心四端终态安全门。

该模块只收紧四端补充接线层，不修改教务、实习、毕设等业务：

1. 所有学生本人补充接口必须先验证 ``userType=STUDENT``，再解析本人主档；
2. 教师移动写接口的权限映射未知时必须 fail-closed；
3. 对新增教师移动写路由做启动期机械检查，避免后续新增接口遗漏权限登记。

必须在其他学工四端兼容层全部安装后最后调用 ``install(api_router)``。
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.core.exceptions import no_permission

_INSTALLED = False
_SENTINEL = "__AFFAIRS_MOBILE_WRITE_NOT_REGISTERED__"
_API_PREFIX = "/api/v1"


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
    """最终收紧教师移动权限映射，未知写路径绝不能退化为总览查看权限。"""
    from app.services import affairs_four_end_contract as contract

    previous = contract._teacher_permissions

    def teacher_permissions(path: str, method: str) -> tuple[str, ...]:
        required = previous(path, method)
        write = str(method or "GET").upper() not in ("GET", "HEAD", "OPTIONS")
        if write and path.startswith("/api/v1/mobile/teacher/affairs"):
            if not required or required == ("studentAffairs.dashboard.view",):
                return (_SENTINEL,)
        return required

    contract._teacher_permissions = teacher_permissions


def _runtime_path(route_path: str) -> str:
    """把 ``api_router`` 内的子路由路径归一化成真实请求路径。

    FastAPI 在子路由对象中通常保存 ``/mobile/...``，最终挂载后才成为
    ``/api/v1/mobile/...``。安全检查必须按真实路径调用权限映射，否则会静默漏检。
    """
    path = str(route_path or "")
    if path.startswith(_API_PREFIX + "/"):
        return path
    if path.startswith("/"):
        return _API_PREFIX + path
    return _API_PREFIX + "/" + path


def _assert_teacher_write_routes_registered(api_router) -> None:
    """启动期检查教师移动写路由。

    直接在端点内部按业务类型校验权限的申诉复核与补偿路由列入显式例外；其余旧
    移动路由必须能被统一权限映射识别。检查失败直接阻止应用启动，避免静默带漏洞上线。
    """
    from app.services import affairs_four_end_contract as contract

    direct_permission_paths = {
        "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review",
        "/api/v1/mobile/teacher/affairs/appeals/repair",
    }
    failures: list[str] = []
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = _runtime_path(str(route.path))
        if not path.startswith("/api/v1/mobile/teacher/affairs"):
            continue
        for method in set(route.methods or ()):
            method = str(method).upper()
            if method in ("GET", "HEAD", "OPTIONS"):
                continue
            if path in direct_permission_paths:
                continue
            required = contract._teacher_permissions(path, method)
            if not required or _SENTINEL in required:
                failures.append(f"{method} {path}")
    if failures:
        joined = ", ".join(sorted(set(failures)))
        raise RuntimeError(f"教师学工移动写接口缺少权限登记: {joined}")


def install(api_router) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _install_student_identity_guard()
    _install_permission_fail_closed()
    _assert_teacher_write_routes_registered(api_router)
    _INSTALLED = True

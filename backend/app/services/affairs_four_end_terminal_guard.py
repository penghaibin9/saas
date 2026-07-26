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

# 只列出教师移动端实际允许使用的 PC 冻结权限码。新增路由必须先进入 PC 权限目录，
# 再在统一映射或端点自身 Depends 中登记，不能临时发明近义码。
_MOBILE_CATALOG_CODES = {
    "studentAffairs.dashboard.view",
    "studentAffairs.stats.view",
    "studentAffairs.talk.view",
    "studentAffairs.talk.create",
    "studentAffairs.mental.manage",
    "studentAffairs.risk.psyDetail.view",
    "studentAffairs.homeSchool.view",
    "studentAffairs.homeSchool.record.create",
    "studentAffairs.leave.view",
    "studentAffairs.leave.approve",
    "studentAffairs.leave.cancelLeaveConfirm",
    "studentAffairs.leave.overdue.handle",
    "studentAffairs.leave.extension.approve",
    "studentAffairs.aid.view",
    "studentAffairs.aid.approve",
    "studentAffairs.aid.counselorReview",
    "studentAffairs.funding.view",
    "studentAffairs.funding.approve",
    "studentAffairs.funding.publicity.manage",
    "studentAffairs.discipline.view",
    "studentAffairs.discipline.approve",
    "studentAffairs.discipline.appeal.review",
    "studentAffairs.risk.view",
    "studentAffairs.risk.handle",
    "studentAffairs.risk.close",
    "studentAffairs.dorm.view",
    "studentAffairs.dorm.allocation.manage",
    "studentAffairs.dorm.transfer.approve",
    "studentAffairs.dorm.exception.handle",
    "studentAffairs.class.view",
    "studentAffairs.class.create",
    "studentAffairs.class.cadre.manage",
    "studentAffairs.activity.publish",
    "studentAffairs.activity.confirm",
}

# 以下端点在自身 Depends/函数体内执行明确 permissionCode 校验。这里记录其真实代码，
# 启动检查仍会验证这些代码属于 PC 权限目录，而不是简单跳过。
_DIRECT_PERMISSION_CODES: dict[str, tuple[str, ...]] = {
    "/api/v1/mobile/teacher/affairs/student-candidates": (
        "studentAffairs.talk.create",
        "studentAffairs.mental.manage",
        "studentAffairs.risk.psyDetail.view",
    ),
    "/api/v1/mobile/teacher/affairs/activities/ongoing": (
        "studentAffairs.activity.publish",
    ),
    "/api/v1/mobile/teacher/affairs/activities/{activity_id}/checkin-token": (
        "studentAffairs.activity.publish",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/{kind}": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/repair": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
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
    from app.api.v1 import affairs_four_end

    affairs_four_end._self_student = _strict_self_student


def _is_teacher_mobile_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _TEACHER_PREFIXES)


def _is_read_only_code(code: str) -> bool:
    return code.endswith(".view") or code == "studentAffairs.stats.view"


def _permission_problem(path: str, method: str, required: tuple[str, ...]) -> str | None:
    if not required or _SENTINEL in required:
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
    """未知路由、近义权限和写操作借用查看权限均不得通过。"""
    from app.services import affairs_four_end_contract as contract

    previous = contract._teacher_permissions

    def teacher_permissions(path: str, method: str) -> tuple[str, ...]:
        required = tuple(previous(path, method) or ())
        if not _is_teacher_mobile_path(path):
            return required
        if path in _DASHBOARD_PATHS:
            return required
        if path in _DIRECT_PERMISSION_CODES:
            return required
        if _permission_problem(path, str(method or "GET").upper(), required):
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
    """启动期完整检查教师学工移动路由的PC权限一致性。"""
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
            if path in _DIRECT_PERMISSION_CODES:
                problem = _permission_problem(path, method, _DIRECT_PERMISSION_CODES[path])
            else:
                problem = _permission_problem(path, method, tuple(contract._teacher_permissions(path, method) or ()))
            if problem:
                failures.append(f"{method} {path}: {problem}")

    # 明确登记的端点若已从路由中删除，也应让测试/启动暴露陈旧矩阵，而不是长期漂移。
    stale = sorted(set(_DIRECT_PERMISSION_CODES) - seen_paths)
    failures.extend(f"STALE {path}: 直接权限登记无对应路由" for path in stale)

    if failures:
        raise RuntimeError("教师学工移动权限矩阵不一致: " + "; ".join(sorted(set(failures))))


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

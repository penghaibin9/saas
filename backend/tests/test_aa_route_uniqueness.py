"""教务扩展 Router 必须使用独立路径，不得靠注册顺序覆盖旧接口。"""
from collections import defaultdict

from fastapi.routing import APIRoute

from app.api.v1.router import api_router


ACADEMIC_PREFIXES = (
    "/academic-affairs",
    "/academic/",
    "/portal/academic/",
    "/mobile/academic/",
    "/mobile/teacher/academic/",
    "/teacher/academic/",
)


def _is_academic_path(path: str) -> bool:
    return path == "/academic-affairs" or path.startswith(ACADEMIC_PREFIXES)


def test_academic_routes_have_unique_method_and_path():
    owners = defaultdict(list)
    for route in api_router.routes:
        if not isinstance(route, APIRoute) or not _is_academic_path(route.path):
            continue
        for method in sorted(route.methods or set()):
            owners[(method, route.path)].append(route.name)

    duplicates = {
        f"{method} {path}": names
        for (method, path), names in owners.items()
        if len(names) > 1
    }
    assert not duplicates, f"教务路由存在重复注册，禁止依赖先后顺序抢占：{duplicates}"


def test_academic_extension_routes_keep_module_dependency():
    # FastAPI 将 Router 级 Depends 合并到每条 APIRoute；新增教务扩展不得裸注册。
    unguarded = []
    for route in api_router.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/academic-affairs"):
            continue
        if not route.dependant.dependencies:
            unguarded.append(f"{','.join(sorted(route.methods or set()))} {route.path}")
    assert not unguarded, f"教务接口缺少模块/身份依赖：{unguarded}"

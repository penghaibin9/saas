"""教务统计 08/09/14 唯一运行 Owner 调用关系防回归。

这组测试不执行业务数据库，只锁定源码调用关系：
Router -> public service -> canonical contract facade -> legacy shared helpers。
后续删除 stats_service 历史重复实现时，禁止把真实 HTTP 入口重新指回 legacy 同名函数。
"""
from __future__ import annotations

import ast
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SERVICES = BACKEND / "app/modules/academic_affairs/services"
ROUTERS = BACKEND / "app/modules/academic_affairs/routers"

CANONICAL_STATS = {
    "course_selection_stats",
    "course_selection_detail",
    "exam_stats",
    "exam_detail",
    "resource_stats",
    "resource_detail",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, f"{name} 在 public service 中必须且只能定义一次"
    return ast.get_source_segment(source, matches[0]) or ""


def test_stats_router_only_enters_public_package_service():
    source = _read(ROUTERS / "stats_core_router.py")
    assert (
        "from app.modules.academic_affairs.services import "
        "academic_affairs_stats_service as stats_svc"
    ) in source
    assert "services.academic_affairs_stats_service import" not in source

    for name in CANONICAL_STATS:
        assert f"stats_svc.{name}(" in source


def test_public_0814_stats_delegate_to_canonical_contract():
    source = _read(SERVICES / "academic_affairs_stats_public_service.py")
    for name in CANONICAL_STATS:
        function_source = _function_source(source, name)
        assert "academic_affairs_stats_contract_facade" in function_source
        assert f"_legacy.{name}(" not in function_source


def test_canonical_facade_rebinds_all_legacy_internal_lookups():
    source = _read(SERVICES / "academic_affairs_stats_contract_facade.py")
    for name in CANONICAL_STATS:
        assert f"_legacy.{name} = {name}" in source


def test_canonical_install_happens_before_late_stats_guards():
    source = _read(SERVICES / "__init__.py")
    canonical = source.index("academic_affairs_stats_contract_facade.install()")
    scale = source.index("academic_affairs_stats_scale_guard.install()")
    detail_scale = source.index("academic_affairs_stats_detail_scale_guard.install()")
    privacy = source.index("academic_affairs_stats_privacy_guard.install()")

    assert canonical < scale
    assert canonical < detail_scale
    assert canonical < privacy


def test_no_router_directly_imports_concrete_legacy_stats_module():
    for path in ROUTERS.glob("*.py"):
        source = _read(path)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            assert not module.endswith("academic_affairs_stats_service"), (
                f"{path.name} 不得直接 import legacy stats_service；必须走包级 public service"
            )

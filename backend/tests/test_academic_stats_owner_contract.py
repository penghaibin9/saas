"""教务统计 08/09/14 唯一运行 Owner 调用关系防回归。

这组测试不执行业务数据库，只锁定真实调用关系：
Router -> package public service -> canonical contract facade -> shared legacy helpers。
后续删除 stats_service 历史重复实现时，禁止把真实 HTTP 入口重新指回 legacy 同名函数。
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
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

PUBLIC_MODULE = "app.modules.academic_affairs.services.academic_affairs_stats_public_service"
LEGACY_MODULE = "app.modules.academic_affairs.services.academic_affairs_stats_service"
CANONICAL_MODULE = "app.modules.academic_affairs.services.academic_affairs_stats_contract_facade"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, f"{name} 在 public service 中必须且只能定义一次"
    return ast.get_source_segment(source, matches[0]) or ""


def _runtime_owners() -> dict:
    script = f"""
import importlib
import json

services = importlib.import_module('app.modules.academic_affairs.services')
public = services.academic_affairs_stats_service
resolved = {{
    'packageEntry': public.__name__,
    'legacyRef': public._legacy.__name__,
    'owners': {{name: getattr(public, name).__module__ for name in {sorted(CANONICAL_STATS)!r}}},
}}
print(json.dumps(resolved, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_stats_runtime_owner_chain_is_explicit():
    """不相信变量名，直接检查 Python 启动后的真实模块对象。"""
    resolved = _runtime_owners()
    assert resolved["packageEntry"] == PUBLIC_MODULE
    assert resolved["legacyRef"] == LEGACY_MODULE
    assert set(resolved["owners"]) == CANONICAL_STATS
    assert set(resolved["owners"].values()) == {CANONICAL_MODULE}


def test_stats_router_only_enters_public_package_service():
    source = _read(ROUTERS / "stats_core_router.py")
    assert (
        "from app.modules.academic_affairs.services import "
        "academic_affairs_stats_service as stats_svc"
    ) in source
    assert "services.academic_affairs_stats_service import" not in source

    for name in CANONICAL_STATS:
        assert f"stats_svc.{name}(" in source


def test_public_0814_stats_delegate_to_canonical_contract_before_package_rebind():
    """public 源码自身也保持 canonical 委托，避免单独导入 public 时退回 legacy owner。"""
    source = _read(SERVICES / "academic_affairs_stats_public_service.py")
    for name in CANONICAL_STATS:
        function_source = _function_source(source, name)
        assert "academic_affairs_stats_contract_facade" in function_source
        assert f"_legacy.{name}(" not in function_source


def test_canonical_install_declares_all_six_package_rebinds():
    """这里只锁源码绑定声明；真实绑定对象由 runtime owner 测试裁定。"""
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


def test_other_services_may_reuse_helpers_but_not_legacy_0814_owners():
    """允许复用 scope/helper，但禁止任何 Service 按值导入 08/09/14 的旧同名业务入口。"""
    for path in SERVICES.glob("*.py"):
        if path.name == "academic_affairs_stats_service.py":
            continue
        source = _read(path)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if not module.endswith("academic_affairs_stats_service"):
                continue
            imported = {alias.name for alias in node.names}
            forbidden = imported & CANONICAL_STATS
            assert not forbidden, (
                f"{path.name} 直接 import legacy 统计 owner：{sorted(forbidden)}；"
                "应改走 public/canonical contract"
            )

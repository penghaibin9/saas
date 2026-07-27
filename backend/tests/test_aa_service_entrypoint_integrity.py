"""教务服务公开入口稳定性合同。

防止兼容层再次通过导入顺序、模块替换或 monkey patch 改写公开 Service。
该测试不访问数据库，可在完整 MySQL 用例前快速发现服务装配回归。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


EXPECTED_ENTRYPOINTS = {
    "academic_affairs_service": (
        "app.modules.academic_affairs.services.academic_affairs_dashboard_scope_facade"
    ),
    "academic_affairs_attendance_service": (
        "app.modules.academic_affairs.services.academic_affairs_attendance_public_service"
    ),
    "academic_affairs_stats_service": (
        "app.modules.academic_affairs.services.academic_affairs_stats_public_service"
    ),
    "academic_affairs_selection_service": (
        "app.modules.academic_affairs.services.academic_affairs_selection_final_service"
    ),
    "academic_affairs_scheduling_service": (
        "app.modules.academic_affairs.services.academic_affairs_scheduling_public_service"
    ),
    "academic_affairs_autoschedule_service": (
        "app.modules.academic_affairs.services.academic_affairs_autoschedule_final_service"
    ),
    "academic_affairs_schedule_service": (
        "app.modules.academic_affairs.services.academic_affairs_schedule_final_service"
    ),
    "academic_affairs_exam_service": (
        "app.modules.academic_affairs.services.academic_affairs_exam_facade"
    ),
    "academic_affairs_textbook_service": (
        "app.modules.academic_affairs.services.academic_affairs_textbook_final_facade"
    ),
    "academic_affairs_recognition_service": (
        "app.modules.academic_affairs.services.academic_affairs_recognition_public_service"
    ),
    "academic_affairs_major_split_service": (
        "app.modules.academic_affairs.services.academic_affairs_major_split_public_service"
    ),
    "mobile_academic_affairs_service": (
        "app.modules.academic_affairs.services.mobile_academic_affairs_facade"
    ),
}

IMPORT_ORDERS = [
    [],
    [
        "app.modules.academic_affairs.services.academic_affairs_service",
        "app.modules.academic_affairs.services.academic_affairs_dashboard_scope_facade",
        "app.modules.academic_affairs.services.academic_affairs_dashboard_readiness_runtime_guard",
    ],
    [
        "app.modules.academic_affairs.services.academic_affairs_attendance_service",
        "app.modules.academic_affairs.services.academic_affairs_attendance_facade",
        "app.modules.academic_affairs.services.academic_affairs_attendance_roster_identity_facade",
        "app.modules.academic_affairs.services.academic_affairs_attendance_public_service",
    ],
    [
        "app.modules.academic_affairs.services.academic_affairs_stats_service",
        "app.modules.academic_affairs.services.academic_affairs_stats_facade",
        "app.modules.academic_affairs.services.academic_affairs_stats_public_service",
    ],
    [
        "app.modules.academic_affairs.services.academic_affairs_level_exam_identity_guard",
        "app.modules.academic_affairs.services.academic_affairs_major_split_service",
        "app.modules.academic_affairs.services.academic_affairs_major_split_identity_guard",
        "app.modules.academic_affairs.services.academic_affairs_major_split_public_service",
    ],
    [
        "app.modules.academic_affairs.services.academic_affairs_exam_service",
        "app.modules.academic_affairs.services.academic_affairs_exam_term_facade",
        "app.modules.academic_affairs.services.academic_affairs_exam_roster_identity_facade",
        "app.modules.academic_affairs.services.academic_affairs_exam_facade",
    ],
    [
        "app.modules.academic_affairs.services.academic_affairs_textbook_workbench_service",
        "app.modules.academic_affairs.services.academic_affairs_textbook_term_facade",
        "app.modules.academic_affairs.services.academic_affairs_textbook_roster_facade",
        "app.modules.academic_affairs.services.academic_affairs_textbook_lock_facade",
        "app.modules.academic_affairs.services.academic_affairs_textbook_order_guard_facade",
        "app.modules.academic_affairs.services.academic_affairs_textbook_final_facade",
    ],
    [
        "app.modules.academic_affairs.services.mobile_academic_gaps_service",
        "app.modules.academic_affairs.services.mobile_academic_grade_identity_facade",
        "app.modules.academic_affairs.services.mobile_academic_grade_entry_closure_service",
        "app.modules.academic_affairs.services.mobile_academic_exam_safety_facade",
        "app.modules.academic_affairs.services.mobile_academic_affairs_facade",
    ],
]


def _resolve_entrypoints(import_order: list[str]) -> dict[str, str]:
    script = f"""
import importlib
import json

for module_name in {import_order!r}:
    importlib.import_module(module_name)

services = importlib.import_module('app.modules.academic_affairs.services')
names = {list(EXPECTED_ENTRYPOINTS)!r}
print(json.dumps({{name: getattr(services, name).__name__ for name in names}}, sort_keys=True))
"""
    backend_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_dir,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_public_service_entrypoints_do_not_depend_on_import_order():
    for import_order in IMPORT_ORDERS:
        assert _resolve_entrypoints(import_order) == EXPECTED_ENTRYPOINTS


def test_service_package_has_no_module_replacement_side_effects():
    services_dir = Path(__file__).resolve().parents[1] / "app/modules/academic_affairs/services"
    package_source = (services_dir / "__init__.py").read_text(encoding="utf-8")
    forbidden = (
        "sys.modules",
        "__dict__.update",
        "globals().update",
        "importlib.reload",
    )
    for token in forbidden:
        assert token not in package_source, f"教务服务包禁止使用导入副作用：{token}"

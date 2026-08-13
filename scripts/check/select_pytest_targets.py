#!/usr/bin/env python3
"""根据 git diff 选择最小必要 pytest 集合（CI push/PR 用）。

用法：
  python scripts/check/select_pytest_targets.py
  # 输出空格分隔的真实 pytest 文件路径，无命中时输出安全默认集合

选择原则：
- 改动过的后端测试必须原样执行；
- 业务域源码改动只拉起该域的稳定生产闸门，不用一个通配符吞下整套历史测试；
- 公共底座、模型和迁移继续执行跨域安全与迁移守卫。
"""
from __future__ import annotations

from glob import glob
import os
import subprocess
import sys


# 路径片段 → pytest 参数
RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("backend/app/core/security", "backend/app/core/permissions",
      "backend/app/middleware/context", "backend/app/core/config",
      "backend/app/api/v1/auth", "backend/app/services/auth"),
     ["tests/test_p1_tenant_readonly_guard.py", "tests/test_p1_config_guards.py",
      "tests/test_p1_tenant_context_required.py", "tests/test_portal_auth*.py"]),
    (("backend/app/services/file", "backend/app/services/storage",
      "backend/app/api/v1/file", "backend/app/models/file",
      "backend/app/services/file_content"),
     ["tests/test_file_p0_authz.py", "tests/test_p1_file_content_security.py"]),
    (("backend/app/services/import_export", "backend/app/services/domain_import",
      "backend/app/services/domain_export", "backend/app/core/import_export",
      "backend/app/api/v1/import_export", "backend/app/api/v1/transfer"),
     ["tests/test_import_export_p0_authz.py", "tests/test_import_export.py"]),
    (("backend/app/api/v1/help_metrics.py", "backend/app/services/help_metrics_service.py"),
     ["tests/test_help_metrics.py"]),
    # D2 学籍名册/注册的公开 owner 已从历史大 Router 迁出；仅靠通用教务闸门
    # 无法及时发现注册 canonical、名册更正、敏感查看或导出 compat 回归。
    # 精确命中 roster_registration（包括后续 convenience service/router）时只增加
    # 这四组稳定专项，不删通用教务权限/并发闸门。
    (("roster_registration",),
     ["tests/test_aa_registration.py",
      "tests/test_aa_roster_correction.py",
      "tests/test_student_sensitive_contract.py",
      "tests/test_academic_export_compat.py"]),
    # D5-U：排课批量导入修改 canonical final service 或 preload 取数层时，
    # 除通用教务权限/并发闸门外，必须立即跑导入语义回归 + 查询数合同。
    (("academic_affairs_schedule_final_service.py",
      "academic_affairs_schedule_import_preload.py"),
     ["tests/test_aa_schedule_import_dry_run.py",
      "tests/test_aa_schedule_import_batch_queries.py"]),
    # D5-U：冲突报告 production owner 或候选分桶索引变化时，必须同时验证
    # 原 MySQL 业务语义与 1000 ScheduleItem 大数据量合同。
    (("academic_affairs_scheduling_final_service.py",
      "academic_affairs_schedule_conflict_index.py"),
     ["tests/test_aa_scheduling.py",
      "tests/test_aa_schedule_conflict_index.py"]),
    # D6：Selection Final 真链、学院范围读侧、轮次写/读 guard 或 TeachingRoster 锁定投影
    # 任一变化，都立即跑完整状态机 + 真值 owner + MySQL 学院隔离 + 轮次并发 + 大批次锁定合同。
    (("academic_affairs_selection_final_service.py",
      "academic_affairs_selection_read_service.py",
      "academic_affairs_selection_round_service.py",
      "academic_affairs_selection_round_read_guard.py",
      "academic_affairs_teaching_roster_service.py"),
     ["tests/test_aa_selection.py",
      "tests/test_aa_d6_selection_truth_contract.py",
      "tests/test_aa_selection_read_production_contract.py",
      "tests/test_aa_selection_scope_mysql.py",
      "tests/test_aa_selection_round_concurrency.py",
      "tests/test_aa_selection_lock_scaling.py",
      "tests/test_aa_teaching_roster_unification.py"]),
    # 教务历史测试目录含尚未收口的旧契约，禁止用 test_aa_*.py 把它们全部带入。
    # 任意教务源码改动执行稳定权限闸门与路由兼容门禁；本次实际改动的 test_aa_* 文件由
    # _changed_backend_tests 精确加入。教务源码改动同时拉起已知 MySQL 并发回归。
    (("backend/app/modules/academic_affairs", "backend/app/api/v1/academic"),
     ["tests/test_aa_p0_authz.py",
      "tests/test_aa_route_registration_main_compat.py",
      "tests/test_aa_grade_identity_head_concurrency.py",
      "tests/test_aa_grade_recheck_concurrency.py",
      "tests/test_aa_status_change_concurrency.py",
      "tests/test_aa_exam_facade_contract_and_changes.py"]),
    (("backend/app/services/affairs", "backend/app/api/v1/student_affairs",
      "backend/app/api/v1/mobile"),
     ["tests/test_affairs_*.py", "tests/test_portal_affairs*.py", "tests/test_mobile*.py"]),
    (("backend/app/api/v1/todos", "backend/app/services/workbench_todo",
      "backend/app/services/workbench_snapshot"),
     ["tests/test_workbench_snapshot.py", "tests/test_mobile_stage_a_contracts.py"]),
    (("backend/app/core/field_crypto", "backend/app/services/student_projection",
      "backend/app/services/db_service", "backend/app/api/v1/student.py",
      "backend/app/models/student", "backend/app/schemas/student",
      "backend/app/core/student_master_contract", "backend/app/services/student_master",
      "backend/app/services/student_org_validator",
      "backend/app/services/school_onboarding_service"),
     ["tests/test_student*.py", "tests/test_students_scope.py",
      "tests/test_student_sensitive_contract.py", "tests/test_student_master_service.py",
      "tests/test_school_onboarding.py"]),
    (("backend/app/modules/internship",), ["tests/test_internship*.py"]),
    (("backend/app/modules/graduation",), ["tests/test_graduation*.py"]),
    (("backend/alembic/", "backend/app/models/", "backend/app/db/"),
     ["tests/test_p1_config_guards.py", "tests/test_alembic*.py"]),
    (("backend/app/main.py", "backend/app/core/runtime_metrics",
      "deploy/nginx/", "SCHEDULER", "run_scheduled_jobs"),
     ["tests/test_p1_health_ops.py", "tests/test_p1_scheduler_mode.py"]),
    ((".github/workflows/ci.yml", "scripts/check/"),
     ["tests/test_p1_config_guards.py", "tests/test_p1_ci_select.py"]),
]

CORE_TOUCH = (
    "backend/app/core/", "backend/app/middleware/", "backend/app/main.py",
)
CORE_TESTS = [
    "tests/test_p1_tenant_readonly_guard.py",
    "tests/test_p1_config_guards.py",
    "tests/test_p1_health_ops.py",
    "tests/test_p1_scheduler_mode.py",
    "tests/test_p1_file_content_security.py",
    "tests/test_p1_tenant_context_required.py",
    "tests/test_file_p0_authz.py",
    "tests/test_import_export_p0_authz.py",
    "tests/test_aa_p0_authz.py",
]


def _changed_files() -> list[str]:
    base = os.environ.get("GITHUB_BASE_REF") or os.environ.get("CI_BASE_SHA") or "origin/main"
    cmds = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only", "HEAD~1"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "status", "--porcelain"],
    ]
    files: set[str] = set()
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) > 3 and line[2] == " ":
                path = line[3:].strip().strip('"')
            else:
                path = line
            files.add(path.replace("\\", "/"))
        if files:
            break
    return sorted(files)


def _changed_backend_tests(files: list[str]) -> list[str]:
    prefix = "backend/tests/"
    return [
        path[len("backend/"):]
        for path in files
        if path.startswith(prefix)
        and path.endswith(".py")
        and path.rsplit("/", 1)[-1].startswith("test_")
    ]


def select(files: list[str]) -> list[str]:
    selected: list[str] = _changed_backend_tests(files)
    joined = "\n".join(files)
    core_hit = any(any(p.startswith(c) or c.rstrip("/") in p for c in CORE_TOUCH) for p in files)
    if core_hit:
        selected.extend(CORE_TESTS)
    for needles, targets in RULES:
        if any(n in joined or any(n in f for f in files) for n in needles):
            selected.extend(targets)
    seen = set()
    out = []
    for t in selected:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        out = [
            "tests/test_portal_*.py",
            "tests/test_p1_tenant_readonly_guard.py",
            "tests/test_p1_config_guards.py",
            "tests/test_p1_health_ops.py",
        ]
    return out


def existing_targets(targets: list[str]) -> list[str]:
    """展开 glob 并剔除不存在路径；canonical workflow 的 shell array 不会二次展开。"""
    existing: list[str] = []
    seen: set[str] = set()
    for target in targets:
        has_glob = any(ch in target for ch in "*?[")
        matches = sorted(glob(target)) if has_glob else ([target] if os.path.exists(target) else [])
        for match in matches:
            normalized = match.replace("\\", "/")
            if normalized not in seen:
                seen.add(normalized)
                existing.append(normalized)
    return existing


def main() -> int:
    files = _changed_files()
    targets = existing_targets(select(files))
    if not targets:
        print("CI 未找到任何存在的 pytest 目标", file=sys.stderr)
        return 2
    print(" ".join(targets))
    print(f"# changed={len(files)} targets={len(targets)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
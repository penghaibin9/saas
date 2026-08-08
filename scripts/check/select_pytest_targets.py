#!/usr/bin/env python3
"""根据 git diff 选择最小必要 pytest 集合（CI push/PR 用）。

用法：
  python scripts/check/select_pytest_targets.py
  # 输出空格分隔的 pytest 路径/glob，无命中时输出安全默认集合

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
    # 教务历史测试目录含尚未收口的旧契约，禁止用 test_aa_*.py 把它们全部带入
    # 任意教务源码改动执行稳定权限闸门；本次实际改动的 test_aa_* 文件由
    # _changed_backend_tests 精确加入，既不漏掉新回归，也不制造历史基线假红。
    # P1 批次D：教务域并发正确性测试(行锁/唯一约束竞态)原来只有每日定时全量才跑，
    # PR 阶段不受保护——一个改坏行锁语义的 PR 可以一路绿灯合并，等到凌晨定时任务
    # 才发现。改为教务源码改动即拉起这几个已知的 MySQL 并发回归。
    (("backend/app/modules/academic_affairs", "backend/app/api/v1/academic"),
     ["tests/test_aa_p0_authz.py",
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
    # 学生主档统一整改：主档写入口/投影/敏感字段读取链
    (("backend/app/core/field_crypto", "backend/app/services/student_projection",
      "backend/app/services/db_service", "backend/app/api/v1/student.py",
      "backend/app/models/student", "backend/app/schemas/student",
      "backend/app/core/student_master_contract", "backend/app/services/student_master",
      "backend/app/services/student_org_validator",
      "backend/app/services/school_onboarding_service"),
     ["tests/test_student*.py", "tests/test_students_scope.py",
      "tests/test_student_sensitive_contract.py", "tests/test_student_master_service.py",
      "tests/test_school_onboarding.py"]),
    (("backend/app/modules/internship",),
     ["tests/test_internship*.py"]),
    (("backend/app/modules/graduation",),
     ["tests/test_graduation*.py"]),
    (("backend/alembic/", "backend/app/models/", "backend/app/db/"),
     ["tests/test_p1_config_guards.py", "tests/test_alembic*.py"]),
    (("backend/app/main.py", "backend/app/core/runtime_metrics",
      "deploy/nginx/", "SCHEDULER", "run_scheduled_jobs"),
     ["tests/test_p1_health_ops.py", "tests/test_p1_scheduler_mode.py"]),
    ((".github/workflows/ci.yml", "scripts/check/"),
     ["tests/test_p1_config_guards.py", "tests/test_p1_ci_select.py"]),
]

# 公共底座改动：多域安全回归
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
            # status --porcelain: " M path" / "?? path"
            if len(line) > 3 and line[2] == " ":
                path = line[3:].strip().strip('"')
            else:
                path = line
            files.add(path.replace("\\", "/"))
        if files:
            break
    return sorted(files)


def _changed_backend_tests(files: list[str]) -> list[str]:
    """把 PR 中实际新增/修改的 pytest 文件转换为 backend 工作目录下的路径。"""
    prefix = "backend/tests/"
    return [
        path[len("backend/"):]
        for path in files
        if path.startswith(prefix)
        and path.endswith(".py")
        and path.rsplit("/", 1)[-1].startswith("test_")
    ]


def select(files: list[str]) -> list[str]:
    # 测试与实现必须同批验证；精确测试路径优先于域级稳定闸门。
    selected: list[str] = _changed_backend_tests(files)
    joined = "\n".join(files)
    core_hit = any(any(p.startswith(c) or c.rstrip("/") in p for c in CORE_TOUCH) for p in files)
    if core_hit:
        selected.extend(CORE_TESTS)
    for needles, targets in RULES:
        if any(n in joined or any(n in f for f in files) for n in needles):
            selected.extend(targets)
    # 去重保序
    seen = set()
    out = []
    for t in selected:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        # 无后端改动时仍跑门户快测 + P1 安全最小集，避免只跑空
        out = [
            "tests/test_portal_*.py",
            "tests/test_p1_tenant_readonly_guard.py",
            "tests/test_p1_config_guards.py",
            "tests/test_p1_health_ops.py",
        ]
    return out


def existing_targets(targets: list[str]) -> list[str]:
    """剔除不存在的精确路径或无匹配通配符，避免 pytest 把它们当成错误参数。"""
    existing: list[str] = []
    for target in targets:
        has_glob = any(ch in target for ch in "*?[")
        if (has_glob and glob(target)) or (not has_glob and os.path.exists(target)):
            existing.append(target)
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

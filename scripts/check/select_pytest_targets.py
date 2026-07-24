#!/usr/bin/env python3
"""根据 git diff 选择最小必要 pytest 集合（CI push/PR 用）。

用法：
  python scripts/check/select_pytest_targets.py
  # 输出空格分隔的 pytest 路径/glob，无命中时输出安全默认集合
"""
from __future__ import annotations

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
    (("backend/app/modules/academic_affairs", "backend/app/api/v1/academic"),
     ["tests/test_aa_*.py", "tests/test_portal_academic*.py"]),
    (("backend/app/services/affairs", "backend/app/api/v1/student_affairs",
      "backend/app/api/v1/mobile"),
     ["tests/test_affairs_*.py", "tests/test_portal_affairs*.py", "tests/test_mobile*.py"]),
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


def select(files: list[str]) -> list[str]:
    selected: list[str] = []
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


def main() -> int:
    files = _changed_files()
    targets = select(files)
    print(" ".join(targets))
    print(f"# changed={len(files)} targets={len(targets)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

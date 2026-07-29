#!/usr/bin/env python3
from __future__ import annotations

import os
import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# round2 会再次调用固定入口。用进程内标记让第二次调用成为 no-op，
# 从而保持 CI 命令不变，同时顺序执行已验证的 round1 → round2。
if os.environ.get("ABCD_ROUND1_DONE") == "1":
    print("ABCD round1 already applied")
else:
    round1_commit = "eaddf0f8bf8a94fc6b79b378d9fc8b299b0fce47"
    source = subprocess.check_output(
        [
            "git", "show",
            f"{round1_commit}:scripts/maintenance/fix_abcd_regression_contracts.py",
        ],
        cwd=ROOT,
        text=True,
    )
    namespace = {
        "__name__": "__main__",
        "__file__": str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts.py"),
    }
    exec(compile(source, "<abcd-round1>", "exec"), namespace)
    os.environ["ABCD_ROUND1_DONE"] = "1"
    runpy.run_path(
        str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts_round2.py"),
        run_name="__main__",
    )

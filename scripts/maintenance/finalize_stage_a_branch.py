#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".git/hooks/pre-commit"

# GitHub Actions 的 GITHUB_TOKEN 可以写业务源码，但当前 GitHub App 不允许它
# 更新 workflow 文件。最终步骤仍会在工作区恢复永久闸门并删除一次性施工器，
# 这里通过一次性 pre-commit hook 将这些 workflow/施工器变更从提交中移除；
# 业务源码提交成功后，再由连接器精确清理这些文件。
UNSTAGE = (
    ".github/workflows/ci.yml",
    ".github/workflows/miniapp-mp-weixin-release.yml",
    ".github/workflows/miniapp-stage-a-autofix.yml",
    "scripts/maintenance/apply_miniapp_stage_a.py",
    "scripts/maintenance/hotfix_stage_a_runner.py",
    "scripts/maintenance/hotfix_stage_a_runner_tail.py",
    "scripts/maintenance/postprocess_stage_a_patch.py",
    "scripts/maintenance/finalize_stage_a_branch.py",
)

quoted = " ".join(f"'{item}'" for item in UNSTAGE)
HOOK.write_text(
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    f"git reset -q HEAD -- {quoted}\n",
    encoding="utf-8",
)
HOOK.chmod(0o755)
print("stage A source-only commit hook installed")

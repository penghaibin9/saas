from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT / "docs" / "00-项目入口与总控" / "project-status.json"
SEAL_PATH = ROOT / "artifacts" / "release-seals" / "main-candidate.json"
RUNTIME_PATHS = (
    "backend",
    "frontend",
    "student-portal",
    "miniapp",
    "enterprise-portal",
    "shared",
    "e2e",
    "performance",
    "deploy",
)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_json(path: Path, blocks: list[str]) -> dict:
    if not path.is_file():
        blocks.append(f"缺少状态文件：{path.relative_to(ROOT).as_posix()}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        blocks.append(f"状态文件无法读取：{path.relative_to(ROOT).as_posix()} ({exc})")
        return {}
    if not isinstance(value, dict):
        blocks.append(f"状态文件格式错误：{path.relative_to(ROOT).as_posix()}")
        return {}
    return value


def is_ancestor(commit: str, head: str) -> bool:
    if not commit:
        return False
    return git("merge-base", "--is-ancestor", commit, head, check=False).returncode == 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    blocks: list[str] = []
    warnings: list[str] = []

    head = git("rev-parse", "HEAD").stdout.strip()
    branch = git("branch", "--show-current").stdout.strip()
    dirty = git("status", "--porcelain").stdout.splitlines()
    if dirty:
        blocks.append(f"工作区不干净：检测到 {len(dirty)} 个未提交状态")

    status = load_json(STATUS_PATH, blocks)
    seal = load_json(SEAL_PATH, blocks)

    if status:
        if status.get("branch") != branch:
            blocks.append(
                f"项目状态属于分支 {status.get('branch')!r}，当前分支是 {branch!r}"
            )
        baseline = str(status.get("baselineCommit") or "")
        if not is_ancestor(baseline, head):
            blocks.append("project-status 的 baselineCommit 不是当前 HEAD 的祖先")
        convergence = status.get("sourceConvergence") or {}
        if convergence.get("containsOriginMain") is not True:
            blocks.append("候选分支尚未包含记录中的 origin/main")
        pending = convergence.get("pendingIntegratedBranches") or []
        if pending:
            blocks.append("仍有未收敛功能分支：" + ", ".join(map(str, pending)))
        worktrees = convergence.get("nonMainWorktrees") or []
        if worktrees:
            blocks.append("仍有非主工作区：" + ", ".join(map(str, worktrees)))
        if status.get("deliverable") is not True:
            blocks.append("project-status.json 的 deliverable 不是 true")

    if seal:
        if seal.get("branch") != branch:
            blocks.append(f"release seal 属于分支 {seal.get('branch')!r}，当前分支是 {branch!r}")
        verification_commit = str(seal.get("verificationBaselineCommit") or "")
        if not is_ancestor(verification_commit, head):
            blocks.append("release seal 的验证 commit 不是当前 HEAD 的祖先")
        elif git("diff", "--quiet", verification_commit, head, "--", *RUNTIME_PATHS, check=False).returncode != 0:
            blocks.append("验证 commit 之后运行时代码或部署文件有变化，既有测试结果已过期")

        gates = seal.get("releaseGates") or {}
        if not gates:
            blocks.append("release seal 没有 releaseGates")
        else:
            for name, value in gates.items():
                if value != "passed":
                    blocks.append(f"交付门禁 {name}={value!r}，要求 'passed'")
        if seal.get("deliverable") is not True:
            blocks.append("release seal 的 deliverable 不是 true")

    if not branch:
        warnings.append("当前处于 detached HEAD；正式发布应记录明确分支或标签")

    print(f"候选分支：{branch or '(detached HEAD)'}")
    print(f"候选 commit：{head}")
    for item in warnings:
        print(f"WARN  {item}")
    if blocks:
        for item in blocks:
            print(f"BLOCK {item}")
        print(f"结论：BLOCKED（{len(blocks)} 项），禁止上线")
        return 1

    print("结论：READY，可进入生产环境预检；本检查本身不执行部署")
    return 0


if __name__ == "__main__":
    sys.exit(main())

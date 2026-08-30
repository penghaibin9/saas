"""Fail-closed C7 order lock for the PLAT-C migration slot."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class COrderLockStopped(RuntimeError):
    """The A+B integration prerequisites do not authorize C7 migration work."""


@dataclass(frozen=True, slots=True)
class COrderLockEvidence:
    integration_head: str
    current_head: str
    alembic_head: str


GitOutput = Callable[..., str]
GitIsAncestor = Callable[..., bool]
AlembicHeads = Callable[[Path], tuple[str, ...]]

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_REVISION_RE = re.compile(r"^[0-9A-Za-z_]{1,120}$")


def _default_git_output(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise COrderLockStopped(f"Git 证据读取失败: {detail or 'unknown error'}")
    return completed.stdout.strip()


def _default_git_is_ancestor(ancestor: str, descendant: str, *, cwd: Path) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    detail = (completed.stderr or completed.stdout).strip()
    raise COrderLockStopped(f"Git ancestry 检查失败: {detail or 'unknown error'}")


def _default_alembic_heads(backend_root: Path) -> tuple[str, ...]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str((backend_root / "alembic").resolve()))
    return tuple(sorted(ScriptDirectory.from_config(config).get_heads()))


def verify_c_order_lock(
    *,
    repository_root: Path,
    backend_root: Path,
    integration_head: str,
    expected_alembic_head: str,
    git_output: GitOutput = _default_git_output,
    git_is_ancestor: GitIsAncestor = _default_git_is_ancestor,
    alembic_heads: AlembicHeads = _default_alembic_heads,
) -> COrderLockEvidence:
    """Prove that current HEAD consumed B's A+B integration and migration lineage."""
    integration = str(integration_head or "").strip().lower()
    expected_revision = str(expected_alembic_head or "").strip()
    if not _SHA_RE.fullmatch(integration):
        raise COrderLockStopped("缺少有效的 PLAT_B_INTEGRATION_HEAD")
    if not _REVISION_RE.fullmatch(expected_revision):
        raise COrderLockStopped("缺少有效的 PLAT_B_ALEMBIC_HEAD")

    repo = Path(repository_root)
    backend = Path(backend_root)
    current = git_output("rev-parse", "HEAD", cwd=repo).strip().lower()
    resolved = git_output("rev-parse", f"{integration}^{{commit}}", cwd=repo).strip().lower()
    if resolved != integration:
        raise COrderLockStopped("PLAT_B_INTEGRATION_HEAD 未解析到声明的 exact commit")
    if not git_is_ancestor(integration, current, cwd=repo):
        raise COrderLockStopped("当前 C HEAD 未消费 A+B integration head")

    heads = tuple(alembic_heads(backend))
    if len(heads) != 1:
        raise COrderLockStopped(f"Alembic 必须只有一个 live head，实际为 {len(heads)} 个")
    if heads[0] != expected_revision:
        raise COrderLockStopped(
            f"Alembic head 未消费 B lineage: expected={expected_revision}, actual={heads[0]}",
        )
    return COrderLockEvidence(
        integration_head=integration,
        current_head=current,
        alembic_head=heads[0],
    )


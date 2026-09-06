from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from app.modules.platform.document_lifecycle.order_lock import (
    COrderLockEvidence,
    COrderLockStopped,
    verify_c_order_lock,
)


INTEGRATION_HEAD = "a" * 40
CURRENT_HEAD = "b" * 40


def _git_output(*args: str, cwd: Path) -> str:
    del cwd
    if args == ("rev-parse", "HEAD"):
        return CURRENT_HEAD
    if args == ("rev-parse", f"{INTEGRATION_HEAD}^{{commit}}"):
        return INTEGRATION_HEAD
    raise AssertionError(args)


def test_order_lock_accepts_exact_b_integration_ancestor_and_single_head() -> None:
    evidence = verify_c_order_lock(
        repository_root=Path("repo"),
        backend_root=Path("repo/backend"),
        integration_head=INTEGRATION_HEAD,
        expected_alembic_head="20260830_plat_b_forms",
        git_output=_git_output,
        git_is_ancestor=lambda *_args, **_kwargs: True,
        alembic_heads=lambda _root: ("20260830_plat_b_forms",),
    )
    assert evidence == COrderLockEvidence(
        integration_head=INTEGRATION_HEAD,
        current_head=CURRENT_HEAD,
        alembic_head="20260830_plat_b_forms",
    )


@pytest.mark.parametrize(
    ("integration_head", "expected_alembic_head"),
    [("", "20260830_plat_b_forms"), ("not-a-sha", "20260830_plat_b_forms"), (INTEGRATION_HEAD, "")],
)
def test_order_lock_requires_exact_b_markers(
        integration_head: str, expected_alembic_head: str) -> None:
    with pytest.raises(COrderLockStopped):
        verify_c_order_lock(
            repository_root=Path("repo"),
            backend_root=Path("repo/backend"),
            integration_head=integration_head,
            expected_alembic_head=expected_alembic_head,
            git_output=_git_output,
            git_is_ancestor=lambda *_args, **_kwargs: True,
            alembic_heads=lambda _root: ("20260830_plat_b_forms",),
        )


def test_order_lock_rejects_unconsumed_integration_head() -> None:
    with pytest.raises(COrderLockStopped, match="未消费"):
        verify_c_order_lock(
            repository_root=Path("repo"),
            backend_root=Path("repo/backend"),
            integration_head=INTEGRATION_HEAD,
            expected_alembic_head="20260830_plat_b_forms",
            git_output=_git_output,
            git_is_ancestor=lambda *_args, **_kwargs: False,
            alembic_heads=lambda _root: ("20260830_plat_b_forms",),
        )


@pytest.mark.parametrize(
    "heads",
    [(), ("a_head", "b_head"), ("20260829_main",)],
)
def test_order_lock_rejects_missing_sibling_or_stale_alembic_head(heads: tuple[str, ...]) -> None:
    with pytest.raises(COrderLockStopped, match="Alembic"):
        verify_c_order_lock(
            repository_root=Path("repo"),
            backend_root=Path("repo/backend"),
            integration_head=INTEGRATION_HEAD,
            expected_alembic_head="20260830_plat_b_forms",
            git_output=_git_output,
            git_is_ancestor=lambda *_args, **_kwargs: True,
            alembic_heads=lambda _root: heads,
        )


def test_order_lock_cli_is_directly_executable_and_fails_closed() -> None:
    completed = subprocess.run(
        [
            sys.executable, "scripts/verify_platform_c_order_lock.py",
            "--integration-head", "not-a-sha", "--alembic-head", "not_a_revision",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 2
    assert "C_ORDER_LOCK=STOP" in completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr

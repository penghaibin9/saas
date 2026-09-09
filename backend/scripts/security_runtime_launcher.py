"""Fixed production launcher for the security image; no shell interpretation.

Only three reviewed long-running roles are accepted. Preflight checks run in the
same process, then os.execv replaces it with a static Python/module command. No
command, argument, path, or executable is accepted from environment/user input.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable

ROLE_TARGETS = {
    "backend": (
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-proxy-headers",
    ),
    "scheduler": (sys.executable, "-m", "scripts.run_scheduled_jobs"),
    "file-scan": (sys.executable, "-m", "app.workers.file_scan_worker"),
}


def target_argv(role: str) -> tuple[str, ...]:
    try:
        return ROLE_TARGETS[role]
    except KeyError as exc:
        raise ValueError("UNSUPPORTED_RUNTIME_ROLE") from exc


def launch(
    role: str,
    *,
    filesystem_fn: Callable[[], object] | None = None,
    redis_fn: Callable[[], int] | None = None,
    scan_fn: Callable[[], int] | None = None,
    exec_fn: Callable[[str, list[str]], object] = os.execv,
) -> None:
    """Run fixed fail-closed preflights then replace this process with its role."""
    target = target_argv(role)
    if filesystem_fn is None:
        from scripts.security_profile_probe import filesystem
        filesystem_fn = filesystem
    if redis_fn is None:
        from scripts.check_production_redis import main as redis_main
        redis_fn = redis_main
    if scan_fn is None:
        from scripts.check_production_file_scan import main as scan_main
        scan_fn = scan_main

    filesystem_fn()
    if role in {"backend", "scheduler"} and int(redis_fn()) != 0:
        raise RuntimeError("REDIS_PREFLIGHT_FAILED")
    if role in {"backend", "file-scan"} and int(scan_fn()) != 0:
        raise RuntimeError("FILE_SCAN_PREFLIGHT_FAILED")

    executable = target[0]
    argv = list(target)
    exec_fn(executable, argv)
    raise RuntimeError("RUNTIME_EXEC_RETURNED")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=tuple(ROLE_TARGETS))
    args = parser.parse_args(argv)
    launch(args.role)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

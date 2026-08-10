#!/usr/bin/env python3
"""Safely read a systemd-style EnvironmentFile for deployment commands.

Why this exists: ``EnvironmentFile=`` values are data, not shell source code.  A
perfectly valid strong password containing ``&``, ``$`` or spaces must never be
executed/interpreted by ``. backend.env``.  The release scripts use this helper
to either read one value or exec a command with the parsed environment.

Deployment contract intentionally supports the subset used by
``deploy/env/backend.systemd.env.example``: one KEY=VALUE assignment per line,
optional matching single/double quotes around the whole value, comments on their
own line, no multiline continuation.  Unsupported syntax fails closed.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvFileError(ValueError):
    pass


def _decode_value(raw: str, *, line_no: int) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.endswith("\\"):
        raise EnvFileError(f"line {line_no}: multiline continuation is not supported")
    if value[0] in {"'", '"'}:
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            raise EnvFileError(f"line {line_no}: unterminated quoted value")
        inner = value[1:-1]
        if quote == '"':
            # Minimal systemd-compatible escaping for the characters operators
            # commonly quote in credentials/URLs.  Unknown escapes are kept.
            inner = inner.replace(r"\\", "\\").replace(r'\"', '"')
        return inner
    return value


def load_env_file(path: str | Path) -> dict[str, str]:
    source = Path(path)
    if not source.is_file():
        raise EnvFileError(f"environment file not found: {source}")
    values: dict[str, str] = {}
    for line_no, raw in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if "=" not in raw:
            raise EnvFileError(f"line {line_no}: expected KEY=VALUE")
        key, raw_value = raw.split("=", 1)
        key = key.strip()
        if not _KEY.fullmatch(key):
            raise EnvFileError(f"line {line_no}: invalid environment key")
        values[key] = _decode_value(raw_value, line_no=line_no)
    return values


def _usage() -> int:
    print(
        "usage: run-with-envfile.py --get <env-file> <KEY> | "
        "run-with-envfile.py <env-file> -- <command> [args...]",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 3 and args[0] == "--get":
            values = load_env_file(args[1])
            # Do not add labels: callers capture stdout as the exact value.
            sys.stdout.write(values.get(args[2], ""))
            return 0

        if len(args) >= 3 and args[1] == "--":
            values = load_env_file(args[0])
            command = args[2:]
            if not command:
                return _usage()
            env = os.environ.copy()
            env.update(values)
            os.execvpe(command[0], command, env)
            return 127
    except (EnvFileError, OSError) as exc:
        # Never print values or the environment map; parser errors expose only
        # structure/line number and OS errors expose the command/path failure.
        print(f"environment_file_error: {exc}", file=sys.stderr)
        return 1
    return _usage()


if __name__ == "__main__":
    raise SystemExit(main())

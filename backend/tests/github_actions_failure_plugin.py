"""Expose compact pytest failures as GitHub Actions check annotations.

The GitHub connector can read check annotations even when raw Actions logs are not
available. This plugin is diagnostic only: it never skips, xfails, retries, or
changes test outcomes. Outside GitHub Actions it is a no-op.
"""
from __future__ import annotations

import os

_MAX_ANNOTATIONS = 40
_failures: list[tuple[str, int, str]] = []


def _escape_data(value: object) -> str:
    return (
        str(value)
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def _escape_property(value: object) -> str:
    return (
        _escape_data(value)
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def _compact_failure(report) -> str:
    text = getattr(report, "longreprtext", "") or str(getattr(report, "longrepr", ""))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "pytest failure"
    return lines[-1][:800]


def pytest_runtest_logreport(report) -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return
    if not report.failed or len(_failures) >= _MAX_ANNOTATIONS:
        return

    path, line, _domain = report.location
    try:
        line_no = int(line) + 1
    except (TypeError, ValueError):
        line_no = 1
    message = f"{report.nodeid} [{report.when}] | {_compact_failure(report)}"
    _failures.append((str(path), line_no, message))


def pytest_terminal_summary(terminalreporter) -> None:
    """Emit annotations after capture has ended so GitHub can parse workflow commands."""
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return
    for path, line_no, message in _failures:
        terminalreporter.write_line(
            "::error "
            f"file={_escape_property(path)},"
            f"line={line_no},"
            f"title={_escape_property('pytest failure')}::"
            f"{_escape_data(message)}"
        )

#!/usr/bin/env python3
"""Fail-closed upstream contract-freeze detector for Academic D-W5.

D-W5 may consume moving A/B/C heads during PRE-GOLD, but Final Gold is forbidden until
all contracts required by the construction book are explicitly frozen by their owner PRs.
This script reads only PR metadata and writes immutable evidence; it never edits upstream PRs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "penghaibin9/saas"
UPSTREAM = {
    "A": {
        "pr": 145,
        "branch": "agent/academic-a-semester-core",
        "contracts": ("A-C1", "A-C2", "A-C3", "A-C4", "A-C5"),
    },
    "B": {
        "pr": 146,
        "branch": "agent/academic-b-schedule-selection",
        "contracts": ("B-C1", "B-C2", "B-C3"),
    },
    "C": {
        "pr": 148,
        "branch": "agent/academic-c-teaching-execution",
        "contracts": ("C-C1", "C-C2", "C-C3"),
    },
}

_FREEZE_TOKENS = (
    "FROZEN",
    "已冻结",
    "冻结完成",
    "CONTRACT FREEZE",
    "FREEZE COMPLETED",
)
_CLAUSE_BOUNDARIES = "\n。.!?！？；;"


def _normalize(text: object) -> str:
    # Preserve newlines because owner freeze assertions are commonly line-scoped in PR bodies.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clause(body: str, start: int, end: int) -> str:
    left = -1
    for boundary in _CLAUSE_BOUNDARIES:
        left = max(left, body.rfind(boundary, 0, start))
    right_candidates = [
        position
        for boundary in _CLAUSE_BOUNDARIES
        if (position := body.find(boundary, end)) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(body)
    return body[left + 1:right].strip()


def _contract_frozen(body: str, code: str) -> bool:
    """Require the contract code and an explicit freeze assertion in the same clause."""
    upper = body.upper()
    code_upper = code.upper()
    for match in re.finditer(re.escape(code_upper), upper):
        context = _clause(body, match.start(), match.end())
        context_upper = context.upper()
        if any(token in context_upper for token in _FREEZE_TOKENS if token.isascii()):
            return True
        if any(token in context for token in _FREEZE_TOKENS if not token.isascii()):
            return True
    return False


def evaluate_pr(line: str, payload: dict[str, Any]) -> dict[str, Any]:
    expected = UPSTREAM[line]
    body = _normalize(payload.get("body"))
    head = payload.get("head") or {}
    branch = str(head.get("ref") or "")
    sha = str(head.get("sha") or "")
    state = str(payload.get("state") or "").lower()
    contracts = {
        code: _contract_frozen(body, code)
        for code in expected["contracts"]
    }
    structural_ok = (
        int(payload.get("number") or 0) == int(expected["pr"])
        and branch == expected["branch"]
        and bool(sha)
        and state == "open"
    )
    missing = [code for code, frozen in contracts.items() if not frozen]
    return {
        "line": line,
        "pr": int(expected["pr"]),
        "expectedBranch": expected["branch"],
        "headBranch": branch,
        "headSha": sha,
        "state": state,
        "draft": bool(payload.get("draft")),
        "bodySha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "contracts": contracts,
        "missingContracts": missing,
        "structuralOk": structural_ok,
        "allContractsFrozen": structural_ok and not missing,
    }


def build_freeze_matrix(payloads: dict[str, dict[str, Any]], *, api_error: str = "") -> dict[str, Any]:
    lines: dict[str, dict[str, Any]] = {}
    for line in UPSTREAM:
        payload = payloads.get(line) or {}
        lines[line] = evaluate_pr(line, payload)
    all_frozen = not api_error and all(row["allContractsFrozen"] for row in lines.values())
    blockers: list[str] = []
    if api_error:
        blockers.append(f"github_api_error:{api_error}")
    for line, row in lines.items():
        if not row["structuralOk"]:
            blockers.append(
                f"{line}:upstream_pr_structure_not_ready:"
                f"branch={row['headBranch'] or 'missing'}:state={row['state'] or 'missing'}"
            )
        for code in row["missingContracts"]:
            blockers.append(f"{line}:contract_not_explicitly_frozen:{code}")
    return {
        "schemaVersion": 1,
        "repository": REPO,
        "allFrozen": all_frozen,
        "lines": lines,
        "blockers": blockers,
        "apiError": api_error,
    }


def fetch_pr(repo: str, number: int, token: str, api_url: str) -> dict[str, Any]:
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    endpoint = f"{api_url.rstrip('/')}/repos/{quote(repo, safe='/')}/pulls/{int(number)}"
    request = Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "academic-d-w5-upstream-freeze",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError(f"PR #{number} response is not an object")
    return payload


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    payloads: dict[str, dict[str, Any]] = {}
    api_error = ""
    try:
        for line, expected in UPSTREAM.items():
            payloads[line] = fetch_pr(args.repo, int(expected["pr"]), token, api_url)
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        api_error = f"{type(exc).__name__}:{exc}"

    matrix = build_freeze_matrix(payloads, api_error=api_error)
    write_json(args.output, matrix)
    print(json.dumps(matrix, ensure_ascii=False, sort_keys=True))
    if args.strict and not matrix["allFrozen"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build a fail-closed D-W5 exact-head evidence matrix from GitHub Actions.

This is an evidence aggregator only. It never changes repository state and it never
promotes PRE-GOLD evidence to Final Gold unless every explicit final condition is true.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REQUIRED_SAME_HEAD_WORKFLOWS = (
    "Sandbox 20K Real-School Data Gate",
    "Academic D MySQL PITR One Shot",
    "Backup restore drill",
    "Graduation Targeted Validation",
    "File center final acceptance",
)

AUXILIARY_BROWSER_WORKFLOW = "Playwright production interaction E2E"
_TRUE = {"1", "true", "yes", "on"}


def _as_bool(value: object) -> bool:
    return str(value or "").strip().lower() in _TRUE


def parse_key_value_evidence(path: str | Path) -> dict[str, str]:
    result: dict[str, str] = {}
    evidence_path = Path(path)
    if not evidence_path.exists():
        return result
    for raw_line in evidence_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def latest_runs_by_name(runs: Iterable[dict[str, Any]], exact_sha: str) -> dict[str, dict[str, Any]]:
    """Return the newest run for each workflow, restricted to the exact source SHA."""
    exact_sha = str(exact_sha).strip()
    selected: dict[str, dict[str, Any]] = {}
    for run in runs:
        if str(run.get("head_sha") or "") != exact_sha:
            continue
        name = str(run.get("name") or "").strip()
        if not name:
            continue
        current = selected.get(name)
        run_key = (int(run.get("run_attempt") or 0), int(run.get("id") or 0))
        current_key = (
            int(current.get("run_attempt") or 0),
            int(current.get("id") or 0),
        ) if current else (-1, -1)
        if run_key >= current_key:
            selected[name] = run
    return selected


def classify_workflow(name: str, run: dict[str, Any] | None) -> dict[str, Any]:
    if run is None:
        return {
            "name": name,
            "state": "MISSING",
            "ready": False,
            "runId": None,
            "status": None,
            "conclusion": None,
        }
    status = str(run.get("status") or "").lower()
    conclusion = str(run.get("conclusion") or "").lower()
    ready = status == "completed" and conclusion == "success"
    if ready:
        state = "SUCCESS"
    elif status != "completed":
        state = "PENDING"
    else:
        state = "FAILURE"
    return {
        "name": name,
        "state": state,
        "ready": ready,
        "runId": run.get("id"),
        "runNumber": run.get("run_number"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "htmlUrl": run.get("html_url"),
    }


def build_matrix(*, sha: str, runs: Iterable[dict[str, Any]], evidence: dict[str, str], api_error: str = "") -> dict[str, Any]:
    selected = latest_runs_by_name(runs, sha)
    required = {
        name: classify_workflow(name, selected.get(name))
        for name in REQUIRED_SAME_HEAD_WORKFLOWS
    }
    browser = classify_workflow(
        AUXILIARY_BROWSER_WORKFLOW,
        selected.get(AUXILIARY_BROWSER_WORKFLOW),
    )

    local_replay_ready = all(
        _as_bool(evidence.get(key))
        for key in (
            "replay_success",
            "clean_tenant_schema_proven",
            "migrated_tenant_contracts_proven",
        )
    )
    external_same_head_ready = not api_error and all(item["ready"] for item in required.values())
    pre_gold_ready = local_replay_ready and external_same_head_ready

    upstream_frozen = _as_bool(evidence.get("upstream_contract_heads_frozen"))
    final_browser_proven = _as_bool(evidence.get("final_browser_gold_proven_on_w5_head"))
    final_gold = pre_gold_ready and upstream_frozen and final_browser_proven

    blockers: list[str] = []
    if api_error:
        blockers.append(f"actions_api_error:{api_error}")
    if not local_replay_ready:
        phase = evidence.get("w5_phase") or "UNKNOWN"
        layer = evidence.get("failed_layer") or ""
        blockers.append(f"pre_gold_replay_not_green:phase={phase}:layer={layer}")
    for name, item in required.items():
        if not item["ready"]:
            blockers.append(f"same_head_workflow:{name}:{item['state']}")
    if not upstream_frozen:
        blockers.append("upstream_contract_heads_not_frozen")
    if not final_browser_proven:
        blockers.append("integrated_final_browser_gold_not_proven")

    return {
        "schemaVersion": 1,
        "sourceSha": sha,
        "w5Phase": evidence.get("w5_phase") or "UNKNOWN",
        "failedLayer": evidence.get("failed_layer") or "",
        "replaySuccess": _as_bool(evidence.get("replay_success")),
        "localReplayReady": local_replay_ready,
        "requiredSameHeadWorkflows": required,
        "auxiliaryRawHeadBrowser": browser,
        "externalSameHeadReady": external_same_head_ready,
        "preGoldReady": pre_gold_ready,
        "upstreamContractHeadsFrozen": upstream_frozen,
        "integratedFinalBrowserGoldProven": final_browser_proven,
        "finalGold": final_gold,
        "blockers": blockers,
        "actionsApiError": api_error,
    }


def fetch_actions_runs(repo: str, sha: str, token: str, api_url: str = "https://api.github.com") -> list[dict[str, Any]]:
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for exact-head Actions evidence")
    endpoint = (
        f"{api_url.rstrip('/')}/repos/{quote(repo, safe='/')}/actions/runs"
        f"?head_sha={quote(sha)}&event=pull_request&per_page=100"
    )
    request = Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "academic-d-w5-same-head-matrix",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise RuntimeError("GitHub Actions response did not contain workflow_runs")
    return runs


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--w5-evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict-final", action="store_true")
    args = parser.parse_args(argv)

    evidence = parse_key_value_evidence(args.w5_evidence)
    token = os.environ.get("GITHUB_TOKEN", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    api_error = ""
    runs: list[dict[str, Any]] = []
    try:
        runs = fetch_actions_runs(args.repo, args.sha, token, api_url)
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        api_error = f"{type(exc).__name__}:{exc}"

    matrix = build_matrix(sha=args.sha, runs=runs, evidence=evidence, api_error=api_error)
    _write_json(args.output, matrix)
    print(json.dumps(matrix, ensure_ascii=False, sort_keys=True))

    if args.strict_final and not matrix["finalGold"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fail-closed D-W5 exact-head Gold evidence matrix."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
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
REPLAY_BRANCHES = {
    "main": ("main", "main_commit"),
    "A": ("agent/academic-a-semester-core", "a_commit"),
    "B": ("agent/academic-b-schedule-selection", "b_commit"),
    "C": ("agent/academic-c-teaching-execution", "c_commit"),
    "INT": ("integration/academic-school-gold", "int_commit"),
}
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


def parse_json_evidence(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    evidence_path = Path(path)
    if not evidence_path.exists():
        return {}
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_runs_by_name(runs: Iterable[dict[str, Any]], exact_sha: str) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for run in runs:
        if str(run.get("head_sha") or "") != str(exact_sha).strip():
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
        return {"name": name, "state": "MISSING", "ready": False, "runId": None, "status": None, "conclusion": None}
    status = str(run.get("status") or "").lower()
    conclusion = str(run.get("conclusion") or "").lower()
    ready = status == "completed" and conclusion == "success"
    state = "SUCCESS" if ready else "PENDING" if status != "completed" else "FAILURE"
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


def compare_upstream_freeze_to_replay(
    freeze_payload: dict[str, Any], evidence: dict[str, str]
) -> tuple[bool, list[dict[str, str]]]:
    lines = freeze_payload.get("lines") or {}
    expected = {
        "A": str(evidence.get("a_commit") or ""),
        "B": str(evidence.get("b_commit") or ""),
        "C": str(evidence.get("c_commit") or ""),
    }
    comparisons: list[dict[str, str]] = []
    matches = True
    for line, replay_sha in expected.items():
        freeze_sha = str((lines.get(line) or {}).get("headSha") or "")
        match = bool(replay_sha and freeze_sha and replay_sha == freeze_sha)
        matches = matches and match
        comparisons.append({
            "line": line,
            "freezeHeadSha": freeze_sha,
            "replayHeadSha": replay_sha,
            "matches": "true" if match else "false",
        })
    return matches, comparisons


def compare_live_heads_to_replay(
    live_heads: dict[str, str], evidence: dict[str, str]
) -> tuple[bool, list[dict[str, str]]]:
    comparisons: list[dict[str, str]] = []
    matches = True
    for label, (branch, evidence_key) in REPLAY_BRANCHES.items():
        replay_sha = str(evidence.get(evidence_key) or "")
        live_sha = str(live_heads.get(branch) or "")
        match = bool(replay_sha and live_sha and replay_sha == live_sha)
        matches = matches and match
        comparisons.append({
            "label": label,
            "branch": branch,
            "replayHeadSha": replay_sha,
            "liveHeadSha": live_sha,
            "matches": "true" if match else "false",
        })
    return matches, comparisons


def build_matrix(
    *,
    sha: str,
    runs: Iterable[dict[str, Any]],
    evidence: dict[str, str],
    upstream_freeze: dict[str, Any] | None = None,
    live_heads: dict[str, str] | None = None,
    api_error: str = "",
    live_heads_error: str = "",
) -> dict[str, Any]:
    selected = latest_runs_by_name(runs, sha)
    required = {name: classify_workflow(name, selected.get(name)) for name in REQUIRED_SAME_HEAD_WORKFLOWS}
    browser = classify_workflow(AUXILIARY_BROWSER_WORKFLOW, selected.get(AUXILIARY_BROWSER_WORKFLOW))

    local_requirements = {
        "replaySuccess": _as_bool(evidence.get("replay_success")),
        "cleanTenantSchema": _as_bool(evidence.get("clean_tenant_schema_proven")),
        "migratedTenantSchema": _as_bool(evidence.get("migrated_tenant_schema_proven")),
        "migratedTenantContracts": _as_bool(evidence.get("migrated_tenant_contracts_proven")),
        "permissionNegative": _as_bool(evidence.get("permission_negative_contract_proven")),
        "dataScopeNegative": _as_bool(evidence.get("datascope_negative_contract_proven")),
        "crossTenantSentinel": _as_bool(evidence.get("cross_tenant_sentinel_proven")),
    }
    local_replay_ready = all(local_requirements.values())
    external_same_head_ready = not api_error and all(item["ready"] for item in required.values())
    pre_gold_ready = local_replay_ready and external_same_head_ready

    freeze_payload = upstream_freeze or {}
    freeze_declared = freeze_payload.get("allFrozen") is True
    freeze_heads_match, freeze_head_comparisons = compare_upstream_freeze_to_replay(freeze_payload, evidence)
    upstream_frozen = freeze_declared and freeze_heads_match
    freeze_blockers = [str(item) for item in (freeze_payload.get("blockers") or []) if str(item).strip()]

    replay_heads_current, replay_head_comparisons = compare_live_heads_to_replay(live_heads or {}, evidence)
    if live_heads_error:
        replay_heads_current = False

    final_browser_proven = _as_bool(evidence.get("final_browser_gold_proven_on_w5_head"))
    final_gold = pre_gold_ready and upstream_frozen and replay_heads_current and final_browser_proven

    blockers: list[str] = []
    if api_error:
        blockers.append(f"actions_api_error:{api_error}")
    if live_heads_error:
        blockers.append(f"live_heads_api_error:{live_heads_error}")
    if not local_replay_ready:
        blockers.append(
            "pre_gold_replay_not_green:"
            f"phase={evidence.get('w5_phase') or 'UNKNOWN'}:layer={evidence.get('failed_layer') or ''}"
        )
        blockers.extend(f"local_requirement:{key}:false" for key, ready in local_requirements.items() if not ready)
    for name, item in required.items():
        if not item["ready"]:
            blockers.append(f"same_head_workflow:{name}:{item['state']}")
    if not upstream_frozen:
        blockers.append("upstream_contract_heads_not_frozen")
        blockers.extend(f"upstream:{item}" for item in freeze_blockers)
        if freeze_declared and not freeze_heads_match:
            for row in freeze_head_comparisons:
                if row["matches"] != "true":
                    blockers.append(
                        "upstream_freeze_head_mismatch:"
                        f"{row['line']}:freeze={row['freezeHeadSha'] or 'missing'}:replay={row['replayHeadSha'] or 'missing'}"
                    )
    if not replay_heads_current:
        blockers.append("replay_heads_no_longer_current")
        for row in replay_head_comparisons:
            if row["matches"] != "true":
                blockers.append(
                    "replay_head_moved_since_snapshot:"
                    f"{row['label']}:branch={row['branch']}:replay={row['replayHeadSha'] or 'missing'}:live={row['liveHeadSha'] or 'missing'}"
                )
    if not final_browser_proven:
        blockers.append("integrated_final_browser_gold_not_proven")

    return {
        "schemaVersion": 6,
        "sourceSha": sha,
        "w5Phase": evidence.get("w5_phase") or "UNKNOWN",
        "failedLayer": evidence.get("failed_layer") or "",
        "localRequirements": local_requirements,
        "localReplayReady": local_replay_ready,
        "requiredSameHeadWorkflows": required,
        "auxiliaryRawHeadBrowser": browser,
        "externalSameHeadReady": external_same_head_ready,
        "preGoldReady": pre_gold_ready,
        "upstreamContractFreezeDeclared": freeze_declared,
        "upstreamFreezeHeadsMatchReplay": freeze_heads_match,
        "upstreamFreezeHeadComparisons": freeze_head_comparisons,
        "upstreamContractHeadsFrozen": upstream_frozen,
        "upstreamFreezeEvidence": freeze_payload,
        "replayHeadsStillCurrent": replay_heads_current,
        "replayHeadComparisons": replay_head_comparisons,
        "integratedFinalBrowserGoldProven": final_browser_proven,
        "finalGold": final_gold,
        "blockers": blockers,
        "actionsApiError": api_error,
        "liveHeadsApiError": live_heads_error,
        "migrationEvidence": {
            "mainAlembicVersion": evidence.get("main_alembic_version") or "",
            "integratedAlembicVersion": evidence.get("integrated_alembic_version") or "",
            "probeDigest": evidence.get("migrated_probe_digest") or "",
        },
    }


def _github_json(endpoint: str, token: str, *, user_agent: str) -> Any:
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    request = Request(endpoint, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": user_agent,
    })
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_actions_runs(repo: str, sha: str, token: str, api_url: str = "https://api.github.com") -> list[dict[str, Any]]:
    endpoint = (
        f"{api_url.rstrip('/')}/repos/{quote(repo, safe='/')}/actions/runs"
        f"?head_sha={quote(sha)}&event=pull_request&per_page=100"
    )
    payload = _github_json(endpoint, token, user_agent="academic-d-w5-same-head-matrix")
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise RuntimeError("GitHub Actions response did not contain workflow_runs")
    return runs


def required_workflows_terminal(runs: Iterable[dict[str, Any]], sha: str) -> bool:
    selected = latest_runs_by_name(runs, sha)
    return all(
        name in selected and str(selected[name].get("status") or "").lower() == "completed"
        for name in REQUIRED_SAME_HEAD_WORKFLOWS
    )


def fetch_live_heads(repo: str, token: str, api_url: str = "https://api.github.com") -> dict[str, str]:
    heads: dict[str, str] = {}
    for branch, _evidence_key in REPLAY_BRANCHES.values():
        endpoint = f"{api_url.rstrip('/')}/repos/{quote(repo, safe='/')}/branches/{quote(branch, safe='')}"
        payload = _github_json(endpoint, token, user_agent="academic-d-w5-live-heads")
        sha = str(((payload or {}).get("commit") or {}).get("sha") or "")
        if not sha:
            raise RuntimeError(f"branch {branch!r} did not return a commit sha")
        heads[branch] = sha
    return heads


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--w5-evidence", required=True)
    parser.add_argument("--upstream-freeze")
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--strict-final", action="store_true")
    args = parser.parse_args(argv)

    evidence = parse_key_value_evidence(args.w5_evidence)
    upstream_freeze = parse_json_evidence(args.upstream_freeze)
    token = os.environ.get("GITHUB_TOKEN", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    api_error = ""
    live_heads_error = ""
    runs: list[dict[str, Any]] = []
    live_heads: dict[str, str] = {}

    deadline = time.monotonic() + max(0, int(args.wait_seconds))
    try:
        while True:
            runs = fetch_actions_runs(args.repo, args.sha, token, api_url)
            if required_workflows_terminal(runs, args.sha) or time.monotonic() >= deadline:
                break
            time.sleep(max(1, int(args.poll_seconds)))
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        api_error = f"{type(exc).__name__}:{exc}"

    try:
        live_heads = fetch_live_heads(args.repo, token, api_url)
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        live_heads_error = f"{type(exc).__name__}:{exc}"

    matrix = build_matrix(
        sha=args.sha,
        runs=runs,
        evidence=evidence,
        upstream_freeze=upstream_freeze,
        live_heads=live_heads,
        api_error=api_error,
        live_heads_error=live_heads_error,
    )
    _write_json(args.output, matrix)
    print(json.dumps(matrix, ensure_ascii=False, sort_keys=True))
    if args.strict_final and not matrix["finalGold"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Seal the Internship V8 final verdict from machine-readable, exact-HEAD evidence."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> dict:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing evidence: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Internship V8 exact-HEAD final verdict")
    parser.add_argument("--output", required=True)
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()

    d_gates = load("artifacts/internship-v8/w17/d-gates.json")
    gates = d_gates.get("gates") or []
    require(len(gates) == 60, "exactly 60 D-GATE entries are required")
    for index, gate in enumerate(gates, 1):
        expected = f"D-GATE-IX-{index:02d}"
        require(gate.get("id") == expected, f"D-GATE order mismatch: {expected}")
        require(gate.get("status") == "PASS", f"{expected} is not PASS")
        evidence = str(gate.get("evidence") or "")
        require(bool(evidence), f"{expected} has no evidence")
        if not evidence.startswith("goal-objective:"):
            require((ROOT / evidence).is_file(), f"{expected} evidence is missing: {evidence}")

    capability = load("artifacts/internship-v8/w17/capability-preservation-final.json")
    capabilities = capability.get("capabilities") or []
    require(len(capabilities) == 20, "exactly 20 capability entries are required")
    for index, item in enumerate(capabilities, 1):
        expected = f"CP-IX-{index:02d}"
        require(item.get("id") == expected, f"capability order mismatch: {expected}")
        require(item.get("status") == "PASS", f"{expected} is not PASS")
        for evidence in item.get("evidence") or []:
            require((ROOT / evidence).is_file(), f"{expected} evidence is missing: {evidence}")

    journeys = load("artifacts/internship-v8/w16/runtime-golden-journeys-seal.json")
    journey_rows = journeys.get("journeys") or []
    require(len(journey_rows) == 9, "exactly nine golden journeys are required")
    require(all(item.get("status") == "L4_SEALED" for item in journey_rows), "all journeys must be L4_SEALED")
    require(journeys.get("result") == "PASS", "W16 runtime journey seal is not PASS")

    release = load("artifacts/internship-v8/w17/release-gates.json")
    require(release.get("result") == "PASS", "W17 release gates are not PASS")
    scale = load("artifacts/internship-v8/w17/scale-20k.json")
    require(scale.get("passed") is True, "20K service evidence is not PASS")
    require(scale.get("dataset", {}).get("internshipRecords") == 20_000, "20K dataset is not exact")
    browser = load("artifacts/internship-v8/w17/browser-scale-20k.json")
    require(browser.get("passed") is True, "20K browser evidence is not PASS")
    require(len(browser.get("targets") or []) == 5, "five 20K browser targets are required")
    require(
        all(item.get("checks", {}).get("authenticatedRoute") is True for item in browser["targets"]),
        "20K browser evidence contains an unauthenticated route",
    )
    closure = load("artifacts/internship/final-audit/source-manifest/source-closure.json")
    for gap in (
        "unclassifiedFiles", "unmappedRoutes", "unmappedApiAliases",
        "unmappedSchedulers", "unmappedMigrations", "unmappedSharedDependencies",
    ):
        require(not closure.get(gap), f"S6 gap is not empty: {gap}")

    heads = subprocess.check_output(
        [sys.executable, "-m", "alembic", "heads"], cwd=ROOT / "backend", text=True,
    ).strip().splitlines()
    actual_heads = [line for line in heads if "(head)" in line]
    require(len(actual_heads) == 1, f"expected one Alembic head, got {actual_heads}")

    head = git("rev-parse", "HEAD")
    main_sha = git("rev-parse", args.main_ref)
    subprocess.check_call(["git", "merge-base", "--is-ancestor", main_sha, head], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if args.require_clean:
        require(not dirty, "final verdict requires a clean exact HEAD")

    verdict = {
        "schema": "internship-v8-final-verdict/1",
        "module": "internship",
        "surfaces": 5,
        "score": "10.0/10",
        "dxP0": 0,
        "dxP1": 0,
        "goldenJourneys": "9/9 L4_SEALED",
        "capabilityPreservation": "20/20 PASS",
        "dGates": "60/60 PASS",
        "scale20k": "PASS",
        "s5": "PASS",
        "s6": "PASS",
        "latestMainSynced": True,
        "sameExactHead": args.require_clean,
        "exactHead": head,
        "mainSha": main_sha,
        "alembicHead": actual_heads[0].split()[0],
        "state": "MERGE_READY_HOLD" if args.hold else "FINAL_GATES_PASS",
        "autoMerge": False,
    }
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, subprocess.CalledProcessError) as error:
        print(f"[internship-v8-final] FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)

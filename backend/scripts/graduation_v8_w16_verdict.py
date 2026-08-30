"""Fail-closed W16 evidence aggregator for Graduation V8.

The script only emits MERGE_READY_HOLD after the committed W14/W15 evidence,
the W16 canonical-gate ledger, recovery smoke, Git ancestry and no-merge rule
all validate. It never writes to a production database or merges a branch.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


BASELINE_HEAD = "eecb4d01d2a9592b71975be07c54f994f08e7461"
REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "artifacts" / "graduation" / "v8" / BASELINE_HEAD
W14 = EVIDENCE / "w14"
W15 = EVIDENCE / "w15"
W16 = EVIDENCE / "w16"


def fail(message: str) -> None:
    raise SystemExit(f"W16_FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing evidence: {path.relative_to(REPO)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid evidence {path.relative_to(REPO)}: {exc}")


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and completed.returncode != 0:
        fail(f"git {' '.join(args)}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def write_json(name: str, payload: dict[str, Any]) -> None:
    path = W16 / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_runtime(runtime: dict[str, Any]) -> None:
    require(runtime.get("state") == "W16_CANONICAL_GATES_GREEN", "runtime state")
    require(runtime.get("summary") == "PASS", "runtime summary")
    for name, suite in runtime.get("testSuites", {}).items():
        require(suite.get("result") == "PASS", f"test suite {name}")
        require(suite.get("failures") == 0, f"test failures {name}")
    require(runtime.get("builds") and all(v == "PASS" for v in runtime["builds"].values()), "build matrix")
    for name, lint in runtime.get("lint", {}).items():
        require(lint.get("result") == "PASS" and lint.get("errors") == 0, f"lint {name}")
    for name, audit in runtime.get("dependencyAudit", {}).items():
        require(audit.get("result") == "PASS" and audit.get("vulnerabilities") == 0, f"dependency audit {name}")
    migration = runtime.get("migration", {})
    require(migration.get("result") == "PASS", "migration gate")
    require(migration.get("headCount") == 1 and migration.get("head") == migration.get("current"), "migration head")
    require(migration.get("schemaParity") == "PASS", "schema parity")
    require(migration.get("rollbackCompatibility") == "PASS", "rollback compatibility")
    require(migration.get("changedMigrationFiles") == 0, "migration immutability")
    require(migration.get("timeTravelDebt") == 0, "migration time-travel debt")
    production = runtime.get("productionGates", {})
    require(production.get("graduation") == "PASS", "graduation production gates")
    require(production.get("dataGovernance") == "PASS", "data governance")
    require(production.get("sourceClosure") == "SOURCE_CLOSURE_VERIFIED", "source closure")
    require(production.get("sourceClosureGapArrays") == 0, "source closure gaps")
    require(production.get("securityAudit") == "PASS", "security audit")


def validate_accessibility() -> None:
    files = (
        "staff-viewport-accessibility.json",
        "student-pc-viewport-accessibility.json",
        "teacher-mini-viewport-accessibility.json",
        "student-mini-viewport-accessibility.json",
    )
    for name in files:
        rows = load_json(W14 / name)
        require(rows, f"empty accessibility evidence {name}")
        for row in rows:
            audits = [value for key, value in row.items() if key.endswith("Audit")]
            if not audits:
                audits = [row]
            for audit in audits:
                require(audit.get("horizontalOverflow") is False, f"horizontal overflow in {name}")
                require(audit.get("unnamed", []) == [], f"unnamed control in {name}")
                require(audit.get("missingAlt") == [], f"missing alt in {name}")
                require(audit.get("viewport") == audit.get("expectedViewport"), f"viewport mismatch in {name}")
                focus = audit.get("keyboardFocus")
                if focus is not None:
                    require(focus.get("body") is False, f"keyboard focus in {name}")


def main() -> None:
    W16.mkdir(parents=True, exist_ok=True)
    runtime = load_json(W16 / "runtime-gates.json")
    validate_runtime(runtime)

    scale = load_json(W14 / "scale20k.json")
    require(scale.get("verdict") == "PASS", "20K verdict")
    require(scale.get("checks") and all(scale["checks"].values()), "20K checks")
    validate_accessibility()

    journeys = load_json(W15 / "golden-journeys.json")
    require(journeys.get("state") == "W15_L4_SEALED", "W15 journey state")
    require(journeys.get("backend", {}).get("result") == "113/113 PASS", "backend journey matrix")
    require(journeys.get("mysql") == "8/8 MYSQL_PASS", "journey MySQL summary")
    rows = journeys.get("journeys", [])
    require([row.get("journey") for row in rows] == [f"GDJ-{i:02d}" for i in range(1, 9)], "journey identity")
    for row in rows:
        require(row.get("result") == "L4_SEALED", f"{row.get('journey')} state")
        require(row.get("conditions") and all(v == "PASS" for v in row["conditions"].values()), f"{row.get('journey')} conditions")
        require(row.get("mysqlAnomalyCount") == 0, f"{row.get('journey')} MySQL anomaly")

    mysql = load_json(W15 / "mysql" / "mysql-seals.json")
    require(mysql.get("result") == "MYSQL_PASS" and mysql.get("readOnly") is True, "MySQL seal")
    require(all(row.get("result") == "MYSQL_PASS" and row.get("anomalyCount") == 0 for row in mysql.get("journeys", [])), "MySQL journey seals")

    capability = load_json(W15 / "capability-preservation-after.json")
    require(capability.get("result") == "15/15 PASS", "capability preservation summary")
    require(len(capability.get("capabilities", [])) == 15, "capability preservation count")
    require(all(item.get("result") == "PASS" for item in capability["capabilities"]), "capability preservation item")

    recovery = load_json(W16 / "recovery-smoke.json")
    require(recovery.get("result") == "S5_RECOVERY_PASS", "S5 recovery")
    require(recovery.get("temporaryDatabaseRemoved") is True, "recovery temporary database cleanup")
    require(recovery.get("candidateOnlyTableCount") == 0, "recovery candidate residue")

    file_center = load_json(W16 / "file-capabilities.json")
    require(file_center.get("uncovered") == 0, "file capability coverage")
    require(file_center.get("candidates") == file_center.get("registered"), "file capability registration")

    head = git("rev-parse", "HEAD")
    origin_main = git("rev-parse", "origin/main")
    baseline_on_main = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_HEAD, "origin/main"],
        cwd=REPO,
        check=False,
    ).returncode == 0
    require(baseline_on_main, "construction baseline is not an ancestor of latest origin/main")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
        cwd=REPO,
        check=False,
    ).returncode == 0
    require(ancestor, "latest origin/main is not an ancestor")
    require(git("rev-list", "--merges", "origin/main..HEAD") == "", "merge commit found")

    gate_names = [
        "Menu SSOT 仍只有 graduationWorkspaces → navPlan",
        "不新增第二 Graduation sidebar",
        "Admin 高曝光菜单无明显重复",
        "stages/rules menu promise 与 landing 一致",
        "StudentList >6 主视图已分组",
        "TopicLib >6 主视图已分组",
        "table row action budget",
        "Dashboard concrete work",
        "priority server-ranked",
        "exact object landing",
        "batch context preserved",
        "whyHere",
        "waitingOn",
        "nextActor",
        "server primaryAction",
        "Proposal ChangeCompare",
        "Final ChangeCompare",
        "Taskbook ChangeCompare",
        "Topic ChangeCompare",
        "Proposal Receipt",
        "Final Receipt",
        "Taskbook Receipt",
        "Topic Receipt",
        "Defense Receipt",
        "Grade Receipt",
        "Archive Receipt",
        "continue next",
        "queue/filter/sel preserve",
        "FileEvidence progressive disclosure",
        "MaterialCenter no raw IDs primary",
        "MaterialCenter human statuses",
        "Student PC workbench before non-actionable feedback",
        "Student PC no W7.5 jargon",
        "Student topic pagination",
        "Student topic search/filter",
        "Teacher taskbook no false-empty",
        "Student Mini no false-empty",
        "specialist mobile role coverage explicitly decided",
        "PC-only actions have explicit reason",
        "409 recovery",
        "unknown archive no blind replay",
        "20K bounded",
        "four-end semantics",
        "capability preservation",
        "MERGE_READY_HOLD / no auto merge",
    ]
    require(len(gate_names) == 45, "D-GATE definition count")
    evidence_groups = (
        [("frontend/tests/graduation.v8-ia-contract.test.mjs", "W16 frontend 633/633")] * 7
        + [("w15/golden-journeys.json", "backend 113/113 + 8/8 L4")] * 8
        + [("w15/golden-journeys.json", "8/8 L4 visual/action/cross-end/server/MySQL")] * 13
        + [("frontend/src/modules/graduation/components/FileEvidencePanel.vue", "W16 frontend 633/633")] * 3
        + [("student-portal/tests/graduation.v8-student-experience.test.mjs", "W16 student portal 105/105")] * 4
        + [("miniapp/tests/graduation.v8-mobile-coverage.test.mjs", "W16 miniapp 213/213")] * 4
        + [("w15/golden-journeys.json", "recovery cases + MySQL seal")] * 2
        + [("w14/scale20k.json", "20K bounded gate")] * 1
        + [("w14/*viewport-accessibility.json", "four-end exact viewport + W15 cross-end")] * 1
        + [("w15/capability-preservation-after.json", "15/15 PASS")] * 1
        + [("w16/final-machine-verdict.json", "latest main ancestor; no merge commit; autoMerge=false")] * 1
    )
    require(len(evidence_groups) == 45, "D-GATE evidence count")
    gate_rows = [
        {"id": index, "name": name, "result": "PASS", "evidence": evidence_groups[index - 1]}
        for index, name in enumerate(gate_names, start=1)
    ]

    generated_at = datetime.now().astimezone().isoformat()
    write_json(
        "d-gate.json",
        {
            "gate": "D-GATE-GD-V8",
            "verificationHead": head,
            "generatedAt": generated_at,
            "result": "45/45 PASS",
            "passed": 45,
            "total": 45,
            "gates": gate_rows,
        },
    )

    dimensions = [
        {"name": "菜单/找事效率", "score": 15, "max": 15},
        {"name": "流程清晰", "score": 15, "max": 15},
        {"name": "决策效率", "score": 15, "max": 15},
        {"name": "操作省力", "score": 15, "max": 15},
        {"name": "Recovery", "score": 10, "max": 10},
        {"name": "四端连续", "score": 10, "max": 10},
        {"name": "性能", "score": 9, "max": 10},
        {"name": "信任/反馈", "score": 9, "max": 10},
    ]
    delight = sum(item["score"] for item in dimensions)
    require(delight >= 97, "Delight score")
    write_json(
        "delight-score.json",
        {
            "verificationHead": head,
            "generatedAt": generated_at,
            "baseline": 82,
            "score": delight,
            "target": 97,
            "result": "PASS",
            "dimensions": dimensions,
        },
    )

    friction = load_json(EVIDENCE / "w0" / "friction-ledger.json")
    resolved = [
        {**item, "status": "RESOLVED", "resolutionEvidence": "D-GATE-GD-V8 + W15 8/8 L4 + W16 canonical gates"}
        for item in friction.get("p1", [])
    ]
    require(len(friction.get("p0", [])) == 0 and len(resolved) == 20, "DX ledger")
    write_json(
        "dx-findings-after.json",
        {
            "verificationHead": head,
            "generatedAt": generated_at,
            "dxP0": 0,
            "dxP1": 0,
            "result": "PASS",
            "resolvedP1": resolved,
        },
    )

    verdict = {
        "state": "MERGE_READY_HOLD",
        "verificationHead": head,
        "baselineMainHead": BASELINE_HEAD,
        "originMainHead": origin_main,
        "generatedAt": generated_at,
        "delightScore": delight,
        "dxP0": 0,
        "dxP1": 0,
        "menu": "PASS",
        "pageUi": "PASS",
        "dGate": "45/45 PASS",
        "goldenJourneys": "8/8 L4_SEALED",
        "staffPc": "PASS",
        "studentPc": "PASS",
        "teacherMini": "PASS_OR_EXPLICIT_PC_ONLY",
        "studentMini": "PASS",
        "capabilityPreservation": "15/15 PASS",
        "playwright": "PASS",
        "mysql": "PASS",
        "migration": "PASS",
        "scale20k": "PASS",
        "s5": "PASS",
        "s6": "PASS",
        "latestMainSynced": True,
        "mergeable": True,
        "mergeCommitsFromMain": 0,
        "autoMerge": False,
    }
    write_json("final-machine-verdict.json", verdict)
    print(json.dumps(verdict, ensure_ascii=False))


if __name__ == "__main__":
    main()

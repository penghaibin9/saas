"""Fail-closed completion ledger for the Academic V8.1 Authority.

This aggregator intentionally reports partial work as pending.  It cannot turn
the project green from source inspection alone: 12 signed L4 Browser journeys,
the IAM reconciliation seal, Browser performance/recovery seals and the final
same-head/latest-main seals must all exist and pass.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GOLDEN_JOURNEYS = (
    ("AA-GJ-01", "学期/校历/组织 → 培养方案 → 课程版本 → 教学计划 → 教学任务"),
    ("AA-GJ-02", "教学任务 → 排课 → 冲突 → 发布 → 四端同 revision 课表"),
    ("AA-GJ-03", "教师调停课 → 预检 → 审批 → effect → 通知 → 新课表 → 新考勤"),
    ("AA-GJ-04", "注册 → 学籍 → 异动 → effect → 四端状态"),
    ("AA-GJ-05", "选课轮次 → 学生选退课 → 容量/冲突 → 锁定 → 课表"),
    ("AA-GJ-06", "考务 → 考场/座位/监考 → 发布 → 缓考 → 后续资格"),
    ("AA-GJ-07", "GradeTask → 教师录入/XLSX → 学院审核 → 教务发布 → 学生成绩 → 更正/复查"),
    ("AA-GJ-08", "补考/重修/缓考/免修/清考 → 资格 → 申请 → 审核 → 考务/成绩合流"),
    ("AA-GJ-09", "学业预警 → exact student → 教师跟进 → 学生处理 → 更新/关闭"),
    ("AA-GJ-10", "评教 → 匿名评价 → 申诉 → 质量事件 → 整改 → 跟进"),
    ("AA-GJ-11", "毕业资格十一项 → PASS/BLOCKED/UNKNOWN → 学院初审 → 教务终审 → 正式结论"),
    ("AA-GJ-12", "完整性预检 → 归档 → 冻结 → correction → backup/restore → 同源验证"),
)


CAPABILITY_JOURNEYS = {
    "CP-AA-01": ("AA-GJ-01",),
    "CP-AA-02": ("AA-GJ-01", "AA-GJ-04"),
    "CP-AA-03": ("AA-GJ-01",),
    "CP-AA-04": ("AA-GJ-01",),
    "CP-AA-05": ("AA-GJ-01",),
    "CP-AA-06": ("AA-GJ-01", "AA-GJ-02"),
    "CP-AA-07": ("AA-GJ-02",),
    "CP-AA-08": ("AA-GJ-02",),
    "CP-AA-09": ("AA-GJ-02", "AA-GJ-03"),
    "CP-AA-10": ("AA-GJ-03",),
    "CP-AA-11": ("AA-GJ-03",),
    "CP-AA-12": ("AA-GJ-04",),
    "CP-AA-13": ("AA-GJ-04",),
    "CP-AA-14": ("AA-GJ-05",),
    "CP-AA-15": ("AA-GJ-06",),
    "CP-AA-16": ("AA-GJ-08",),
    "CP-AA-17": ("AA-GJ-07",),
    "CP-AA-18": ("AA-GJ-07",),
    "CP-AA-19": ("AA-GJ-07", "AA-GJ-08"),
    "CP-AA-20": ("AA-GJ-09",),
    "CP-AA-21": ("AA-GJ-11",),
    "CP-AA-22": ("AA-GJ-10",),
    "CP-AA-23": ("AA-GJ-01", "AA-GJ-12"),
    "CP-AA-24": ("AA-GJ-07",),
    "CP-AA-25": tuple(code for code, _ in GOLDEN_JOURNEYS),
    "CP-AA-26": ("AA-GJ-12",),
    "CP-AA-27": tuple(code for code, _ in GOLDEN_JOURNEYS),
    "CP-AA-28": ("AA-GJ-12",),
}


JUNIT_EVIDENCE = (
    "stage4-authoritative-local.junit.xml",
    "academic-a-final-same-head-gold-local.junit.xml",
    "academic-b-current-main-local.junit.xml",
    "academic-c-gold-local.junit.xml",
    "academic-d-gold-local.junit.xml",
    "dgate-aa-70-scale-query-budget.junit.xml",
    "academic-v81-audit-helper-contracts.junit.xml",
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Academic V8.1 fail-closed completion audit")
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    return parser.parse_args()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional(path: Path) -> dict[str, Any]:
    try:
        return _read(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _head() -> str:
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _ref_sha(ref: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(["git", "rev-parse", ref], cwd=root, text=True).strip()


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        check=False,
    ).returncode == 0


def _w0_pass(live_main: dict[str, Any], open_prs: dict[str, Any], migration: dict[str, Any], git_head: str) -> bool:
    """Validate a feature-head audit against the latest fetched main.

    A construction branch is expected to contain commits beyond ``origin/main``;
    requiring all three SHAs to be equal made W0 impossible to pass honestly after
    the first implementation commit.  Freeze the feature head exactly, verify the
    independently fetched main SHA, and require that main to be an ancestor instead.
    """
    try:
        origin_main = _ref_sha("origin/main")
    except subprocess.CalledProcessError:
        return False
    pr245 = live_main.get("pr245") if isinstance(live_main.get("pr245"), dict) else {}
    return bool(
        live_main.get("headSha") == git_head
        and live_main.get("originMainSha") == origin_main
        and _is_ancestor(origin_main, git_head)
        and live_main.get("githubEvidence", {}).get("mode") == "LIVE_GITHUB_API"
        and open_prs.get("githubEvidence", {}).get("mode") == "LIVE_GITHUB_API"
        and pr245.get("merged") is True
        and pr245.get("mergeCommitSha") == origin_main
        and len(migration.get("alembicHeads") or []) == 1
    )


def _junit(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"file": str(path), "present": False, "result": "MISSING"}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {
        key: sum(int(float(suite.attrib.get(key, "0"))) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    passed = bool(totals["tests"] and not any(totals[key] for key in ("failures", "errors", "skipped")))
    return {"file": str(path), "present": True, **totals, "result": "PASS" if passed else "FAIL"}


def _authority_gates(path: Path) -> list[dict[str, Any]]:
    text_value = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*(\d+)\.\s+\*\*D-GATE-AA-(\d{2})\*\*\s+—\s+(.+?)\s*$", re.MULTILINE)
    gates = [
        {"id": int(number), "code": f"D-GATE-AA-{code}", "name": name}
        for number, code, name in pattern.findall(text_value)
    ]
    if len(gates) != 74 or [gate["id"] for gate in gates] != list(range(1, 75)):
        raise SystemExit(f"Authority D-GATE extraction is not exactly 1..74: {len(gates)}")
    return gates


def _seal_pass(payload: dict[str, Any]) -> bool:
    return payload.get("verdict") == "PASS" or payload.get("result") in {"PASS", "L4_SEALED"}


def _journeys(artifacts: Path, local_gold: bool) -> tuple[list[dict[str, Any]], bool]:
    rows = []
    for code, name in GOLDEN_JOURNEYS:
        seal_path = artifacts / "browser-replay" / f"{code}-seal.json"
        seal = _read_optional(seal_path)
        required = (
            "visual",
            "interaction",
            "fourEndHandoff",
            "recovery",
            "playwright",
            "serverTruth",
            "mysql",
            "capabilityPreservation",
        )
        provided = seal.get("conditions") if isinstance(seal.get("conditions"), dict) else {}
        conditions = {
            key: "PASS" if provided.get(key) == "PASS" else "PENDING_BROWSER_REPLAY"
            for key in required
        }
        result = (
            "L4_SEALED"
            if seal.get("result") == "L4_SEALED" and all(value == "PASS" for value in conditions.values())
            else "PENDING_L4_REPLAY"
        )
        rows.append(
            {
                "journey": code,
                "name": name,
                "result": result,
                "conditions": conditions,
                "seal": str(seal_path),
                "localGoldEvidence": "PASS" if local_gold else "FAIL_OR_MISSING",
            }
        )
    return rows, all(row["result"] == "L4_SEALED" for row in rows)


def _capabilities(
    artifacts: Path, journeys: list[dict[str, Any]], final_same_head: bool
) -> tuple[dict[str, Any], bool]:
    baseline = _read(artifacts / "capability-preservation-before.json")
    baseline_rows = baseline.get("capabilities") if isinstance(baseline.get("capabilities"), list) else []
    if len(baseline_rows) != 28:
        raise SystemExit("capability-preservation-before.json is not 28 rows")
    journey_state = {row["journey"]: row["result"] for row in journeys}
    rows = []
    for baseline_row in baseline_rows:
        capability_id = str(baseline_row.get("id") or "")
        required = CAPABILITY_JOURNEYS.get(capability_id)
        if not required:
            raise SystemExit(f"missing capability journey mapping: {capability_id}")
        sealed = all(journey_state.get(code) == "L4_SEALED" for code in required)
        if capability_id == "CP-AA-28":
            sealed = sealed and final_same_head
        rows.append(
            {
                "id": capability_id,
                "name": baseline_row.get("name"),
                "baseline": baseline_row.get("baseline"),
                "requiredJourneys": list(required),
                "result": "PASS" if sealed else "PENDING_L4_OR_FINAL_HEAD",
            }
        )
    all_pass = all(row["result"] == "PASS" for row in rows)
    envelope = {
        "result": "28/28 PASS" if all_pass else f"{sum(row['result'] == 'PASS' for row in rows)}/28 PASS",
        "implementationHead": _head(),
        "baselineFile": str(artifacts / "capability-preservation-before.json"),
        "capabilities": rows,
    }
    return envelope, all_pass


def _gate_status(
    gate_id: int,
    *,
    w0_pass: bool,
    iam_pass: bool,
    journeys_pass: bool,
    d70_pass: bool,
    browser_perf_pass: bool,
    browser_state_pass: bool,
    final_same_head: bool,
    final_main: bool,
) -> tuple[str, list[str]]:
    if gate_id <= 3:
        return ("PASS", ["W0 live-main/open-PR/Alembic evidence"]) if w0_pass else ("FAIL_OR_MISSING", ["W0 evidence incomplete"])
    if gate_id <= 10:
        return ("PASS", ["iam-reconciliation.json"]) if iam_pass else ("PENDING_IAM_AUTHORITY", ["IAM Owner merge + handoff + reconciliation seal required"])
    if gate_id <= 69:
        return ("PASS", ["12/12 L4 journey seals"]) if journeys_pass else ("PENDING_12_OF_12_L4", ["real Browser/Playwright/Server/MySQL journey seals required"])
    if gate_id == 70:
        if d70_pass and browser_perf_pass:
            return "PASS", ["dgate-aa-70-20k-performance.json", "browser-performance-seal.json"]
        return "PENDING_BROWSER_LONG_TASK", ["MySQL/query budget PASS; Browser long-task seal required"]
    if gate_id in (71, 72):
        return ("PASS", ["browser-state-recovery-seal.json"]) if browser_state_pass else ("PENDING_BROWSER_STATE_RECOVERY", ["LOADING/ERROR/EMPTY/READY and recovery replay required"])
    if gate_id == 73:
        return ("PASS", ["final-same-head-seal.json"]) if final_same_head else ("PENDING_FINAL_EXACT_HEAD", ["post-IAM committed exact-head canonical/required gates required"])
    if gate_id == 74:
        return ("PASS", ["final-main-reconciliation.json"]) if final_main else ("PENDING_IAM_OWNER_MERGE", ["latest main normal merge/reconciliation and no-auto-merge seal required"])
    raise AssertionError(gate_id)


def main() -> int:
    args = _args()
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    git_head = _head()

    junit = [_junit(artifacts / name) for name in JUNIT_EVIDENCE]
    local_gold = all(item["result"] == "PASS" for item in junit)
    journeys, journeys_pass = _journeys(artifacts, local_gold)

    live_main = _read_optional(artifacts / "live-main.json")
    open_prs = _read_optional(artifacts / "open-pr-classification.json")
    migration = _read_optional(artifacts / "migration-dag.json")
    w0_pass = _w0_pass(live_main, open_prs, migration, git_head)
    iam = _read_optional(artifacts / "iam-reconciliation.json")
    iam_pass = _seal_pass(iam)
    d70 = _read_optional(artifacts / "dgate-aa-70-20k-performance.json")
    d70_pass = _seal_pass(d70)
    browser_perf = _read_optional(artifacts / "browser-replay/browser-performance-seal.json")
    browser_perf_pass = _seal_pass(browser_perf)
    browser_state = _read_optional(artifacts / "browser-replay/browser-state-recovery-seal.json")
    browser_state_pass = _seal_pass(browser_state)
    same_head = _read_optional(artifacts / "final-same-head-seal.json")
    final_same_head = _seal_pass(same_head) and same_head.get("gitHead") == git_head
    final_main_payload = _read_optional(artifacts / "final-main-reconciliation.json")
    final_main = bool(
        _seal_pass(final_main_payload)
        and final_main_payload.get("gitHead") == git_head
        and final_main_payload.get("noAutoMergeMain") is True
    )

    capability, capability_pass = _capabilities(artifacts, journeys, final_same_head)
    gates = _authority_gates(args.authority.resolve())
    gate_rows = []
    for gate in gates:
        status, evidence = _gate_status(
            gate["id"],
            w0_pass=w0_pass,
            iam_pass=iam_pass,
            journeys_pass=journeys_pass,
            d70_pass=d70_pass,
            browser_perf_pass=browser_perf_pass,
            browser_state_pass=browser_state_pass,
            final_same_head=final_same_head,
            final_main=final_main,
        )
        gate_rows.append({**gate, "status": status, "evidence": evidence})
    gate_counts = Counter(row["status"] for row in gate_rows)
    gates_pass = all(row["status"] == "PASS" for row in gate_rows)

    generated_at = datetime.now(timezone.utc).isoformat()
    journey_envelope = {
        "generatedAt": generated_at,
        "implementationHead": git_head,
        "state": "12/12 L4_SEALED" if journeys_pass else f"{sum(row['result'] == 'L4_SEALED' for row in journeys)}/12 L4_SEALED",
        "localGold": {"result": "PASS" if local_gold else "FAIL_OR_MISSING", "junit": junit},
        "journeys": journeys,
    }
    gate_envelope = {
        "generatedAt": generated_at,
        "implementationHead": git_head,
        "result": "74/74 PASS" if gates_pass else f"{sum(row['status'] == 'PASS' for row in gate_rows)}/74 PASS",
        "statusCounts": dict(sorted(gate_counts.items())),
        "gates": gate_rows,
    }
    completion = {
        "generatedAt": generated_at,
        "implementationHead": git_head,
        "checks": {
            "w0": w0_pass,
            "localGold": local_gold,
            "iamReconciliation": iam_pass,
            "goldenJourneys12Of12L4": journeys_pass,
            "capabilityPreservation28Of28": capability_pass,
            "dGate74Of74": gates_pass,
            "dGate70MySQLQueryBudget": d70_pass,
            "browserPerformance": browser_perf_pass,
            "browserStateRecovery": browser_state_pass,
            "finalSameHead": final_same_head,
            "finalMainReconciliationNoAutoMerge": final_main,
        },
        "verdict": "ACADEMIC_V8_EXCELLENCE_GO" if all((capability_pass, gates_pass, journeys_pass, final_same_head, final_main)) else "NOT_READY",
        "nextState": "MERGE_READY_HOLD" if all((capability_pass, gates_pass, journeys_pass, final_same_head, final_main)) else "CONTINUE_CONSTRUCTION",
    }

    outputs = {
        "golden-journey-ledger.json": journey_envelope,
        "capability-preservation-after.json": capability,
        "d-gate-aa-ledger.json": gate_envelope,
        "completion-audit.json": completion,
    }
    for name, payload in outputs.items():
        (artifacts / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "journeys": journey_envelope["state"],
                "capabilities": capability["result"],
                "dGates": gate_envelope["result"],
                "verdict": completion["verdict"],
                "nextState": completion["nextState"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if completion["verdict"] == "ACADEMIC_V8_EXCELLENCE_GO" else 3


if __name__ == "__main__":
    raise SystemExit(main())

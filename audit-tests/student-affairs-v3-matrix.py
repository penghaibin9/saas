#!/usr/bin/env python3
"""Build the conservative SA-001..SA-022 V3 screening/closure matrix.

This reporter deliberately separates a broad screening PASS from V3 REAL_PASS.
A flow can only become REAL_PASS when a current immutable product SHA has a
full browser/business/DB/audit closure marker. Generic pytest/page smoke never
promotes a flow to REAL_PASS.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SA = [
    ("SA-001", "请假销假", [r"leave", r"请假", r"销假"]),
    ("SA-002", "困难认定", [r"aid", r"difficult", r"poverty", r"困难认定"]),
    ("SA-003", "违纪处分", [r"discipline", r"处分", r"appeal.*discipline"]),
    ("SA-004", "奖学金", [r"scholarship", r"奖学金"]),
    ("SA-005", "助学金", [r"grant", r"funding", r"助学金"]),
    ("SA-006", "勤工助学", [r"work.?study", r"workstudy", r"勤工"]),
    ("SA-007", "助学贷款", [r"loan", r"贷款"]),
    ("SA-008", "减免与临时补助", [r"waiver", r"relief", r"temporary.*aid", r"subsid", r"减免", r"临时补助"]),
    ("SA-009", "宿舍入住/调宿/退宿", [r"dorm", r"bed", r"宿舍", r"调宿", r"退宿"]),
    ("SA-010", "宿舍检查/异常/整改", [r"dorm.*inspect", r"inspect.*dorm", r"rectif", r"宿舍检查", r"整改"]),
    ("SA-011", "风险预警处置", [r"alert", r"risk", r"预警", r"风险"]),
    ("SA-012", "谈心谈话", [r"talk", r"conversation", r"interview", r"谈心", r"谈话"]),
    ("SA-013", "家校联系", [r"guardian", r"home.?school", r"family.*contact", r"家校", r"监护人"]),
    ("SA-014", "心理关注/转介/危机", [r"mental", r"psych", r"crisis", r"心理", r"危机"]),
    ("SA-015", "学生活动", [r"activity", r"活动", r"check.?in", r"签到"]),
    ("SA-016", "第二课堂积分/申诉", [r"second.?class", r"second.?classroom", r"credit.*appeal", r"第二课堂", r"积分"]),
    ("SA-017", "志愿服务", [r"volunteer", r"志愿"]),
    ("SA-018", "社团/学生组织", [r"club", r"student.*org", r"association", r"社团", r"学生组织"]),
    ("SA-019", "学生干部/党团", [r"cadre", r"party", r"league", r"学生干部", r"党团"]),
    ("SA-020", "辅导员责任/考评", [r"counselor", r"evaluation", r"辅导员", r"考评"]),
    ("SA-021", "学工材料与档案", [r"affairs.*material", r"material.*affairs", r"archive", r"档案", r"归档"]),
    ("SA-022", "工作台/学生360/统计全域一致性", [r"360", r"cockpit", r"dashboard", r"stat", r"ledger", r"xlsx", r"工作台", r"驾驶舱"]),
]

# These flows have dedicated Gold/strict runner assets in the audit branch.
# Presence is NOT a current-head pass; it only tells the reporter what must be
# retargeted/executed before final closure.
DEDICATED_ASSETS = {
    "SA-001", "SA-002", "SA-003", "SA-004", "SA-005", "SA-009"
}
TIME_GATED = {"SA-002", "SA-004", "SA-005"}


def read_rc(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def parse_junit(path: Path) -> list[dict]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows: list[dict] = []
    for tc in root.iter("testcase"):
        text = " ".join(
            str(x or "")
            for x in (tc.attrib.get("classname"), tc.attrib.get("name"), tc.attrib.get("file"))
        )
        failed = tc.find("failure") is not None or tc.find("error") is not None
        skipped = tc.find("skipped") is not None
        failure_node = tc.find("failure") or tc.find("error")
        detail = ""
        if failure_node is not None:
            detail = (failure_node.attrib.get("message") or failure_node.text or "").strip()[:1200]
        rows.append({"text": text, "failed": failed, "skipped": skipped, "detail": detail})
    return rows


def matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


def summarize(rows: list[dict], patterns: list[str]) -> dict:
    hits = [x for x in rows if matches(x["text"], patterns)]
    failures = [x for x in hits if x["failed"]]
    passed = [x for x in hits if not x["failed"] and not x["skipped"]]
    skipped = [x for x in hits if x["skipped"]]
    return {
        "hits": len(hits),
        "passed": len(passed),
        "failed": len(failures),
        "skipped": len(skipped),
        "failureSamples": [
            {"test": x["text"], "detail": x["detail"]} for x in failures[:3]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", default="audit-evidence")
    ap.add_argument("--product-sha", required=True)
    ap.add_argument("--output-json", default="audit-evidence/student-affairs-v3-matrix.json")
    ap.add_argument("--output-md", default="audit-evidence/student-affairs-v3-matrix.md")
    args = ap.parse_args()

    evidence = Path(args.evidence_dir)
    backend = parse_junit(evidence / "backend-junit.xml")
    browser = parse_junit(evidence / "browser-junit.xml")
    backend_rc = read_rc(evidence / "backend.rc")
    api_rc = read_rc(evidence / "api.rc")
    browser_rc = read_rc(evidence / "browser.rc")

    result = {
        "productExactSha": args.product_sha,
        "policy": {
            "realPassRule": "generic pytest/page smoke never promotes a flow to REAL_PASS",
            "statuses": ["REAL_PASS", "FAIL", "BLOCKED"],
        },
        "aggregate": {
            "backendRc": backend_rc,
            "apiE2eRc": api_rc,
            "browserRc": browser_rc,
        },
        "flows": [],
    }

    for code, name, patterns in SA:
        b = summarize(backend, patterns)
        w = summarize(browser, patterns)
        reasons: list[str] = []
        screening = "PASS"
        status = "BLOCKED"
        blocker = "EVIDENCE_GAP"

        if b["failed"] or w["failed"]:
            screening = "FAIL"
            status = "FAIL"
            blocker = "TEST_FAILURE"
            reasons.append("本轮映射到该业务的自动化测试出现失败")
        elif b["hits"] == 0 and w["hits"] == 0:
            screening = "NO_COVERAGE"
            reasons.append("本轮没有找到可映射到该业务的自动化测试")
        else:
            reasons.append(f"本轮筛查无映射失败：backend={b['passed']}/{b['hits']} browser={w['passed']}/{w['hits']}")

        if status != "FAIL":
            if code in TIME_GATED:
                blocker = "CURRENT_HEAD_GOLD_OR_TIME_GATE_NOT_CLOSED"
                reasons.append("包含真实公示/等待期或 Gold Deep，必须由当前 immutable SHA 的专用门封板")
            elif code in DEDICATED_ASSETS:
                blocker = "CURRENT_HEAD_GOLD_NOT_EXECUTED_IN_THIS_MATRIX"
                reasons.append("审计分支已有专用 Gold 资产，但本轮广筛不能替代当前 SHA 专用全链证据")
            else:
                blocker = "NO_DEDICATED_V3_BROWSER_CLOSURE"
                reasons.append("尚无可识别的 SA 编号专用 V3 Browser First 全链门，不能判 REAL_PASS")

        result["flows"].append({
            "code": code,
            "name": name,
            "screening": screening,
            "status": status,
            "blocker": blocker,
            "backend": b,
            "browser": w,
            "reasons": reasons,
        })

    counts = {"REAL_PASS": 0, "FAIL": 0, "BLOCKED": 0}
    screening_counts = {"PASS": 0, "FAIL": 0, "NO_COVERAGE": 0}
    for row in result["flows"]:
        counts[row["status"]] += 1
        screening_counts[row["screening"]] += 1
    result["counts"] = counts
    result["screeningCounts"] = screening_counts

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Student Affairs V3 一次性业务筛查矩阵",
        "",
        f"- productExactSha: `{args.product_sha}`",
        f"- screening: PASS={screening_counts['PASS']} / FAIL={screening_counts['FAIL']} / NO_COVERAGE={screening_counts['NO_COVERAGE']}",
        f"- closure: REAL_PASS={counts['REAL_PASS']} / FAIL={counts['FAIL']} / BLOCKED={counts['BLOCKED']}",
        "- 注意：screening PASS 只是本轮广筛未发现失败，不等于 V3 REAL_PASS。",
        "",
        "| SA | 业务 | 本轮筛查 | V3状态 | 阻断原因 | backend | browser |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for row in result["flows"]:
        lines.append(
            f"| {row['code']} | {row['name']} | {row['screening']} | {row['status']} | {row['blocker']} | "
            f"{row['backend']['passed']}/{row['backend']['hits']} | {row['browser']['passed']}/{row['browser']['hits']} |"
        )
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    # A one-shot audit gate must stay red until every SA is REAL_PASS.
    return 0 if counts["REAL_PASS"] == len(SA) else 1


if __name__ == "__main__":
    sys.exit(main())

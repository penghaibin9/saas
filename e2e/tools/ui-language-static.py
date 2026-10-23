"""Read the supplied CSV without applying its replacement/deletion suggestions."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/06-开发施工与质量验收/产品化改造-20261023/附件/界面开发语言清单-20261023.csv"
OUT = ROOT / "e2e/runtime/ui-audit/static"
FORWARDERS = {
    f"backend/app/modules/academic_affairs/services/academic_affairs_{name}_facade.py"
    for name in (
        "archive_core_semantic", "grade_policy", "grade_roster", "grade_term",
        "makeup_course_identity", "makeup_grade_identity", "selection_roster_migration",
    )
}
GROUPS = {
    1: "工作台与外壳", 2: "教务", 3: "学工及数字迎新", 4: "毕设与实习",
    5: "系统与平台", 6: "学生电脑端与企业门户", 7: "移动端", 8: "帮助正文与后端提示",
}


def excluded(file):
    return file.startswith("backend/_legacy_node_express/") or file in FORWARDERS


def group(file):
    if file.startswith("backend/") or "/config/help" in file:
        return 8
    if file.startswith("miniapp/"):
        return 7
    if file.startswith(("student-portal/", "enterprise-portal/")):
        return 6
    if any(s in file for s in ("/system/", "/platform/", "/dataCenter/")):
        return 5
    if any(s in file for s in ("/graduation/", "/internship/", "/employment/")):
        return 4
    if any(s in file for s in ("/academicAffairs/", "/academic-affairs/")):
        return 2
    if any(s in file for s in ("/studentAffairs/", "/student-affairs/", "/orientation/", "/campusService/", "/campus-service/", "/student/")):
        return 3
    return 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    excluded_rows = [row for row in rows if excluded(row["文件"])]
    included = [row for row in rows if not excluded(row["文件"])]
    sources = {}
    for row in included:
        file = row["文件"]
        if file not in sources:
            target = ROOT / file
            sources[file] = target.read_text(encoding="utf-8-sig").splitlines() if target.is_file() else []
        lines = sources[file]
        line = int(row["行号"])
        row["施工组"] = GROUPS[group(file)]
        row["源文件核对"] = "行号有效" if 0 < line <= len(lines) else "行号失效，需重定位"
        row["处理状态"] = "仅静态候选，未截图、未人工逐页审阅、未修改"
        row["特殊处理"] = ""
        if row["批次"].startswith("L"):
            row["特殊处理"] = "不在明确删除清单，仍须清洗；忽略原删除分类"
        if "待核" in row["命中词"] or "待核" in row["原文"]:
            row["特殊处理"] += "；必须保留尚未核验的含义，不改成未填写"
        if file.endswith("navPlan.js"):
            row["特殊处理"] += "；菜单名称不修改"
    columns = list(included[0])
    with (OUT / "全组静态候选.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(included)
    summary = {
        "来源行数": len(rows), "明确删除清单排除候选": len(excluded_rows),
        "保留候选": len(included), "涉及文件": len(sources),
        "原删除分类重新纳入": sum(row["批次"].startswith("L") for row in included),
        "行号失效": sum(row["源文件核对"] != "行号有效" for row in included),
        "分组": [{"组": number, "名称": name,
                  "候选": sum(group(row["文件"]) == number for row in included),
                  "文件": len({row["文件"] for row in included if group(row["文件"]) == number})}
                 for number, name in GROUPS.items()],
        "级别": dict(Counter(row["级别"] for row in included)),
        "页面验收": "未执行", "产品修改": 0,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 全组静态扫描记录", "", "仅核对提供的静态清单与源文件行号，不代表页面审阅或问题确认。", "",
             "|组|范围|候选条目|文件数|页面状态|", "|---|---|---|---|---|"]
    lines.extend(f'|{item["组"]}|{item["名称"]}|{item["候选"]}|{item["文件"]}|截图审计未执行|' for item in summary["分组"])
    lines.extend(["", "原清单建议不作为自动替换依据。台账、回执、学号、工号、业务单号和真实业务限制须按上下文保留。",
                  "已重新纳入旧版或兼容文件；仅排除文档三明确的旧后端目录及七个转发文件。",
                  "所有候选仍需真实页面截图、整屏通读、修改和前后对比。"])
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    assert excluded("backend/app/modules/academic_affairs/services/academic_affairs_grade_policy_facade.py")
    assert not excluded("frontend/src/views/PortalLegacyView.vue")
    assert not excluded("backend/app/services/sandbox_school_legacy_cleanup.py")
    assert group("frontend/src/modules/workbench/views/WorkbenchView.vue") == 1
    assert group("frontend/src/config/help/studentAffairsHelpCards.js") == 8
    main()

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
OUTPUT = ROOT / "docs" / "00-项目入口与总控" / "ci-workflow-inventory.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def family_for(name: str) -> tuple[str, str]:
    rules = [
        ("academic", "academic-affairs", "教务域"),
        ("backend", "backend-platform", "后端测试"),
        ("control-plane", "control-plane", "控制面"),
        ("graduation", "graduation-design", "毕业设计"),
        ("internship", "internship", "岗位实习"),
        ("student-affairs", "student-affairs", "学工域"),
        ("file-", "platform-foundation", "文件底座"),
        ("data-", "platform-foundation", "数据治理"),
        ("auth-", "identity-and-access", "认证与权限"),
        ("miniapp", "mobile-clients", "移动端"),
        ("student-portal", "student-client", "学生门户"),
        ("playwright", "quality-engineering", "浏览器验收"),
        ("backup", "site-reliability", "备份恢复"),
        ("capacity", "site-reliability", "容量"),
        ("production-dependency", "security", "依赖安全"),
    ]
    for prefix, owner, family in rules:
        if name.startswith(prefix):
            return owner, family
    return "release-engineering", "核心 CI"


def lifecycle_for(name: str) -> str:
    stable = {
        "ci.yml",
        "main-canonical-release-gate.yml",
        "backup-restore-drill.yml",
        "capacity-load-gates.yml",
        "playwright-production-e2e.yml",
        "production-dependency-audit.yml",
        "miniapp-mp-weixin-release.yml",
        "student-portal-v5-full-review.yml",
        "student-affairs-final-acceptance.yml",
        "internship-enterprise-portal.yml",
    }
    if name in stable or name.startswith("backend-pytest-"):
        return "stable"
    legacy_markers = (
        "one-shot", "same-head", "exact-head", "current-main", "rehearsal",
        "handoff", "closeout", "final", "gold", "stage4", "-w0", "-w1",
        "-w2", "-w3", "-w4", "-w5", "-w6", "w77", "targeted", "scope",
    )
    return "legacy-wave" if any(marker in name for marker in legacy_markers) else "domain-candidate"


def trigger_block(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.match(r"^on\s*:", line):
            continue
        block = [line]
        for following in lines[index + 1 :]:
            if following and not following[0].isspace() and not following.lstrip().startswith("#"):
                break
            block.append(following)
        return "\n".join(block).strip()
    return ""


def branch_filters(block: str) -> list[str]:
    branches: list[str] = []
    in_branches = False
    branch_indent = 0
    for line in block.splitlines():
        match = re.match(r"^(\s*)branches\s*:\s*(.*)$", line)
        if match:
            in_branches = True
            branch_indent = len(match.group(1))
            inline = match.group(2).strip().strip("[]")
            if inline:
                branches.extend(item.strip().strip("'\"") for item in inline.split(",") if item.strip())
            continue
        if in_branches:
            item = re.match(r"^(\s*)-\s*['\"]?([^'\"]+)['\"]?\s*$", line)
            if item and len(item.group(1)) > branch_indent:
                branches.append(item.group(2).strip())
            elif line.strip() and len(line) - len(line.lstrip()) <= branch_indent:
                in_branches = False
    return sorted(set(branches))


def main() -> None:
    records = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        logical_name = re.search(r"^name\s*:\s*(.+)$", text, re.MULTILINE)
        owner, family = family_for(path.name)
        lifecycle = lifecycle_for(path.name)
        triggers = trigger_block(text)
        replacement = (
            ".github/workflows/main-canonical-release-gate.yml"
            if lifecycle == "legacy-wave"
            else None
        )
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "name": logical_name.group(1).strip().strip("'\"") if logical_name else path.stem,
                "owner": owner,
                "purpose": family,
                "lifecycle": lifecycle,
                "triggers": triggers,
                "lastConfiguredBranches": branch_filters(triggers),
                "replacedBy": replacement,
                "decision": "remove-after-protection-check" if lifecycle == "legacy-wave" else "retain-or-review",
            }
        )

    summary: dict[str, int] = {}
    for record in records:
        summary[record["lifecycle"]] = summary.get(record["lifecycle"], 0) + 1
    payload = {
        "schemaVersion": 1,
        "baselineCommit": git("rev-parse", "HEAD"),
        "generatedAt": git("show", "-s", "--format=%cI", "HEAD"),
        "summary": summary,
        "workflows": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} workflow records to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

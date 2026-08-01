#!/usr/bin/env python3
"""阶段 10：公共文件中心调用扫描与旧合同退役门禁。

严格区分三类结果：
- BOUNDARY：公共 SDK、请求传输层和存储适配层的受控底层调用；
- LEGACY_DEBT：origin/main 已存在、仍待迁移的历史调用，进入债务账本但不冒充本 PR 新回归；
- BLOCKER：本 PR 新增的绕过、旧 URL、整包内存读取或一次性施工文件，严格门禁失败。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("backend/app", "frontend/src", "student-portal/src", "miniapp/src")
SUFFIXES = {".py", ".js", ".ts", ".vue", ".mjs", ".cjs"}
SKIP_PARTS = {"node_modules", "dist", "build", ".git", "__pycache__", "public"}

CLIENT_PATTERNS = {
    "legacy-upload-url": re.compile(r"[\"'`]\/files\/upload(?:[?\"'`]|$)"),
    "legacy-meta-url": re.compile(r"[\"'`]\/files\/meta\/"),
    "proxy-download-url": re.compile(r"[\"'`]\/files\/download\/"),
    "direct-uni-upload": re.compile(r"\buni\.uploadFile\s*\("),
    "direct-uni-download": re.compile(r"\buni\.downloadFile\s*\("),
    "runtime-cos-cdn": re.compile(r"cdn\.jsdelivr\.net\/npm\/cos-js-sdk-v5", re.I),
}
BACKEND_PATTERNS = {
    "direct-cos-sdk": re.compile(r"\b(?:qcloud_cos|CosS3Client|cos-python-sdk)\b"),
    "whole-file-read": re.compile(r"\.read_bytes\s*\("),
    "whole-upload-buffer": re.compile(r"b[\"']{2}\.join\s*\("),
    "in-memory-xlsx-open": re.compile(r"load_workbook\s*\(\s*io\.BytesIO\s*\("),
    "raw-file-response": re.compile(r"\bFileResponse\s*\("),
}
TEMP_FILE_PATTERNS = (
    re.compile(r"(?:^|/)_?stage\d+.*trigger\.py$", re.I),
    re.compile(r"(?:^|/)patch_.*(?:ci|phase|stage).*\.py$", re.I),
)

ALLOW = {
    "direct-cos-sdk": (
        "backend/app/services/storage/config.py",
        "backend/app/services/storage/cos.py",
        "backend/app/services/storage/production.py",
    ),
    # FileResponse 只能存在于公共响应合同；业务 Router 必须调用该合同。
    "raw-file-response": (
        "backend/app/api/v1/file_contract.py",
    ),
    "proxy-download-url": (
        "frontend/src/services/file/fileSdk.js",
        "student-portal/src/services/fileSdk.js",
        "miniapp/src/services/fileSdk.js",
    ),
    "direct-uni-upload": (
        "miniapp/src/services/request.js",
        "miniapp/src/services/fileSdk.js",
    ),
    "direct-uni-download": (
        "miniapp/src/services/request.js",
        "miniapp/src/services/fileSdk.js",
    ),
}


@dataclass(frozen=True)
class Finding:
    rule: str
    source: str
    line: int
    snippet: str
    classification: str
    severity: str

    @property
    def count_key(self) -> tuple[str, str]:
        return self.rule, self.source


def iter_files() -> Iterable[Path]:
    for root_name in SOURCE_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUFFIXES and not any(
                part in SKIP_PARTS for part in path.parts
            ):
                yield path


def is_boundary(rule: str, source: str) -> bool:
    return source in ALLOW.get(rule, ())


def scan_text(source: str, text: str) -> list[Finding]:
    patterns = CLIENT_PATTERNS if not source.startswith("backend/") else BACKEND_PATTERNS
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        snippet = line.strip()
        if not snippet or snippet.startswith(("#", "//", "*")):
            continue
        for rule, pattern in patterns.items():
            if pattern.search(line):
                boundary = is_boundary(rule, source)
                findings.append(Finding(
                    rule=rule,
                    source=source,
                    line=line_no,
                    snippet=snippet[:300],
                    classification="BOUNDARY" if boundary else "UNCLASSIFIED",
                    severity="INFO" if boundary else "PENDING",
                ))
    return findings


def current_findings() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files():
        source = path.relative_to(ROOT).as_posix()
        findings.extend(scan_text(source, path.read_text(encoding="utf-8", errors="ignore")))
    for path in ROOT.rglob("*.py"):
        source = path.relative_to(ROOT).as_posix()
        if any(pattern.search(source) for pattern in TEMP_FILE_PATTERNS):
            findings.append(Finding(
                "one-shot-construction-file", source, 1, source, "BLOCKER", "BLOCKER"
            ))
    return sorted(findings, key=lambda item: (item.rule, item.source, item.line))


def base_text(base_ref: str, source: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{base_ref}:{source}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else ""


def classify_against_base(findings: list[Finding], base_ref: str) -> list[Finding]:
    base_counts: collections.Counter[tuple[str, str]] = collections.Counter()
    sources = sorted({item.source for item in findings if item.classification == "UNCLASSIFIED"})
    for source in sources:
        for item in scan_text(source, base_text(base_ref, source)):
            if item.classification != "BOUNDARY":
                base_counts[item.count_key] += 1

    consumed: collections.Counter[tuple[str, str]] = collections.Counter()
    classified: list[Finding] = []
    for item in findings:
        if item.classification != "UNCLASSIFIED":
            classified.append(item)
            continue
        key = item.count_key
        if consumed[key] < base_counts[key]:
            consumed[key] += 1
            classified.append(Finding(
                item.rule, item.source, item.line, item.snippet, "LEGACY_DEBT", "WARNING"
            ))
        else:
            classified.append(Finding(
                item.rule, item.source, item.line, item.snippet, "BLOCKER", "BLOCKER"
            ))
    return classified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", type=Path, default=ROOT / "artifacts/file-center-call-scan.json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args()

    findings = classify_against_base(current_findings(), args.base_ref)
    blockers = [item for item in findings if item.classification == "BLOCKER"]
    debts = [item for item in findings if item.classification == "LEGACY_DEBT"]
    boundaries = [item for item in findings if item.classification == "BOUNDARY"]
    report = {
        "schemaVersion": 3,
        "baseRef": args.base_ref,
        "summary": {
            "findings": len(findings),
            "boundaries": len(boundaries),
            "legacyDebt": len(debts),
            "blockers": len(blockers),
        },
        "blockers": [asdict(item) for item in blockers],
        "legacyDebt": [asdict(item) for item in debts],
        "boundaries": [asdict(item) for item in boundaries],
    }
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    for item in debts:
        print(f"LEGACY_DEBT {item.rule}: {item.source}:{item.line} {item.snippet}")
    for item in blockers:
        print(f"BLOCKER {item.rule}: {item.source}:{item.line} {item.snippet}", file=sys.stderr)
    return 1 if args.strict and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

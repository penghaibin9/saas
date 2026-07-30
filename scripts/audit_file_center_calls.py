#!/usr/bin/env python3
"""阶段 10：公共文件中心调用扫描与旧合同退役门禁。

输出机器可读 JSON；发现客户端仍调用旧上传/元数据 URL、业务页面绕开统一 SDK、业务模块直连
COS SDK 或一次性施工残留时失败。受控代理下载只允许存在于共享 File SDK 内。
"""
from __future__ import annotations

import argparse
import json
import re
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
}
BACKEND_PATTERNS = {
    "direct-cos-sdk": re.compile(r"\b(?:qcloud_cos|CosS3Client|cos-python-sdk)\b"),
    "whole-file-read": re.compile(r"\.read_bytes\s*\("),
    "raw-file-response": re.compile(r"\bFileResponse\s*\("),
}
TEMP_FILE_PATTERNS = (
    re.compile(r"(?:^|/)_?stage\d+.*trigger\.py$", re.I),
    re.compile(r"(?:^|/)patch_.*(?:ci|phase|stage).*\.py$", re.I),
)

# 这些文件是唯一允许接触相应底层能力的边界；其它业务模块命中即视为绕过。
ALLOW = {
    "direct-cos-sdk": (
        "backend/app/services/storage/cos.py",
        "backend/app/services/storage/production.py",
    ),
    "whole-file-read": (
        # 当前允许的非用户上传场景；大文件扫描路径必须使用流式读取。
        "backend/app/services/graduation/graduation_archive_service.py",
    ),
    "raw-file-response": (
        "backend/app/api/v1/file_contract.py",
        "backend/app/api/v1/data_exchange.py",
        "backend/app/api/v1/import_export.py",
        "backend/app/modules/academic_affairs/routers/academic_file_exchange_router.py",
        "backend/app/modules/graduation/routers/graduation_material_center.py",
        "backend/app/modules/internship/routers/internship_material_center.py",
        "backend/app/modules/student_affairs/routers/affairs_material_center.py",
    ),
    "proxy-download-url": (
        "frontend/src/services/file/fileSdk.js",
        "student-portal/src/services/fileCenter.js",
        "miniapp/src/services/fileCenter.js",
    ),
    "direct-uni-upload": (
        "miniapp/src/services/http.js",
        "miniapp/src/services/fileCenter.js",
    ),
    "direct-uni-download": (
        "miniapp/src/services/http.js",
        "miniapp/src/services/fileCenter.js",
    ),
}


@dataclass(frozen=True)
class Finding:
    rule: str
    source: str
    line: int
    snippet: str
    severity: str
    allowed: bool


def iter_files() -> Iterable[Path]:
    for root_name in SOURCE_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUFFIXES and not any(part in SKIP_PARTS for part in path.parts):
                yield path


def allowed(rule: str, source: str) -> bool:
    return source in ALLOW.get(rule, ())


def scan() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files():
        source = path.relative_to(ROOT).as_posix()
        patterns = CLIENT_PATTERNS if not source.startswith("backend/") else BACKEND_PATTERNS
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            snippet = line.strip()
            if not snippet or snippet.startswith(("#", "//", "*")):
                continue
            for rule, pattern in patterns.items():
                if pattern.search(line):
                    permitted = allowed(rule, source)
                    findings.append(Finding(
                        rule=rule,
                        source=source,
                        line=line_no,
                        snippet=snippet[:300],
                        severity="INFO" if permitted else "BLOCKER",
                        allowed=permitted,
                    ))
    for path in ROOT.rglob("*.py"):
        source = path.relative_to(ROOT).as_posix()
        if any(pattern.search(source) for pattern in TEMP_FILE_PATTERNS):
            findings.append(Finding("one-shot-construction-file", source, 1, source, "BLOCKER", False))
    return sorted(findings, key=lambda item: (item.allowed, item.rule, item.source, item.line))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-report", type=Path, default=ROOT / "artifacts/file-center-call-scan.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    findings = scan()
    blockers = [item for item in findings if not item.allowed]
    report = {
        "schemaVersion": 1,
        "summary": {
            "findings": len(findings),
            "allowedBoundaryCalls": len(findings) - len(blockers),
            "blockers": len(blockers),
        },
        "blockers": [asdict(item) for item in blockers],
        "allowed": [asdict(item) for item in findings if item.allowed],
    }
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    for item in blockers:
        print(f"BLOCKER {item.rule}: {item.source}:{item.line} {item.snippet}", file=sys.stderr)
    return 1 if args.strict and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

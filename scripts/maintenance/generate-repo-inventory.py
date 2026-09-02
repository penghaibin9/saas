from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "docs" / "00-项目入口与总控"
GENERATED_OUTPUTS = {
    "docs/00-项目入口与总控/repo-inventory.json",
    "docs/00-项目入口与总控/document-catalog.json",
}
ARCHIVE_REPLACEMENTS = {
    "docs/08-历史记录与归档/ai-handoff/AI执行状态-20260704-历史快照.md":
        "docs/00-项目入口与总控/project-status.json",
    "docs/08-历史记录与归档/project-map-snapshots/2026-07/当前有效文档索引-20260716.md":
        "docs/00-项目入口与总控/project-map/当前有效文档索引.md",
    "docs/08-历史记录与归档/project-map-snapshots/2026-07/模块状态总表-20260709.md":
        "docs/00-项目入口与总控/project-map/模块状态总表.md",
    "docs/08-历史记录与归档/project-map-snapshots/2026-07/下一步施工总控-20260709.md":
        "docs/00-项目入口与总控/project-map/下一步施工总控.md",
    "docs/08-历史记录与归档/project-map-snapshots/2026-07/文档归档与废弃清单-20260711.md":
        "docs/00-项目入口与总控/project-map/文档归档与废弃清单.md",
}


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.quotepath=false", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def category(relative: str) -> str:
    top = relative.split("/", 1)[0]
    if top == "docs":
        return "documentation"
    if top in {"frontend", "student-portal", "miniapp", "enterprise-portal"}:
        return "frontend-app"
    if top == "backend":
        return "backend"
    if top in {"e2e", "performance"}:
        return "verification"
    if top in {"deploy", ".github"}:
        return "delivery"
    if top in {"shared", "scripts"}:
        return "tooling"
    if top in {"artifacts", "tmp", "_run"}:
        return "generated-evidence"
    return "repository-root"


def recommended_action(relative: str) -> str:
    if relative.startswith(("tmp/", "_run/", ".codex-artifacts/")) or relative.endswith(".log"):
        return "remove-from-git"
    if relative.startswith("artifacts/") and not relative.startswith("artifacts/release-seals/"):
        return "move-to-ci-artifact"
    if relative.startswith("docs/08-历史记录与归档/"):
        return "archive"
    return "keep"


def owner_for_doc(relative: str) -> str:
    if "/03-业务模块设计/" in f"/{relative}":
        return "business-domain"
    if "/05-数据接口权限与安全/" in f"/{relative}":
        return "security-and-contracts"
    if "/07-部署运维交付与商业化/" in f"/{relative}":
        return "delivery"
    if "/08-历史记录与归档/" in f"/{relative}":
        return "archive"
    return "project-governance"


def main() -> None:
    CONTROL.mkdir(parents=True, exist_ok=True)
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    committed_at = git("show", "-s", "--format=%cI", "HEAD")
    raw = subprocess.check_output(
        ["git", "-c", "core.quotepath=false", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    paths = sorted(
        {item.decode("utf-8") for item in raw.split(b"\0") if item}
        - GENERATED_OUTPUTS
    )

    files: list[dict[str, object]] = []
    docs: list[dict[str, object]] = []
    categories: Counter[str] = Counter()
    total_bytes = 0
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        digest = sha256(path)
        kind = category(relative)
        categories[kind] += 1
        total_bytes += size
        files.append(
            {
                "path": relative,
                "category": kind,
                "sizeBytes": size,
                "sha256": digest,
                "gitStatus": "tracked" if relative in git_files else "untracked-planned",
                "recommendedAction": recommended_action(relative),
            }
        )
        if relative.startswith("docs/") and path.suffix.lower() in {".md", ".html", ".json", ".yml", ".yaml"}:
            archived = relative.startswith("docs/08-历史记录与归档/")
            replaced_by = ARCHIVE_REPLACEMENTS.get(relative)
            docs.append(
                {
                    "path": relative,
                    "status": "archived" if archived else "active",
                    "owner": owner_for_doc(relative),
                    "canonicalPath": replaced_by or relative,
                    "replacedBy": replaced_by,
                    "lastVerifiedCommit": head,
                    "sha256": digest,
                }
            )

    inventory = {
        "schemaVersion": 1,
        "baselineCommit": head,
        "branch": branch,
        "generatedAt": committed_at,
        "summary": {
            "fileCount": len(files),
            "totalBytes": total_bytes,
            "categories": dict(sorted(categories.items())),
        },
        "files": files,
    }
    catalog = {
        "schemaVersion": 1,
        "baselineCommit": head,
        "generatedAt": committed_at,
        "documents": docs,
    }
    (CONTROL / "repo-inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (CONTROL / "document-catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(files)} files and {len(docs)} document records for {head}")


git_files = set(git("ls-files").splitlines())


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_REPO = ROOT.parent.parent
REPORT = ROOT / "artifacts" / "release-seals" / "repo-hygiene.json"
MANIFEST = ROOT / "docs" / "00-项目入口与总控" / "duplicate-resolution-20260831.json"
BACKUP_ROOT = ORIGINAL_REPO / "_local-backup" / "repo-cleanup-20260831" / "duplicate-files"
EXPLICIT_CANONICALS = {
    "docs/03-业务模块设计/数字迎新中心/03-数字迎新API.md":
        "docs/05-数据接口权限与安全/api/03-数字迎新API.md",
    "docs/03-业务模块设计/岗位实习中心/05-岗位实习API.md":
        "docs/05-数据接口权限与安全/api/05-岗位实习API.md",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC-v7-02-岗位实习中心.pdf":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC-v7-02-岗位实习中心.pdf",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC岗位实习中心/.thumbnail":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/.thumbnail",
    "docs/03-业务模块设计/岗位实习中心/ui/pc-ui-v2/03-岗位实习管理.dc.html":
        "docs/04-UI与全端交互/ui/pc-ui-v2/03-岗位实习管理.dc.html",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC岗位实习中心/PC-v7-02-岗位实习中心.dc.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/PC-v7-02-岗位实习中心.dc.html",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC-v7-02-岗位实习中心-完整管理版.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC-v7-02-岗位实习中心-完整管理版.html",
    "docs/03-业务模块设计/岗位实习中心/ui/pc-ui-v2/10-岗位实习.dc.html":
        "docs/04-UI与全端交互/ui/pc-ui-v2/10-岗位实习.dc.html",
    "docs/03-业务模块设计/毕业设计中心/23-毕业设计.dc.html":
        "docs/04-UI与全端交互/ui/pc-ui-v2/23-毕业设计.dc.html",
    "docs/学生主档统一整改实施总控计划.md":
        "docs/00-项目入口与总控/学生主档统一整改实施总控计划.md",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC岗位实习中心/PC-v7-02-岗位实习中心-print-qlbsj0.dc.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/PC-v7-02-岗位实习中心-print-qlbsj0.dc.html",
    "docs/07-部署运维交付与商业化/20-岗位实习预设便捷字段与提示词.md":
        "docs/03-业务模块设计/岗位实习中心/20-岗位实习预设便捷字段与提示词.md",
    "docs/03-业务模块设计/岗位实习中心/ui/fable5-pc-final/PC岗位实习中心.zip":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心.zip",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/03-mob.png":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/02-mob.png",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/04-white.png":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/02-white3.png",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/03-white2.png":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/shots/03-white.png",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/Canvas-2.dc.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/Canvas.dc.html",
    "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/uploads/Canvas-2.dc.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/Canvas.dc.html",
    "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/uploads/Canvas.dc.html":
        "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/Canvas.dc.html",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/uploads/平台设计/管理端原型 v6 三主题拔高版.dc.html":
        "docs/04-UI与全端交互/ui/pc-ui-v2/00-基准-管理端v6三主题.dc.html",
    "docs/04-UI与全端交互/ui/fable5-pc-final/Future Campus SaaS 设计升级/.thumbnail":
        "docs/04-UI与全端交互/ui/fable5-pc-final/PC岗位实习中心/uploads/.thumbnail",
    "artifacts/release-seals/internship-v8/w0__4plus1-role-surface.json":
        "artifacts/release-seals/internship-v8/w0__role-surface-coverage.json",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def is_archived(relative: str) -> bool:
    return (
        relative.startswith("docs/08-历史记录与归档/")
        or "/archive/" in relative
        or "/历史参考/" in relative
    )


def archive_score(relative: str) -> tuple[int, int, str]:
    if "/source-design/" in relative:
        priority = 0
    elif "/archive/path-conflicts/" in relative:
        priority = 1
    elif "/ai-handoff/" in relative:
        priority = 2
    else:
        priority = 3
    return priority, len(relative), relative


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up and remove archived or explicitly governed byte-identical document copies."
    )
    parser.add_argument("--apply", action="store_true", help="Back up exact files and remove them from Git.")
    args = parser.parse_args()

    if ROOT.name != "repo-consolidation" or ROOT.parent.name != ".worktrees":
        raise SystemExit(f"refusing unexpected worktree: {ROOT}")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    new_resolutions: list[dict[str, str]] = []
    for group in payload.get("duplicateGroups", []):
        active = sorted(path for path in group["paths"] if not is_archived(path))
        archived = sorted(path for path in group["paths"] if is_archived(path))
        if active:
            canonical = active[0]
            removable = archived
        elif len(archived) > 1:
            canonical = min(archived, key=archive_score)
            removable = [path for path in archived if path != canonical]
        else:
            continue
        for relative in removable:
            new_resolutions.append(
                {
                    "removedPath": relative,
                    "canonicalPath": canonical,
                    "sha256": group["sha256"],
                }
            )
        group_paths = set(group["paths"])
        for relative, governed_canonical in EXPLICIT_CANONICALS.items():
            if relative in group_paths and governed_canonical in group_paths:
                new_resolutions.append(
                    {
                        "removedPath": relative,
                        "canonicalPath": governed_canonical,
                        "sha256": group["sha256"],
                    }
                )

    previous = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    merged = {
        item["removedPath"]: item
        for item in [*previous.get("resolutions", []), *new_resolutions]
    }
    manifest = {
        "schemaVersion": 1,
        "strategy": "remove archived byte-identical copies after local backup",
        "backupRoot": str(BACKUP_ROOT),
        "applied": not new_resolutions and bool(previous.get("applied")),
        "resolutions": [merged[key] for key in sorted(merged)],
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"newCandidates={len(new_resolutions)} totalResolutions={len(merged)} "
        f"manifest={MANIFEST.relative_to(ROOT)}"
    )
    if not args.apply:
        print("PREVIEW ONLY. Nothing was removed.")
        return 0

    if not inside(BACKUP_ROOT, ORIGINAL_REPO / "_local-backup"):
        raise SystemExit(f"unsafe backup path: {BACKUP_ROOT}")
    for item in new_resolutions:
        relative = item["removedPath"]
        source = (ROOT / relative).resolve()
        target = (BACKUP_ROOT / relative).resolve()
        if not inside(source, ROOT) or not inside(target, BACKUP_ROOT):
            raise SystemExit(f"unsafe path: {relative}")
        if not source.is_file():
            raise SystemExit(f"missing candidate: {relative}")
        if digest(source) != item["sha256"]:
            raise SystemExit(f"hash changed since report: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != item["sha256"]:
            raise SystemExit(f"backup verification failed: {relative}")

    for item in new_resolutions:
        subprocess.run(["git", "rm", "-f", "--", item["removedPath"]], cwd=ROOT, check=True)
    manifest["applied"] = True
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"removed={len(new_resolutions)} backup={BACKUP_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

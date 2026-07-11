#!/usr/bin/env python3
"""Reorganize docs/ into nine categories. Run from repo root."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CAT = {
    "00": DOCS / "00-项目入口与总控",
    "01": DOCS / "01-产品需求与范围",
    "02": DOCS / "02-总体架构与公共底座",
    "03": DOCS / "03-业务模块设计",
    "04": DOCS / "04-UI与全端交互",
    "05": DOCS / "05-数据接口权限与安全",
    "06": DOCS / "06-开发施工与质量验收",
    "07": DOCS / "07-部署运维交付与商业化",
    "08": DOCS / "08-历史记录与归档",
}

BIZ = CAT["03"]
CENTERS = {
    "系统管理中心": BIZ / "系统管理中心",
    "学工中心": BIZ / "学工中心",
    "教务中心": BIZ / "教务中心",
    "数字迎新中心": BIZ / "数字迎新中心",
    "在校服务中心": BIZ / "在校服务中心",
    "学业过程中心": BIZ / "学业过程中心",
    "毕业设计中心": BIZ / "毕业设计中心",
    "岗位实习中心": BIZ / "岗位实习中心",
    "就业与离校中心": BIZ / "就业与离校中心",
    "跨模块融合": BIZ / "跨模块融合",
}

DIR_MOVES: list[tuple[str, Path]] = [
    ("project-map", CAT["00"] / "project-map"),
    ("公共组件", CAT["02"] / "公共组件"),
    ("backend-integration", CAT["02"] / "backend-integration"),
    ("frontend", CAT["02"] / "frontend"),
    ("api", CAT["05"] / "api"),
    ("database", CAT["05"] / "database"),
    ("rbac", CAT["05"] / "rbac"),
    ("security", CAT["05"] / "security"),
    ("施工记录", CAT["06"] / "施工记录"),
    ("testing", CAT["06"] / "testing"),
    ("deploy", CAT["07"] / "deploy"),
    ("ops", CAT["07"] / "ops"),
    ("dev-run", CAT["07"] / "dev-run"),
    ("delivery", CAT["07"] / "delivery"),
    ("sales", CAT["07"] / "sales"),
    ("demo", CAT["07"] / "demo"),
    ("demo-data", CAT["07"] / "demo-data"),
    ("templates", CAT["07"] / "templates"),
    ("commercialization", CAT["01"] / "commercialization"),
    ("ui", CAT["04"] / "ui"),
    ("design", CAT["04"] / "design"),
    ("archive", CAT["08"] / "archive"),
    ("source-design", CAT["08"] / "source-design"),
    ("ai-handoff", CAT["08"] / "ai-handoff"),
    ("modules", CAT["08"] / "legacy-modules"),
    ("跨模块共享", CENTERS["跨模块融合"]),
    ("学工中心", CENTERS["学工中心"]),
    ("教务中心", CENTERS["教务中心"]),
    ("毕业设计中心", CENTERS["毕业设计中心"]),
    ("岗位实习中心", CENTERS["岗位实习中心"]),
    ("安全审计", CAT["05"] / "security" / "安全审计"),
]

FILE_MOVES: list[tuple[str, Path]] = [
    ("00-只看这个-项目入口.md", CAT["00"] / "00-只看这个-项目入口.md"),
    ("文档导航总览.md", CAT["00"] / "00-文档总导航.md"),
    ("系统管理中心-权限与流程现场审计报告-2026-07-10.md", CAT["05"] / "security" / "系统管理中心-权限与流程现场审计报告-2026-07-10.md"),
]


def safe_move(src: Path, dst: Path) -> bool:
    if not src.exists() or dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        shutil.move(str(src), str(dst))
        subprocess.run(["git", "add", str(dst)], cwd=ROOT, check=True)
        if subprocess.run(["git", "ls-files", "--error-unmatch", str(src)], cwd=ROOT, capture_output=True).returncode == 0:
            subprocess.run(["git", "rm", "-f", str(src)], cwd=ROOT, check=True)
    print(f"mv {src.relative_to(ROOT)}")
    return True


def move_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if not dst.exists() and src.is_dir():
        safe_move(src, dst)
        return
    if not src.is_dir():
        safe_move(src, dst)
        return
    for item in sorted(src.iterdir()):
        safe_move(item, dst / item.name)
    try:
        src.rmdir()
    except OSError:
        pass


def main() -> None:
    for c in CAT.values():
        c.mkdir(parents=True, exist_ok=True)
    for c in CENTERS.values():
        c.mkdir(parents=True, exist_ok=True)

    for name, dst in DIR_MOVES:
        move_tree(DOCS / name, dst)

    for name, dst in FILE_MOVES:
        safe_move(DOCS / name, dst)

    src_02a = CENTERS["学工中心"] / "02A-数字迎新-生产级施工审计与续接说明.md"
    safe_move(src_02a, CENTERS["数字迎新中心"] / src_02a.name)

    perm = CENTERS["跨模块融合"] / "00-系统管理中心-权限角色模块授权与权责边界设计.md"
    safe_move(perm, CENTERS["系统管理中心"] / perm.name)

    sd = CAT["08"] / "source-design"
    mapping = {
        "02-数字迎新中心深化设计 V1.0.md": CENTERS["数字迎新中心"],
        "03-在校服务中心深化设计 V1.0.md": CENTERS["在校服务中心"],
        "04-学业过程中心深化设计 V1.0.md": CENTERS["学业过程中心"],
        "07-毕业与就业中心深化设计 V1.0.md": CENTERS["就业与离校中心"],
    }
    if sd.exists():
        for fn, dest in mapping.items():
            safe_move(sd / fn, dest / fn)

    api_ori = CAT["05"] / "api" / "03-数字迎新API.md"
    safe_move(api_ori, CENTERS["数字迎新中心"] / "03-数字迎新API.md")

    # cleanup empty legacy top-level dirs
    for name, _ in DIR_MOVES:
        p = DOCS / name
        if p.exists() and p.is_dir() and not any(p.iterdir()):
            try:
                p.rmdir()
            except OSError:
                pass

    print("Done.")


if __name__ == "__main__":
    main()

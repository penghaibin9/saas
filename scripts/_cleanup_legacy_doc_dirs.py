#!/usr/bin/env python3
"""Merge legacy docs/ root folders into nine-category paths, then delete legacy copies."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

NINE = {
    "00-项目入口与总控",
    "01-产品需求与范围",
    "02-总体架构与公共底座",
    "03-业务模块设计",
    "04-UI与全端交互",
    "05-数据接口权限与安全",
    "06-开发施工与质量验收",
    "07-部署运维交付与商业化",
    "08-历史记录与归档",
}

# legacy top-level name -> destination under docs/
LEGACY_MOVES: dict[str, Path] = {
    "project-map": DOCS / "00-项目入口与总控" / "project-map",
    "公共组件": DOCS / "02-总体架构与公共底座" / "公共组件",
    "backend-integration": DOCS / "02-总体架构与公共底座" / "backend-integration",
    "frontend": DOCS / "02-总体架构与公共底座" / "frontend",
    "api": DOCS / "05-数据接口权限与安全" / "api",
    "database": DOCS / "05-数据接口权限与安全" / "database",
    "rbac": DOCS / "05-数据接口权限与安全" / "rbac",
    "security": DOCS / "05-数据接口权限与安全" / "security",
    "compliance": DOCS / "05-数据接口权限与安全" / "compliance",
    "施工记录": DOCS / "06-开发施工与质量验收" / "施工记录",
    "testing": DOCS / "06-开发施工与质量验收" / "testing",
    "qa": DOCS / "06-开发施工与质量验收" / "qa",
    "deploy": DOCS / "07-部署运维交付与商业化" / "deploy",
    "ops": DOCS / "07-部署运维交付与商业化" / "ops",
    "dev-run": DOCS / "07-部署运维交付与商业化" / "dev-run",
    "delivery": DOCS / "07-部署运维交付与商业化" / "delivery",
    "sales": DOCS / "07-部署运维交付与商业化" / "sales",
    "demo": DOCS / "07-部署运维交付与商业化" / "demo",
    "demo-data": DOCS / "07-部署运维交付与商业化" / "demo-data",
    "templates": DOCS / "07-部署运维交付与商业化" / "templates",
    "commercialization": DOCS / "01-产品需求与范围" / "commercialization",
    "ui": DOCS / "04-UI与全端交互" / "ui",
    "design": DOCS / "04-UI与全端交互" / "design",
    "archive": DOCS / "08-历史记录与归档" / "archive",
    "source-design": DOCS / "08-历史记录与归档" / "source-design",
    "ai-handoff": DOCS / "08-历史记录与归档" / "ai-handoff",
    "modules": DOCS / "08-历史记录与归档" / "legacy-modules",
    "岗位实习中心": DOCS / "03-业务模块设计" / "岗位实习中心",
    "毕业设计中心": DOCS / "03-业务模块设计" / "毕业设计中心",
    "安全审计": DOCS / "05-数据接口权限与安全" / "security" / "安全审计",
}

LEGACY_FILES: dict[str, Path] = {
    "00-只看这个-项目入口.md": DOCS / "00-项目入口与总控" / "00-只看这个-项目入口.md",
    "D1-现有系统反向建模报告.md": DOCS / "02-总体架构与公共底座" / "D1-现有系统反向建模报告.md",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def tracked(p: Path) -> bool:
    return run("ls-files", "--error-unmatch", p.relative_to(ROOT).as_posix()).returncode == 0


def git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel_s, rel_d = src.relative_to(ROOT).as_posix(), dst.relative_to(ROOT).as_posix()
    if run("mv", rel_s, rel_d).returncode != 0:
        shutil.move(str(src), str(dst))
        run("add", rel_d)
        if tracked(src):
            run("rm", "-f", rel_s)
    print(f"mv {rel_s} -> {rel_d}")


def git_rm_path(p: Path) -> None:
    rel = p.relative_to(ROOT).as_posix()
    if tracked(p):
        run("rm", "-r", "-f", rel)


def merge_tree(src_root: Path, dst_root: Path) -> None:
    if not src_root.exists():
        return
    for src in sorted(src_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        if not dst.exists():
            git_mv(src, dst)
            continue
        if sha(src) == sha(dst):
            git_rm_path(src)
            if src.exists():
                src.unlink()
            print(f"drop dup {src.relative_to(ROOT)}")
        else:
            alt = DOCS / "08-历史记录与归档" / "archive" / "path-conflicts" / src_root.name / rel
            git_mv(src, alt)


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for f in sorted(path.rglob("*"), reverse=True):
        if f.is_file():
            git_rm_path(f)
            if f.exists():
                f.unlink()
    if path.is_dir():
        try:
            path.rmdir()
        except OSError:
            shutil.rmtree(path, ignore_errors=True)
    print(f"removed {path.relative_to(ROOT)}")


def main() -> None:
    for dst in LEGACY_MOVES.values():
        dst.mkdir(parents=True, exist_ok=True)

    for name, dst in LEGACY_MOVES.items():
        if name in NINE:
            raise SystemExit(f"refuse legacy name in NINE: {name}")
        merge_tree(DOCS / name, dst)

    for name, dst in LEGACY_FILES.items():
        src = DOCS / name
        if not src.exists():
            continue
        if dst.exists():
            if sha(src) == sha(dst):
                git_rm_path(src)
                if src.exists():
                    src.unlink()
            else:
                alt = DOCS / "08-历史记录与归档" / "archive" / "path-conflicts" / name
                git_mv(src, alt)
        else:
            git_mv(src, dst)

    for name in LEGACY_MOVES:
        remove_tree(DOCS / name)
    for name in LEGACY_FILES:
        remove_tree(DOCS / name)

    leftovers = [p.name for p in DOCS.iterdir() if p.name not in NINE and p.name != "README.md"]
    if leftovers:
        print("WARN leftovers:", leftovers)
    else:
        print("docs root clean: nine categories + README only")
    print("done")


if __name__ == "__main__":
    main()

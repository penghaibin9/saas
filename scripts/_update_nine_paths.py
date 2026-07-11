#!/usr/bin/env python3
"""Update all documentation path references after nine-category reorg."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Longest-prefix first
REPLACEMENTS = [
    # new absolute paths (idempotent partial)
    ("docs/modules/", "docs/08-历史记录与归档/legacy-modules/"),
    ("docs/跨模块共享/", "docs/03-业务模块设计/跨模块融合/"),
    ("docs/学工中心/", "docs/03-业务模块设计/学工中心/"),
    ("docs/教务中心/", "docs/03-业务模块设计/教务中心/"),
    ("docs/毕业设计中心/", "docs/03-业务模块设计/毕业设计中心/"),
    ("docs/岗位实习中心/", "docs/03-业务模块设计/岗位实习中心/"),
    ("docs/公共组件/", "docs/02-总体架构与公共底座/公共组件/"),
    ("docs/00-项目入口与总控/project-map/", "docs/00-项目入口与总控/project-map/"),
    ("docs/00-只看这个-项目入口.md", "docs/00-项目入口与总控/00-只看这个-项目入口.md"),
    ("docs/文档导航总览.md", "docs/00-项目入口与总控/00-文档总导航.md"),
    ("docs/施工记录/", "docs/06-开发施工与质量验收/施工记录/"),
    ("docs/testing/", "docs/06-开发施工与质量验收/testing/"),
    ("docs/api/", "docs/05-数据接口权限与安全/api/"),
    ("docs/database/", "docs/05-数据接口权限与安全/database/"),
    ("docs/rbac/", "docs/05-数据接口权限与安全/rbac/"),
    ("docs/security/", "docs/05-数据接口权限与安全/security/"),
    ("docs/07-部署运维交付与商业化/deploy/", "docs/07-部署运维交付与商业化/deploy/"),
    ("docs/ops/", "docs/07-部署运维交付与商业化/ops/"),
    ("docs/dev-run/", "docs/07-部署运维交付与商业化/dev-run/"),
    ("docs/delivery/", "docs/07-部署运维交付与商业化/delivery/"),
    ("docs/sales/", "docs/07-部署运维交付与商业化/sales/"),
    ("docs/demo-data/", "docs/07-部署运维交付与商业化/demo-data/"),
    ("docs/demo/", "docs/07-部署运维交付与商业化/demo/"),
    ("docs/templates/", "docs/07-部署运维交付与商业化/templates/"),
    ("docs/commercialization/", "docs/01-产品需求与范围/commercialization/"),
    ("docs/backend-integration/", "docs/02-总体架构与公共底座/backend-integration/"),
    ("docs/frontend/", "docs/02-总体架构与公共底座/frontend/"),
    ("docs/ui/", "docs/04-UI与全端交互/ui/"),
    ("docs/design/", "docs/04-UI与全端交互/design/"),
    ("docs/archive/", "docs/08-历史记录与归档/archive/"),
    ("docs/source-design/", "docs/08-历史记录与归档/source-design/"),
    ("docs/ai-handoff/", "docs/08-历史记录与归档/ai-handoff/"),
    # relative from 03 centers (siblings)
    ("../跨模块共享/", "../跨模块融合/"),
    ("../../跨模块共享/", "../../跨模块融合/"),
    # relative from 03 centers to other categories
    ("../施工记录/", "../../06-开发施工与质量验收/施工记录/"),
    ("../公共组件/", "../../02-总体架构与公共底座/公共组件/"),
    ("../project-map/", "../../00-项目入口与总控/project-map/"),
    ("../文档导航总览.md", "../../00-项目入口与总控/00-文档总导航.md"),
    ("../00-只看这个-项目入口.md", "../../00-项目入口与总控/00-只看这个-项目入口.md"),
    ("../api/", "../../05-数据接口权限与安全/api/"),
    ("../testing/", "../../06-开发施工与质量验收/testing/"),
    ("../archive/", "../../08-历史记录与归档/archive/"),
    # CLAUDE from docs/03/.../center (3 levels to docs, 1 more to root)
    ("../../CLAUDE.md", "../../../CLAUDE.md"),
    ("../../../CLAUDE.md", "../../../CLAUDE.md"),
    # shorthand (only when not already under docs/03-业务模块设计/)
    ("modules/13A", "03-业务模块设计/学工中心/13A"),
    ("modules/13B", "03-业务模块设计/教务中心/13B"),
]

EXTENSIONS = {".md", ".js", ".vue", ".py", ".ps1", ".sh", ".yml", ".yaml", ".toml", ".txt", ".json"}


def patch(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def main() -> None:
    changed = []
    skip_dirs = {".git", "node_modules", ".worktrees", "__pycache__", "venv", ".venv", "99-老毕业设计系统-只参考不要照抄"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        base = Path(dirpath)
        if any(s in base.parts for s in skip_dirs):
            continue
        for name in filenames:
            path = base / name
            if path.suffix.lower() not in EXTENSIONS:
                continue
            if path.match("scripts/_reorg_nine_categories.py") or path.match("scripts/_update_nine_paths.py"):
                continue
            try:
                raw = path.read_bytes()
                for enc in ("utf-8", "utf-8-sig", "gbk"):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    continue
            except OSError:
                continue
            new = patch(text)
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed.append(path.relative_to(ROOT))
    print(f"Updated {len(changed)} files")
    for p in changed[:50]:
        print(" ", p)
    if len(changed) > 50:
        print(f"  ... +{len(changed)-50} more")


if __name__ == "__main__":
    main()

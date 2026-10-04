"""Check the current release's schema pins without imports or database access."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import sys

PRODUCT = Path("products/internship-platform")
CURRENT_WORKFLOWS = (
    "internship-standalone-browser-auth.yml",
    "internship-standalone-c09-g19-g20.yml",
    "internship-standalone-db-head.yml",
    "internship-standalone-fullstack-enterprise.yml",
    "internship-standalone-fullstack-pc.yml",
    "internship-standalone-g01-g18-current-head.yml",
    "internship-standalone-mobile-fullstack.yml",
    "internship-standalone-pc-fullstack.yml",
)
CURRENT_PRODUCT_FILES = (
    PRODUCT / "deploy/docker-compose.production.yml",
    PRODUCT / "deploy/env.production.example",
    PRODUCT / "deploy/backup/restore-drill.sh",
    PRODUCT / "scripts/c09_recovery_drill_ci.sh",
)
PIN = re.compile(
    r"\bEXPECTED_ALEMBIC_REVISION\s*[:=]\s*[\"']?"
    r"(?:\$\{EXPECTED_ALEMBIC_REVISION:-)?(ix\d+)\b"
)
RECEIPT_PIN = re.compile(
    r"\[\s*[\"'](?:schemaRevision|alembicRevision)[\"']\s*\]"
    r"\s*==\s*[\"'](ix\d+)[\"']"
)


def migration_head(versions: Path) -> str:
    """Read literal Alembic edges; reject broken or ambiguous installation graphs."""
    graph: dict[str, set[str]] = {}
    for path in sorted(versions.glob("*.py")):
        values = {}
        for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    values[target.id] = ast.literal_eval(node.value)
        revision = values.get("revision")
        if not isinstance(revision, str) or not revision:
            raise ValueError(f"迁移文件缺少固定版本：{path.name}")
        if revision in graph:
            raise ValueError(f"迁移版本重复：{revision}")
        if "down_revision" not in values:
            raise ValueError(f"迁移文件缺少上级版本：{path.name}")
        previous = values["down_revision"]
        parents = set(previous if isinstance(previous, (tuple, list)) else [previous]) if previous else set()
        if any(not isinstance(parent, str) or not parent for parent in parents):
            raise ValueError(f"迁移上级版本格式错误：{path.name}")
        graph[revision] = parents
    if not graph:
        raise ValueError("未找到数据库安装链")
    referenced = set().union(*graph.values())
    missing = referenced - graph.keys()
    if missing:
        raise ValueError(f"迁移链缺少上级版本：{', '.join(sorted(missing))}")
    heads = graph.keys() - referenced
    if len(heads) != 1:
        raise ValueError(f"迁移链必须有唯一最高版本，实际为：{', '.join(sorted(heads)) or '无'}")
    roots = {revision for revision, parents in graph.items() if not parents}
    if len(roots) != 1:
        raise ValueError("迁移链必须有唯一初始版本")
    reached: set[str] = set()
    while True:
        available = {revision for revision, parents in graph.items() if parents <= reached} - reached
        if not available:
            break
        reached.update(available)
    if reached != graph.keys():
        raise ValueError("迁移链存在循环或不可达版本")
    return next(iter(heads))


def current_consumers(repository: Path) -> list[Path]:
    """Keep required consumers and discover additional current-version workflows."""
    paths = set(CURRENT_PRODUCT_FILES)
    paths.update(Path(".github/workflows") / name for name in CURRENT_WORKFLOWS)
    for path in (repository / ".github/workflows").glob("internship-standalone*.yml"):
        if "EXPECTED_ALEMBIC_REVISION" in path.read_text(encoding="utf-8-sig"):
            paths.add(path.relative_to(repository))
    return sorted(paths)


def check_contract(repository: Path) -> tuple[str, list[Path], list[str]]:
    head = migration_head(repository / PRODUCT / "backend/alembic/versions")
    paths = current_consumers(repository)
    errors = []
    for relative in paths:
        path = repository / relative
        if not path.is_file():
            errors.append(f"缺少当前运行版本配置：{relative.as_posix()}")
            continue
        source = path.read_text(encoding="utf-8-sig")
        pins = list(PIN.finditer(source))
        if not pins:
            errors.append(f"缺少固定的当前期望版本：{relative.as_posix()}")
        for match in pins + list(RECEIPT_PIN.finditer(source)):
            if match.group(1) != head:
                line = source.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{relative.as_posix()}:{line} 期望 {head}，发现 {match.group(1)}"
                )
    return head, paths, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="核对独立岗位实习当前数据库迁移版本约定")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args(argv)
    try:
        head, paths, errors = check_contract(args.repo_root.resolve())
    except (OSError, SyntaxError, ValueError, TypeError) as exc:
        print(f"数据库迁移版本约定未通过：{exc}", file=sys.stderr)
        return 1
    if errors:
        print("数据库迁移版本约定未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"数据库迁移版本约定通过：最高版本 {head}，已核对 {len(paths)} 个当前运行/验收文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

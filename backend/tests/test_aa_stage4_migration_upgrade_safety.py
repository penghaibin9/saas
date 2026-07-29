"""第四阶段：教务新增迁移的 upgrade 路径不得包含无保护破坏性 DDL。"""
from __future__ import annotations

import ast
from pathlib import Path


VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
EXPECTED_PREFIXES = tuple(f"{number:04d}_aa_" for number in range(127, 135))
FINAL_MERGE = "aa_final_20260729_merge_academic_affairs_final_with_main.py"


def _migration_files() -> list[Path]:
    files: list[Path] = []
    for prefix in EXPECTED_PREFIXES:
        matches = sorted(VERSIONS.glob(f"{prefix}*.py"))
        assert len(matches) == 1, f"迁移 {prefix} 应且仅应存在一份，实际：{matches}"
        files.extend(matches)

    merge = VERSIONS / FINAL_MERGE
    assert merge.is_file(), f"缺少最终 Alembic merge 迁移：{merge.name}"
    files.append(merge)
    return files


def _upgrade_function(tree: ast.Module, path: Path) -> ast.FunctionDef:
    upgrade = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"),
        None,
    )
    assert upgrade is not None, f"{path.name} 缺少 upgrade()"
    return upgrade


def test_stage4_academic_migration_upgrade_has_no_destructive_ddl():
    files = _migration_files()
    assert len(files) == 9

    violations: list[str] = []
    revisions: set[str] = set()

    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        upgrade = _upgrade_function(tree, path)

        revision = next(
            (
                node.value.value
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "revision" for target in node.targets)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ),
            None,
        )
        assert revision, f"{path.name} 缺少字符串 revision"
        assert revision not in revisions, f"重复 revision：{revision}"
        revisions.add(revision)

        for node in ast.walk(upgrade):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"drop_table", "drop_column"}:
                    violations.append(f"{path.name}:{node.lineno}:{node.func.attr}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                normalized = " ".join(node.value.upper().split())
                if "DROP TABLE" in normalized or "DROP COLUMN" in normalized:
                    violations.append(f"{path.name}:{node.lineno}:raw destructive SQL")

    assert not violations, "upgrade() 存在无保护破坏性 DDL：\n" + "\n".join(violations)

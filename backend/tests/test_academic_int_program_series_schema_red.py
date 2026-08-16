"""RED contract for the Program stable-series shared schema/writer handoff.

This file is intentionally staged before the shared DDL.  It must stay off the
formal INT head until the control-plane Alembic lineage is present there.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from sqlalchemy import UniqueConstraint


VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revision_text(revision: str) -> str:
    marker = f'revision = "{revision}"'
    matches = []
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if marker in text:
            matches.append((path, text))
    assert len(matches) == 1, f"expected exactly one Alembic revision {revision}, got {[str(p) for p, _ in matches]}"
    return matches[0][1]


def _aa_program_keyword_expressions(fn) -> dict[str, ast.AST]:
    tree = ast.parse(inspect.getsource(fn))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else None
        if name != "AaProgram":
            continue
        return {kw.arg: kw.value for kw in node.keywords if kw.arg}
    raise AssertionError(f"{fn.__name__} must construct AaProgram explicitly")


def test_alembic_convergence_merges_academic_c1_and_control_plane_lineages_before_series_ddl():
    text = _revision_text("20260817_acad_int_ctrl_merge")
    assert "20260816_acad_int_c1_att" in text
    assert "20260816_merge_ctrl_intern_e" in text
    assert "down_revision" in text
    assert "def upgrade()" in text and "pass" in text
    assert "def downgrade()" in text and "pass" in text


def test_program_series_migration_is_nullable_expand_only_after_convergence():
    text = _revision_text("20260817_acad_int_program_series")
    compact = "".join(text.split())
    upper = text.upper()

    assert 'down_revision="20260817_acad_int_ctrl_merge"' in compact
    assert 'revision="20260817_acad_int_program_series"' in compact
    assert '"series_key"' in text
    assert "nullable=True" in compact
    assert "uk_aa_program_series_version" in text
    assert "tenant_id" in text and "version" in text
    assert "UPDATE T_AA_PROGRAM" not in upper
    assert "LEGACY-" not in text


def test_program_model_keeps_unresolved_legacy_series_nullable_and_unique_per_version():
    from app.models import AaProgram

    column = AaProgram.__table__.c.series_key
    assert column.nullable is True
    assert getattr(column.type, "length", None) in {64, 100, 128}

    matches = [
        constraint
        for constraint in AaProgram.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uk_aa_program_series_version"
    ]
    assert len(matches) == 1
    assert tuple(column.name for column in matches[0].columns) == (
        "tenant_id",
        "series_key",
        "version",
    )


def test_new_program_root_assigns_series_once_and_w2_successor_inherits_it():
    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_program_authority_service as authority

    root_keywords = _aa_program_keyword_expressions(core.create_program)
    successor_keywords = _aa_program_keyword_expressions(authority.create_new_version)

    assert "series_key" in root_keywords
    assert isinstance(root_keywords["series_key"], ast.Call), "new v1 must generate/normalize one root series key"

    assert "series_key" in successor_keywords
    inherited = successor_keywords["series_key"]
    assert isinstance(inherited, ast.Attribute) and inherited.attr == "series_key", "v+1 must inherit the locked source series key"

    successor_source = inspect.getsource(authority.create_new_version)
    assert "PROGRAM_SERIES_UNRESOLVED" in successor_source
    assert "series_key" in successor_source

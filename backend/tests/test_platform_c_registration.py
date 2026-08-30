from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

from app.models import DocumentCompareResult, FileDerivedArtifact, StudentLifecycleFact
from app.models.base import Base
from app.modules.platform.document_lifecycle.router import router
from app.services.file_access_service import resolver_registry_snapshot
from app.services import file_access_resolvers as _registered_resolvers  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]


def _assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def test_c_migration_consumes_b_head_and_contains_no_backfill() -> None:
    path = ROOT / "alembic" / "versions" / "20260830_plat_c_document_lifecycle.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _assignment(tree, "revision") == "20260830_plat_c_lifecycle"
    assert _assignment(tree, "down_revision") == "20260830_plat_b_forms"
    assert source.count("op.create_table(") == 3
    assert "t_file_derived_artifact" in source
    assert "t_document_compare_result" in source
    assert "t_student_lifecycle_fact" in source
    assert "StudentStageEvent" not in source
    assert "backfill" not in source.lower()


def test_c_models_are_shared_registered_with_projection_shape() -> None:
    assert Base.metadata.tables["t_file_derived_artifact"] is FileDerivedArtifact.__table__
    assert Base.metadata.tables["t_document_compare_result"] is DocumentCompareResult.__table__
    assert Base.metadata.tables["t_student_lifecycle_fact"] is StudentLifecycleFact.__table__
    assert "is_current" not in FileDerivedArtifact.__table__.c
    assert "is_current" not in DocumentCompareResult.__table__.c
    assert "is_deleted" not in StudentLifecycleFact.__table__.c
    assert "version" not in StudentLifecycleFact.__table__.c


def test_c_routes_and_source_bound_file_resolver_are_shared_registered() -> None:
    routes = {(route.path, frozenset(route.methods or set())) for route in router.routes}
    expected = {
        ("/platform-c/document-intelligence/extractions", "POST"),
        ("/platform-c/document-intelligence/comparisons", "POST"),
        ("/platform-c/document-intelligence/jobs/{job_id}", "GET"),
        ("/platform-c/document-intelligence/extractions/{artifact_id}", "GET"),
        ("/platform-c/document-intelligence/comparisons/{result_id}", "GET"),
        ("/platform-c/students/{student_id}/lifecycle", "GET"),
    }
    for path, method in expected:
        assert any(route_path == path and method in methods for route_path, methods in routes)
    registration = (ROOT / "app" / "api" / "v1" / "route_registration.py").read_text(encoding="utf-8")
    assert "api_router.include_router(document_lifecycle_router)" in registration
    resolver = resolver_registry_snapshot()["DOCUMENT_DERIVATIVE"]
    assert resolver.endswith("document_lifecycle.derived_access.document_derivative_resolver")


def test_schema_parity_cli_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_platform_c_schema_parity.py"), "--help"],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--database-url" in completed.stdout

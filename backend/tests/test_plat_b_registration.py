from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1 import platform_business_forms as api
from app.models import BusinessFormDefinition, BusinessFormVersion, StudentProfile
from app.models.base import Base


ROOT = Path(__file__).resolve().parents[1]


def _assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def test_migration_consumes_a_head_and_creates_only_the_two_b_tables():
    path = ROOT / "alembic" / "versions" / "20260830_plat_b_business_forms.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert _assignment(tree, "revision") == "20260830_plat_b_forms"
    assert _assignment(tree, "down_revision") == "20260829_plat_a_integrity"
    source = path.read_text(encoding="utf-8")
    assert source.count('op.create_table(') == 2
    assert '"t_business_form_definition"' in source
    assert '"t_business_form_version"' in source
    assert "ComplianceResult" not in source
    assert "GenericFormSubmission" not in source
    assert "MaterialPolicy" not in source


def test_models_are_registered_and_match_the_only_two_b_tables():
    assert Base.metadata.tables["t_business_form_definition"] is BusinessFormDefinition.__table__
    assert Base.metadata.tables["t_business_form_version"] is BusinessFormVersion.__table__
    assert BusinessFormDefinition.__table__.c.active_version_id.nullable
    assert BusinessFormVersion.__table__.c.schema_hash.type.length == 64


def test_shared_router_exposes_staff_and_four_client_runtime_contracts():
    routes = {
        (route.path, frozenset(route.methods or set()))
        for route in api.router.routes
    }
    expected = {
        ("/platform/compliance/evaluate", "POST"),
        ("/platform/business-forms", "GET"),
        ("/platform/business-forms", "POST"),
        ("/platform/business-form-versions/{version_id}", "GET"),
        ("/platform/business-form-versions/{version_id}/validate", "GET"),
        ("/platform/business-form-versions/{version_id}/impact", "GET"),
        ("/platform/business-form-versions/{version_id}/publish", "POST"),
        ("/platform/business-form-versions/{version_id}/disable", "POST"),
        ("/business-forms/runtime/load", "POST"),
        ("/business-forms/runtime/submit", "POST"),
    }
    for path, method in expected:
        assert any(route_path == path and method in methods for route_path, methods in routes)
    registration = (ROOT / "app" / "api" / "v1" / "route_registration.py").read_text(encoding="utf-8")
    assert "platform_business_forms.router" in registration


def test_runtime_file_authorizer_rechecks_access_and_scan(monkeypatch):
    calls = []

    def access(file_id, *, user, action):
        calls.append(("access", file_id, user, action))

    def ready(file_id, *, user):
        calls.append(("ready", file_id, user))

    monkeypatch.setattr("app.services.file_access_service.require_file_access", access)
    monkeypatch.setattr("app.services.file_scan_service.assert_file_ready_for_business", ready)
    user = {"userId": "9"}
    assert api._file_authorizer("17", {}, user) is True
    assert calls == [
        ("access", "17", user, "bind"),
        ("ready", "17", user),
    ]


def test_student_picker_is_tenant_scoped_and_student_self_only():
    engine = create_engine("sqlite:///:memory:")
    StudentProfile.__table__.create(engine)
    with Session(engine) as db:
        own = StudentProfile(
            tenant_id=7, student_no="B-001", real_name="B Student",
            class_id=31, current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
        )
        other_tenant = StudentProfile(
            tenant_id=8, student_no="B-002", real_name="Other",
            class_id=31, current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([own, other_tenant])
        db.flush()
        authorize = api._student_authorizer(db, 7)
        assert authorize(own.id, {}, {"userType": "STUDENT", "studentId": str(own.id)})
        assert not authorize(own.id, {}, {"userType": "STUDENT", "studentId": "999"})
        assert not authorize(other_tenant.id, {}, {"userType": "STUDENT", "studentId": str(other_tenant.id)})


def test_runtime_submit_returns_stable_camel_case_command_result(monkeypatch):
    class FakeService:
        def submit(self, **kwargs):
            assert kwargs["expected_business_version"] == 3
            return SimpleNamespace(
                domain="INTERNSHIP",
                command="CREATE_SPECIAL_FILING",
                record_id="filing-19",
                status="SUBMITTED",
                version=4,
                next_action={"type": "navigate", "url": "/internship/filings/filing-19"},
            )

    monkeypatch.setattr(api, "_tenant_id", lambda: 7)
    monkeypatch.setattr(api, "_application_service", lambda db, tenant_id: FakeService())
    response = api.submit_form(
        api.FormSubmitBody(
            formCode="INTERNSHIP_SPECIAL_FILING",
            versionId=11,
            client="STUDENT_PC",
            context={"recordId": "filing-19"},
            schemaHash="a" * 64,
            values={"reason": "test"},
            expectedBusinessVersion=3,
        ),
        user={"userId": "9"},
        db=object(),
    )

    assert response["data"] == {
        "domain": "INTERNSHIP",
        "command": "CREATE_SPECIAL_FILING",
        "recordId": "filing-19",
        "status": "SUBMITTED",
        "version": 4,
        "nextAction": {"type": "navigate", "url": "/internship/filings/filing-19"},
    }

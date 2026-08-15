from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/modules/internship/routers/internship_enterprise_collaboration.py"
SERVICE = ROOT / "app/modules/internship/services/internship_enterprise_collaboration_service.py"
CONTEXT = ROOT / "app/modules/internship/dependencies/enterprise_context.py"
ROUTES = ROOT / "app/api/v1/route_registration.py"


def test_e9_routes_use_internship_collab_context_not_recruitment_context():
    router = ROUTER.read_text(encoding="utf-8")
    for route in (
        '@router.get("/internship-students")',
        '@router.get("/internship-students/{internship_id}")',
        '@router.get("/evaluation-tasks")',
        '@router.post("/evaluation-tasks/{internship_id}/submit")',
    ):
        assert route in router
    assert "resolve_internship_collab_context" in router
    assert "resolve_recruitment_context" not in router
    assert 'require_permission("internship.student.view")' in router
    assert 'require_permission("internship.eval.enterprise.manage")' in router


def test_e9_scope_is_canonical_company_batch_and_formal_position_only():
    service = SERVICE.read_text(encoding="utf-8")
    assert "InternshipRecord.enterprise_id == context.company_id" in service
    assert "InternshipRecord.batch_id == context.batch_id" in service
    assert "InternshipRecord.position_id.is_not(None)" in service
    assert "InternshipRecord.mentor_contact_id == mentor_contact_id" in service
    assert "StudentContact" not in service
    assert "contact_value" not in service


def test_e9_mentor_role_requires_bound_contact_and_permissions_are_explicit():
    service = SERVICE.read_text(encoding="utf-8")
    context = CONTEXT.read_text(encoding="utf-8")
    assert 'if str(context.member_role or "").upper() != "MENTOR"' in service
    assert "if not member.contact_id" in service
    assert '"internship.student.view": frozenset({"COMPANY_ADMIN", "HR", "MENTOR"})' in context
    assert '"internship.eval.enterprise.manage": frozenset({"COMPANY_ADMIN", "HR", "MENTOR"})' in context


def test_e9_online_evaluation_reuses_canonical_fact_and_is_audited():
    service = SERVICE.read_text(encoding="utf-8")
    assert "InternshipEnterpriseEval(" in service
    assert 'source="ENTERPRISE"' in service
    assert 'source_type="ENTERPRISE_ONLINE"' in service
    assert 'evaluation.school_review_status = "PENDING"' in service
    assert 'action="ENTERPRISE_ONLINE_SUBMIT"' in service
    assert "EnterpriseEvaluation" not in service


def test_e9_returned_resubmit_requires_exact_version_cas():
    service = SERVICE.read_text(encoding="utf-8")
    assert 'evaluation.school_review_status != "RETURNED"' in service
    assert 'expected = payload.get("expectedVersion")' in service
    assert 'expected is None or int(expected) != int(evaluation.version or 0)' in service
    for field in ("attendanceScore", "skillScore", "attitudeScore", "collaborationScore", "safetyScore"):
        assert field in service
    assert "if not 0 <= parsed <= 100" in service


def test_e9_router_is_registered_without_staff_dependencies():
    routes = ROUTES.read_text(encoding="utf-8")
    assert "internship_enterprise_collaboration" in routes
    assert "api_router.include_router(internship_enterprise_collaboration.router)" in routes
    assert "api_router.include_router(internship_enterprise_collaboration.router, dependencies=d)" not in routes

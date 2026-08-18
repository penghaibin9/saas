from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/modules/internship/routers/internship_enterprise_portal.py"
SERVICE = ROOT / "app/modules/internship/services/internship_enterprise_position_service.py"
MODEL = ROOT / "app/models/employment.py"
MIGRATION = ROOT / "alembic/versions/20260815_internship_e_m7_enterprise_public_profile.py"


def test_e4_company_public_profile_is_additive_on_emp_company():
    model = MODEL.read_text(encoding="utf-8")
    for field in ("logo_file_id", "cover_file_id", "short_name", "short_intro", "website", "main_business", "established_year"):
        assert f"{field}:" in model
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260815_internship_e_m7"' in migration
    assert 'down_revision = "20260815_internship_e_m6"' in migration
    assert '_TABLE = "t_emp_company"' in migration


def test_enterprise_position_facade_never_exposes_publish_authority():
    router = ROUTER.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    for route in (
        '@router.get("/company")', '@router.put("/company")', '@router.get("/positions")',
        '@router.post("/positions")', '@router.get("/positions/{position_id}")',
        '@router.put("/positions/{position_id}")', '@router.post("/positions/{position_id}/submit")',
        '@router.post("/positions/{position_id}/withdraw")',
    ):
        assert route in router
    assert '@router.post("/positions/{position_id}/publish")' not in router.lower()
    assert 'source_type="ENTERPRISE"' in service
    assert 'row.status = "PENDING"' in service
    assert 'row.status = "DRAFT"' in service
    assert 'assert_campaign_operation_window(campaign, "POSITION_SUBMIT")' in service


def test_enterprise_position_scope_is_server_derived_and_cas_protected():
    service = SERVICE.read_text(encoding="utf-8")
    assert "InternshipPosition.company_id == context.company_id" in service
    assert "InternshipPosition.campaign_id == context.campaign_id" in service
    assert 'payload.get("expectedVersion") is None' in service
    assert 'if row.status != "DRAFT"' in service
    assert 'if row.status != "PENDING"' in service
    editable = service.split("_POSITION_FIELDS =", 1)[1].split("}", 1)[0]
    assert "allocated_count" not in editable
    assert "rights_status" not in editable


def test_company_profile_only_writes_public_fields_and_keeps_school_controls_read_only():
    service = SERVICE.read_text(encoding="utf-8")
    assert 'biz_type="INTERNSHIP_ENTERPRISE_PROFILE"' in service
    update_block = service.split("def update_company_profile_in_tx", 1)[1].split("def _campaign", 1)[0]
    for allowed in ("row.short_name =", "row.short_intro =", "row.website =", "row.main_business ="):
        assert allowed in update_block
    for forbidden in ("qualification_status =", "coop_status =", "blacklist =", "access_valid_until =", "credit_code ="):
        assert forbidden not in update_block


def test_context_capability_is_explicit_and_fail_closed():
    router = ROUTER.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    assert "context_projection_in_tx" in router
    assert '"recruitmentWrite": bool(recruitment_write)' in service
    assert '_role(context) in _EDITOR_ROLES' in service
    assert 'str(campaign.status or "").upper() == "OPEN"' in service


def test_enterprise_position_mentor_is_validated_against_current_company_context():
    service = SERVICE.read_text(encoding="utf-8")
    assert "InternshipEnterpriseContact" in service
    validator = service.split("def _validate_mentor_contact_in_tx", 1)[1].split("def _validate_position_relations_in_tx", 1)[0]
    assert "InternshipEnterpriseContact.tenant_id == context.tenant_id" in validator
    assert "InternshipEnterpriseContact.company_id == context.company_id" in validator
    assert "InternshipEnterpriseContact.is_deleted.is_(False)" in validator
    assert "企业导师不存在或不属于当前企业" in validator
    create_block = service.split("def create_position_in_tx", 1)[1].split("def update_position_in_tx", 1)[0]
    update_block = service.split("def update_position_in_tx", 1)[1].split("def _assert_submit_ready", 1)[0]
    assert "_validate_position_relations_in_tx" in create_block
    assert "_validate_position_relations_in_tx" in update_block

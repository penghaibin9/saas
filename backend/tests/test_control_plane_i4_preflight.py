from pathlib import Path


def test_role_member_and_audit_queries_are_page_bounded():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_i4_router.py").read_text(encoding="utf-8")
    assert 'pageSize: int = Query(50, ge=1, le=200)' in source
    assert '.offset((page - 1) * pageSize).limit(pageSize)' in source
    assert 'SecurityAuditLog.created_at.desc()' in source
    assert '.limit(pageSize)' in source


def test_i4_contract_does_not_fake_20k_import_gold():
    root = Path(__file__).resolve().parents[2]
    contract = (root / "shared/contracts/control-plane/i4-20k-preflight.json").read_text(encoding="utf-8")
    assert '"currentSingleJobGold": false' in contract
    assert 'I3_NORMALIZED_STAGING_MIGRATION' in contract


def test_role_detail_advertises_paged_resources_instead_of_fake_complete_preview():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_i4_router.py").read_text(encoding="utf-8")
    assert 'membersTruncated' in source
    assert 'membersEndpoint' in source
    assert 'auditTrailComplete' in source
    assert 'auditEndpoint' in source

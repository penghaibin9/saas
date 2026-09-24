from pathlib import Path
import json


def test_role_member_and_audit_queries_are_page_bounded():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_i4_router.py").read_text(encoding="utf-8")
    assert 'pageSize: int = Query(50, ge=1, le=200)' in source
    assert '.offset((page - 1) * pageSize).limit(pageSize)' in source
    assert 'SecurityAuditLog.created_at.desc()' in source
    assert '.limit(pageSize)' in source


def test_role_list_is_sql_paginated_and_member_counts_only_cover_current_page():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_router.py").read_text(encoding="utf-8")
    block = source.split("def list_system_roles(", 1)[1].split("def get_system_role(", 1)[0]
    assert "select(func.count()).select_from(stmt.order_by(None).subquery())" in block
    assert ".offset((page - 1) * page_size).limit(page_size)" in block
    assert "UserRole.role_id.in_(role_ids)" in block
    assert "DataScopeRule.role_code.in_(role_codes)" in block
    assert "scope_by_role.get" in block
    assert '"version": int(role.version or 0)' in source
    assert "total = len(roles)" not in block


def test_w13_impact_uses_database_aggregation_and_static_trees_use_no_database():
    root = Path(__file__).resolve().parents[2]
    service = (root / "backend/app/modules/system_admin/services/school_iam_authority_projection_service.py").read_text(
        encoding="utf-8"
    )
    impact = service.split("def school_template_impact(", 1)[1].split("def explain_subject_access(", 1)[0]
    catalog = service.split("def assignable_catalog(", 1)[1].split("def template_catalog(", 1)[0]
    assert "func.count(func.distinct(UserRole.user_id))" in impact
    assert '"affectedUserCountAuthority": "DB_COUNT_DISTINCT_USER_ROLE"' in impact
    assert "get_sessionmaker" not in catalog


def test_permission_tree_loads_actor_authority_once_instead_of_per_catalog_row():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/services/system_admin_catalog_service.py").read_text(encoding="utf-8")
    block = source.split("def build_permission_tree(", 1)[1].split("def visible_codes_from_tree(", 1)[0]
    assert "patterns = get_effective_permission_patterns(user)" in block
    assert "has_permission(" not in block


def test_role_detail_marks_legacy_permissions_explicitly_read_only():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_router.py").read_text(encoding="utf-8")
    block = source.split("def get_system_role(", 1)[1].split("def assign_system_user_roles(", 1)[0]
    assert '"editable": False' in block
    assert "仅在保存时只读保留" in block


def test_access_explain_reads_only_the_requested_module_not_the_global_registry():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/core/effective_access.py").read_text(encoding="utf-8")
    explain = source.split("def explain_tenant_access(", 1)[1].split("def explain_enterprise_access(", 1)[0]
    assert "module_keys=(module_key,)" in explain


def test_i4_contract_records_real_20k_single_job_gold_evidence():
    root = Path(__file__).resolve().parents[2]
    path = root / "shared/contracts/control-plane/i4-20k-preflight.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    identity = contract["gates"]["identityImport"]
    evidence = contract["candidateEvidence"]

    assert contract["card"] == "I4_GOLD"
    assert contract["schoolScaleTarget"] == 20000
    assert identity["targetRows"] == 20000
    assert identity["currentSingleJobGold"] is True
    assert identity["blockedBy"] is None
    assert identity["normalizedStaging"] is True
    assert identity["stageChunkSize"] == 500
    assert identity["batchPayloadRowsMaterialized"] is False
    assert identity["canonicalConfirm"] is True
    assert identity["realPasswordHashing"] == "PBKDF2_SHA256_200000"
    assert identity["idempotentReplay"] is True

    assert evidence["rows"] == 20000
    assert evidence["runtimeUsers"] == 20000
    assert evidence["runtimeRoleLinks"] == 20000
    assert evidence["stagingRows"] == 20000
    assert evidence["rowErrors"] == 0
    assert evidence["markerPayloadBytes"] < 4096
    assert evidence["maxRssMb"] < 512
    assert evidence["artifactDigest"].startswith("sha256:")
    assert "final branch HEAD" in contract["goldRule"]


def test_role_detail_advertises_paged_resources_instead_of_fake_complete_preview():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_i4_router.py").read_text(encoding="utf-8")
    assert 'membersTruncated' in source
    assert 'membersEndpoint' in source
    assert 'auditTrailComplete' in source
    assert 'auditEndpoint' in source


def test_effective_access_module_failure_is_explicitly_non_cacheable():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/core/effective_access.py").read_text(encoding="utf-8")
    contract = (root / "shared/contracts/control-plane/effective-access-contract.json").read_text(encoding="utf-8")
    assert 'module_access_healthy = bool(base.get("moduleAccessHealthy"))' in source
    assert 'cacheable = bool(revision_healthy and module_access_healthy)' in source
    assert '"cacheable": cacheable' in source
    assert '"ctxKey": null' in contract
    assert '"cacheable": false' in contract

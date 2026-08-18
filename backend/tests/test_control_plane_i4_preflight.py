from pathlib import Path
import json


def test_role_member_and_audit_queries_are_page_bounded():
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/modules/system_admin/routers/system_i4_router.py").read_text(encoding="utf-8")
    assert 'pageSize: int = Query(50, ge=1, le=200)' in source
    assert '.offset((page - 1) * pageSize).limit(pageSize)' in source
    assert 'SecurityAuditLog.created_at.desc()' in source
    assert '.limit(pageSize)' in source


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

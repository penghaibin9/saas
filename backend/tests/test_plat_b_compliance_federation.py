from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.modules.platform.compliance_federation.inventory import DOMAIN_COMPLIANCE_INVENTORY
from app.modules.platform.compliance_federation.providers import (
    ComplianceFederation,
    EvidenceOnlyProvider,
    InternshipComplianceProvider,
    _graduation_current_version_is_valid,
    _graduation_operation_applicable,
    _graduation_state_blocks,
)
from app.modules.platform.compliance_federation.schemas import (
    ComplianceState,
    ProviderMode,
    SubjectRef,
)


SUBJECT = SubjectRef(domain="INTERNSHIP", subject_type="INTERNSHIP_RECORD", subject_id="42")


def _native_result(items, *, passed=False):
    return {
        "passed": passed,
        "items": items,
        "ruleVersion": "batch-7-rv3",
        "operation": "ONBOARD",
    }


def test_internship_provider_normalizes_without_changing_native_semantics():
    source = [
        {"code": "ok", "label": "通过", "status": "VALID", "required": True, "applicable": True, "severity": "BLOCK"},
        {"code": "missing", "label": "缺失", "status": "MISSING", "required": True, "applicable": True, "severity": "BLOCK"},
        {"code": "warn", "label": "提醒", "status": "MISSING", "required": False, "applicable": True, "severity": "WARN"},
        {"code": "pending", "label": "处理中", "status": "PENDING", "required": True, "applicable": True, "severity": "BLOCK"},
        {"code": "na", "label": "不适用", "status": "NOT_APPLICABLE", "required": False, "applicable": False, "severity": "BLOCK"},
        {"code": "exempt", "label": "豁免", "status": "EXEMPTED", "required": True, "applicable": True, "severity": "BLOCK", "evidenceId": 9},
        {"code": "future", "label": "未知来源态", "status": "SOMETHING_NEW", "required": True, "applicable": True, "severity": "BLOCK"},
    ]
    calls = []

    def canonical(internship_id, operation, user):
        calls.append((internship_id, operation, user))
        return _native_result(source, passed=False)

    assessment = InternshipComplianceProvider(canonical).evaluate(
        subject_ref=SUBJECT, operation="ONBOARD", user={"userId": "u1"},
    )

    assert calls == [("42", "ONBOARD", {"userId": "u1"})]
    assert assessment.provider_mode == ProviderMode.NATIVE_ENGINE
    assert assessment.policy_version == "batch-7-rv3"
    assert assessment.blocking is True
    states = {item.code: item.state for item in assessment.items}
    assert states == {
        "ok": ComplianceState.PASS,
        "missing": ComplianceState.BLOCKER,
        "warn": ComplianceState.WARNING,
        "pending": ComplianceState.PENDING,
        "na": ComplianceState.NOT_APPLICABLE,
        "exempt": ComplianceState.EXEMPTED,
        "future": ComplianceState.NOT_EVALUATED,
    }
    assert next(item for item in assessment.items if item.code == "exempt").evidence_ref == {
        "evidenceId": "9", "evidenceVersion": None,
    }


def test_default_internship_provider_consumes_installed_canonical_authority(monkeypatch):
    from app.modules.internship.services import (
        internship_compliance_authoritative_service as authoritative,
        internship_compliance_service as base,
    )

    monkeypatch.setattr(base, "evaluate_internship_compliance", lambda *_args, **_kwargs: {})
    evaluator = InternshipComplianceProvider()._native_evaluator()
    assert evaluator is authoritative.evaluate_internship_compliance


def test_federation_rejects_duplicate_or_blank_provider_identity():
    first = EvidenceOnlyProvider("ACADEMIC_EVIDENCE", "ACADEMIC", "教务")
    duplicate = EvidenceOnlyProvider("academic_evidence", "ACADEMIC", "教务副本")
    with pytest.raises(AppException) as caught:
        ComplianceFederation([first, duplicate])
    assert caught.value.code == "COMPLIANCE_PROVIDER_INVALID"

    blank = EvidenceOnlyProvider("", "ACADEMIC", "空 provider")
    with pytest.raises(AppException) as caught:
        ComplianceFederation([blank])
    assert caught.value.code == "COMPLIANCE_PROVIDER_INVALID"


def test_provider_exception_fails_closed_as_not_evaluated():
    def broken(*_args, **_kwargs):
        raise RuntimeError("sensitive source failure")

    result = ComplianceFederation([InternshipComplianceProvider(broken)]).evaluate(
        provider_code="INTERNSHIP_NATIVE",
        subject_ref=SUBJECT,
        operation="ARCHIVE",
        user={},
    )
    assert result.blocking is True
    assert result.items[0].state == ComplianceState.NOT_EVALUATED
    assert "sensitive source failure" not in (result.items[0].reason or "")


def test_domain_app_exception_is_not_hidden_by_federation():
    def denied(*_args, **_kwargs):
        raise AppException("NO_PERMISSION", "scope denied")

    with pytest.raises(AppException) as caught:
        ComplianceFederation([InternshipComplianceProvider(denied)]).evaluate(
            provider_code="INTERNSHIP_NATIVE", subject_ref=SUBJECT, operation="ONBOARD", user={},
        )
    assert caught.value.code == "NO_PERMISSION"


def test_unknown_provider_is_a_404_and_evidence_only_never_passes():
    federation = ComplianceFederation([EvidenceOnlyProvider("ACADEMIC_EVIDENCE", "ACADEMIC", "教务")])
    with pytest.raises(AppException) as caught:
        federation.evaluate(provider_code="UNKNOWN", subject_ref=SUBJECT, operation="READ", user={})
    assert caught.value.http_status == 404

    result = federation.evaluate(
        provider_code="ACADEMIC_EVIDENCE",
        subject_ref=SubjectRef(domain="ACADEMIC", subject_type="STATUS_CHANGE", subject_id="42"),
        operation="READ", user={},
    )
    assert result.blocking is True
    assert result.items[0].state == ComplianceState.NOT_EVALUATED


def test_provider_rejects_confused_deputy_subject_domain_before_source_call():
    calls = []

    def canonical(*args, **kwargs):
        calls.append((args, kwargs))
        return _native_result([], passed=True)

    with pytest.raises(AppException) as caught:
        ComplianceFederation([InternshipComplianceProvider(canonical)]).evaluate(
            provider_code="INTERNSHIP_NATIVE",
            subject_ref=SubjectRef(domain="GRADUATION", subject_type="STUDENT", subject_id="42"),
            operation="ONBOARD",
            user={},
        )
    assert caught.value.code == "COMPLIANCE_SUBJECT_DOMAIN_MISMATCH"
    assert calls == []


def test_c0_inventory_covers_four_domains_without_fabricated_affairs_or_academic_rules():
    rows = {row["domain"]: row for row in DOMAIN_COMPLIANCE_INVENTORY}
    assert set(rows) == {"INTERNSHIP", "GRADUATION", "STUDENT_AFFAIRS", "ACADEMIC"}
    assert rows["INTERNSHIP"]["mode"] == "NATIVE_ENGINE"
    assert rows["GRADUATION"]["mode"] == "MATERIAL_POLICY"
    assert rows["STUDENT_AFFAIRS"]["mode"] == "EVIDENCE_ONLY"
    assert rows["ACADEMIC"]["mode"] == "EVIDENCE_ONLY"
    assert rows["STUDENT_AFFAIRS"]["operationCodes"] == ()
    assert rows["ACADEMIC"]["operationCodes"] == ()


def test_federation_runtime_has_no_domain_writer_imports():
    source = Path("app/modules/platform/compliance_federation/providers.py").read_text(encoding="utf-8")
    forbidden = (
        "_ensure_asset",
        "_invalidate_current",
        "_adopt_file",
        "affairs_material_center_service",
        "status_change_material_service",
        "graduation.materials.command_service",
        "InternshipSpecialFiling(",
    )
    assert not [token for token in forbidden if token in source]


def test_graduation_adapter_is_backed_only_by_canonical_rule_fact_and_scope_sources():
    source = Path("app/modules/platform/compliance_federation/providers.py").read_text(encoding="utf-8")
    required_sources = (
        "graduation.materials.rule_service import active_rule, rule_items",
        "GraduationStudentMaterial",
        "FileVersion",
        "FileObject",
        "assert_student_access",
        "SAFE_SCAN",
    )
    assert not [token for token in required_sources if token not in source]
    assert "MaterialConstraintState.ENFORCED" in source
    assert "MaterialConstraintState.UNSPECIFIED" not in source


def test_graduation_operation_and_blocking_match_canonical_archive_collector():
    from types import SimpleNamespace

    definition = SimpleNamespace(review_required=False, archive_required=False)
    assert _graduation_operation_applicable(definition, "SUBMIT") is True
    assert _graduation_operation_applicable(definition, "REVIEW") is False
    assert _graduation_operation_applicable(definition, "ARCHIVE") is False

    assert _graduation_state_blocks(
        state=ComplianceState.PENDING,
        required=True,
        operation="SUBMIT",
        has_evidence=True,
    ) is True
    assert _graduation_state_blocks(
        state=ComplianceState.PENDING,
        required=False,
        operation="SUBMIT",
        has_evidence=True,
    ) is False
    # Graduation manifest_service._collect_items rejects a supplied optional
    # archive item when it is pending/returned/unsafe; optional absence is okay.
    assert _graduation_state_blocks(
        state=ComplianceState.PENDING,
        required=False,
        operation="ARCHIVE",
        has_evidence=True,
    ) is True
    assert _graduation_state_blocks(
        state=ComplianceState.WARNING,
        required=False,
        operation="ARCHIVE",
        has_evidence=True,
    ) is True
    assert _graduation_state_blocks(
        state=ComplianceState.WARNING,
        required=False,
        operation="ARCHIVE",
        has_evidence=False,
    ) is False


def test_graduation_evidence_rejects_stale_or_cross_asset_current_version_pointer():
    from types import SimpleNamespace

    actual = SimpleNamespace(asset_id=41)
    assert _graduation_current_version_is_valid(
        actual,
        SimpleNamespace(asset_id=41, is_current=True, is_deleted=False),
    ) is True
    assert _graduation_current_version_is_valid(
        actual,
        SimpleNamespace(asset_id=99, is_current=True, is_deleted=False),
    ) is False
    assert _graduation_current_version_is_valid(
        actual,
        SimpleNamespace(asset_id=41, is_current=False, is_deleted=False),
    ) is False
    assert _graduation_current_version_is_valid(
        actual,
        SimpleNamespace(asset_id=41, is_current=True, is_deleted=True),
    ) is False

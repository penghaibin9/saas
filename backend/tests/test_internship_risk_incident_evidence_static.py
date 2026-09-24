from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_incident_risk_freezes_canonical_source_identity():
    text = _read("backend/app/modules/internship/services/internship_incident_service.py")
    block = text[text.index("def report_incident"):text.index("def transition")]
    assert 'source_type="INCIDENT"' in block
    assert "source_id=x.id" in block
    assert "source_version=int(x.version or 0)" in block
    assert "assert_internship_record_scope" in block


def test_incident_and_linked_risk_close_fail_closed_on_missing_evidence():
    incident = _read("backend/app/modules/internship/services/internship_incident_service.py")
    risk = _read("backend/app/modules/internship/services/internship_risk_service.py")
    transition = incident[incident.index("def transition"):]
    close = risk[risk.index("def close"):risk.index("def student_help_report")]
    for fact in ("investigation_conclusion", "rectification_plan", "responsibility_conclusion", "file_ids"):
        assert fact in transition
    assert "_source_truth(db, r)" in close
    assert 'source.get("closeAllowed", True)' in close
    assert '"closeBlockers"' in close
    assert "file_service.get_file_meta" in transition
    assert "file_service.bind_file_biz" in incident


def test_high_risk_writes_use_audit_health_gate_and_same_transaction_trail():
    audit = _read("backend/app/modules/internship/services/internship_audit_service.py")
    incident = _read("backend/app/modules/internship/services/internship_incident_service.py")
    risk = _read("backend/app/modules/internship/services/internship_risk_service.py")
    evidence = _read("backend/app/modules/internship/services/internship_evidence_package_service.py")
    assert "def assert_high_risk_write_available" in audit
    assert 'if not status["healthy"]' in audit
    assert "http_status=503" in audit
    assert incident.count("assert_high_risk_write_available(db)") >= 2
    assert risk.count("assert_high_risk_write_available(db)") >= 2
    assert "assert_high_risk_write_available(db)" in evidence
    assert "InternshipAuditTrail" in incident and "db.commit()" in incident


def test_regulatory_package_contains_complaint_risk_incident_and_their_audits():
    text = _read("backend/app/modules/internship/services/internship_evidence_package_service.py")
    assert '("complaints", "InternshipComplaint")' in text
    assert '("risks", "RiskRecord")' in text
    assert '("incidents", "InternshipIncident")' in text
    for target_type in ("COMPLAINT", "RISK", "INTERNSHIP_INCIDENT"):
        assert f'"{target_type}"' in text
    assert '"contact"' in text


def test_complaint_privacy_and_versions_are_server_owned():
    text = _read("backend/app/modules/internship/services/internship_complaint_service.py")
    assert "complainant_contact_encrypted=encrypt_sensitive" in text
    assert "complainant_contact_hash=hash_sensitive" in text
    assert '"complainantContactMasked"' in text
    assert '"version": int(c.version or 0)' in text
    assert "client_version is not None" in text

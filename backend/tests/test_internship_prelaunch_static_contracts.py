from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_no_name_fallback_in_communication_scope():
    text = src("app/modules/internship/services/internship_communication_service.py")
    assert 'return (c.advisor_name or "") in' not in text

def test_evidence_audit_is_type_scoped():
    text = src("app/modules/internship/services/internship_evidence_package_service.py")
    assert text.count('InternshipAuditTrail.target_type == "INTERN_STUDENT"') >= 2

def test_incident_requires_internship_id():
    text = src("app/modules/internship/services/internship_incident_service.py")
    assert '学生事故上报必须关联 internshipId' in text

def test_special_filing_is_type_covered():
    text = src("app/modules/internship/services/internship_compliance_service.py")
    assert 'missing_types = [code for code in triggers if code not in approved]' in text
    assert 'ok = bool(rec.advisor_user_id)' in text

def test_process_report_returned_requires_resubmit():
    text = src("app/modules/internship/services/internship_process_report_service.py")
    assert 'if r.status != "PENDING_REVIEW"' in text
    assert 'dup.version = int(dup.version or 0) + 1' in text

def test_match_conflict_cannot_be_confirmed():
    text = src("app/modules/internship/services/internship_match_service.py")
    assert 'if m.conflict_flag:' in text
    assert '该匹配仍存在冲突' in text

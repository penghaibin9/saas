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


def test_score_appeal_is_real_domain_flow():
    text = src("app/modules/internship/services/internship_score_appeal_service.py")
    assert 'scoreVersion' in text
    assert 'expected_status="PUBLISHED"' in text
    assert 'values={"status": "WITHDRAWN"}' in text
    assert '实习已最终归档' in text
    assert 'def my_latest' in text

def test_score_appeal_generic_workorder_cannot_bypass_domain():
    text = src("app/api/v1/campus_service.py")
    assert '_is_internship_score_appeal' in text
    assert 'internship_score_appeal.decide' in text

def test_score_recalc_supports_withdrawn_and_optimistic_lock():
    text = (ROOT.parent / "frontend/src/modules/internship/views/ScoreView.vue").read_text(encoding="utf-8")
    assert "'WITHDRAWN'" in text
    assert 'body.expectedVersion = current.version' in text
    assert 'scoreApi.getAppeals' in text

def test_student_score_appeal_sends_context_and_reads_status():
    text = (ROOT.parent / "student-portal/src/views/internship/InternshipView.vue").read_text(encoding="utf-8")
    assert '...currentInternshipContext(), reason: appealReason.value' in text
    assert 'internshipScoreAppealStatus(currentInternshipContext())' in text

def test_score_appeal_router_is_registered():
    text = src("app/api/v1/route_registration.py")
    assert 'internship_score_appeal' in text


def test_enterprise_and_student_mutations_require_versions():
    enterprise_schema = src("app/modules/internship/schemas/internship.py")
    student_schema = src("app/modules/internship/schemas/internship_student.py")
    enterprise_service = src("app/modules/internship/services/internship_enterprise_service.py")
    student_service = src("app/modules/internship/services/internship_student_service.py")
    assert enterprise_schema.count('expectedVersion: int = Field(...') >= 5
    assert student_schema.count('expectedVersion: int = Field(...') >= 7
    assert '必须提供 expectedVersion（企业乐观锁）' in enterprise_service
    assert '必须提供 expectedVersion（实习记录乐观锁）' in student_service

def test_staff_student_api_forwards_versions_and_destination_contract():
    api = (ROOT.parent / "frontend/src/modules/internship/api/internship-student.api.js").read_text(encoding="utf-8")
    detail = (ROOT.parent / "frontend/src/modules/internship/views/InternshipStudentDetailView.vue").read_text(encoding="utf-8")
    listing = (ROOT.parent / "frontend/src/modules/internship/views/InternshipStudentListView.vue").read_text(encoding="utf-8")
    assert api.count('expectedVersion') >= 8
    assert 'destination: extra' in detail
    assert 'destinationType: extra' not in detail
    assert 'expectedVersion: this.advisorRow.version' in listing
    assert 'expectedVersion: row.version' in listing

def test_enterprise_edit_and_contact_type_keep_concurrency_invariants():
    form = (ROOT.parent / "frontend/src/modules/internship/views/EnterpriseFormView.vue").read_text(encoding="utf-8")
    service = src("app/modules/internship/services/internship_enterprise_service.py")
    assert 'body.expectedVersion = this.detail?.version' in form
    assert 'was_primary = bool(t.is_primary)' in service
    assert 't.contact_type != old_contact_type and was_primary' in service

def test_participant_summary_hides_global_plan_for_scoped_roles():
    service = src("app/modules/internship/services/internship_participant_service.py")
    view = (ROOT.parent / "frontend/src/modules/internship/views/components/BatchParticipantScope.vue").read_text(encoding="utf-8")
    assert 'planned_count = len(visible) if scoped_view' in service
    assert '"plannedCountScoped": scoped_view' in service
    assert "summary.plannedCountScoped ? '当前范围人数' : '批次计划人数'" in view


def test_common_sql_scope_never_authorizes_advisor_by_name():
    text = src("app/modules/internship/services/internship_scope.py")
    assert 'InternshipRecord.advisor_user_id.in_(advisor_ids)' in text
    assert 'InternshipRecord.advisor_name.in_(advisor_names)' not in text

def test_match_stats_uses_row_level_scope():
    svc = src("app/modules/internship/services/internship_match_service.py")
    router = src("app/modules/internship/routers/internship_match.py")
    assert 'def match_stats(batch_id=None, user=None)' in svc
    assert 'apply_internship_record_scope' in svc
    assert 'InternshipIntention.record_id.in_(scoped_record_ids)' in svc
    assert 'svc.match_stats(batch_id=batchId, user=user)' in router

def test_batch_invalid_dates_and_counts_fail_validation():
    text = src("app/modules/internship/services/internship_service.py")
    assert 'f"{label}格式不正确，请使用 YYYY-MM-DD"' in text
    assert 'def _parse_nonnegative_int' in text
    assert '_parse_nonnegative_int(body["plannedCount"], "计划人数")' in text

def test_legacy_internship_detail_audit_is_type_scoped():
    text = src("app/modules/internship/services/internship_service.py")
    anchor = text.index('def get_internship_student_detail')
    tail = text[anchor:anchor + 5000]
    assert 'InternshipAuditTrail.target_type == "INTERN_STUDENT"' in tail


def test_frozen_participant_roster_scope_does_not_reapply_lifecycle_eligibility():
    text = src("app/modules/internship/services/internship_participant_service.py")
    assert "def _visible_participant_student_ids" in text
    assert "apply_internship_record_scope" in text
    list_start = text.index("def list_participants")
    add_start = text.index("def add_participants", list_start)
    remove_start = text.index("def remove_participant", add_start)
    summary_start = text.index("def summary", remove_start)
    assert "scope.resolve" not in text[list_start:add_start]
    assert "scope.resolve" in text[add_start:remove_start]
    assert "scope.resolve" not in text[remove_start:summary_start]
    assert "scope.resolve" not in text[summary_start:]


def test_student_guarded_mutations_lock_and_advance_record_version():
    text = src("app/modules/internship/services/internship_student_service.py")
    assert "def _get_for_update" in text
    for name in ("update_student_record", "assign_advisor", "set_status", "set_eligibility", "set_destination"):
        start = text.index(f"def {name}")
        next_def = text.find("\ndef ", start + 4)
        block = text[start:] if next_def < 0 else text[start:next_def]
        assert "_get_for_update(db, rec_id)" in block
    for name in ("set_status", "set_eligibility", "set_destination"):
        start = text.index(f"def {name}")
        next_def = text.find("\ndef ", start + 4)
        block = text[start:] if next_def < 0 else text[start:next_def]
        assert "r.version = int(r.version or 0) + 1" in block

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w76_formal_review_todo_uses_shared_unified_todo_and_stable_reviewer_identity():
    lifecycle = text("backend/app/modules/graduation/services/graduation_review_w76_lifecycle_service.py")
    router = text("backend/app/modules/graduation/routers/graduation_review_w7_router.py")

    assert 'TODO_FORMAL_REVIEW = "GD_FORMAL_REVIEW"' in lifecycle
    assert "GraduationReview" in lifecycle and "reviewer_mentor_id" in lifecycle
    assert "GraduationMentor" in lifecycle and "User" in lifecycle and "login_name" in lifecycle
    assert "todo.todo_upsert" in lifecycle
    assert "todo.todo_done" in lifecycle
    assert "正式评阅退回重评" in lifecycle
    assert "reconcile_formal_todos" in lifecycle
    assert "reviewer_account_unresolved" in lifecycle
    assert "graduation_review_w76_lifecycle_service as review" in router


def test_w76_student_reject_message_is_transactional_projection_of_append_only_feedback():
    feedback = text("backend/app/modules/graduation/services/graduation_review_feedback_service.py")
    guard = text("backend/app/modules/graduation/services/graduation_review_message_event_guard.py")

    assert 'if result == "REJECTED":' in feedback
    assert "_emit_student_rejected_notice(" in feedback
    assert "visible_to_student" in feedback
    assert "SELECT student_id FROM t_gd_student" in feedback
    assert "emit_receiver_notice" in feedback
    assert "receiver_as=\"student\"" in feedback
    assert "ACTION_STUDENT_REVIEW_FEEDBACK" in feedback
    assert "GRADUATION_DESIGN.REVIEW_REJECTED" in guard
    assert "student.graduation.review-feedback" in guard
    assert '"studentPc": "/graduation/feedback"' in guard
    assert '"studentMini": None' in guard
    assert "message_event_outbox_service" in guard
    assert "UnifiedMessage" not in feedback


def test_w76_resubmit_reuses_canonical_proposal_final_todos():
    records = text("backend/app/modules/graduation/materials/record_service.py")
    todo = text("backend/app/modules/graduation/services/graduation_todo_helper.py")

    assert "is_resubmit=bool(existing)" in records
    assert "todo.push_proposal_todo(db, proposal, student)" in records
    assert "same_type = [row for row in existing if row.final_type == final_type]" in records
    assert "todo.push_final_todo(db, final, student)" in records
    assert 'TODO_PROPOSAL = "GD_PROPOSAL_REVIEW"' in todo
    assert 'TODO_FINAL = "GD_FINAL_REVIEW"' in todo


def test_w76_overdue_and_average_processing_time_reuse_review_center_projection():
    query = text("backend/app/modules/graduation/services/graduation_review_center_query_service.py")
    summary = text("backend/app/modules/graduation/services/graduation_review_center_summary_service.py")
    lifecycle = text("backend/app/modules/graduation/services/graduation_review_w76_lifecycle_service.py")

    assert "_batch_deadlines" in query and "stage_config" in query and "batch.end_date" in query
    assert "q._batch_deadlines" in summary
    assert "COUNT(*) AS total" in summary
    assert "overdue_count" in summary
    assert "TIMESTAMPDIFF" in summary and "AVG(CASE" in summary
    assert "GROUP BY case_type" in summary
    assert "review_center.summary" in lifecycle
    assert '"overdue"' in lifecycle and '"avgHours"' in lifecycle
    for forbidden in ("teacherRanking", "performanceRanking", "aiScore", "automaticScore"):
        assert forbidden not in lifecycle


def test_w76_w7_router_batch_guard_is_tenant_scoped_before_student_metadata():
    router = text("backend/app/modules/graduation/routers/graduation_review_w7_router.py")

    assert "def _review_batch(review_id, batch_id)" in router
    assert "GraduationReview.tenant_id == _tid()" in router
    assert "GraduationStudent.tenant_id == _tid()" in router
    assert "GraduationStudent.record_status == \"ACTIVE\"" in router
    assert "assert_student_batch(student, batch_id)" in router
    assert "_review_batch(rid, batchId)" in router
    assert "_record_batch" not in router


def test_w76_communication_registry_owns_review_event_and_todo_types():
    registry = yaml.safe_load(text("docs/architecture/communication-capability-registry.yaml"))
    events = {item["eventCode"] for item in registry.get("events", [])}
    todos = {item["todoType"]: item for item in registry.get("todoTypes", [])}

    assert "GRADUATION_DESIGN.REVIEW_REJECTED" in events
    for todo_type in ("GD_PROPOSAL_REVIEW", "GD_FINAL_REVIEW", "GD_FORMAL_REVIEW"):
        assert todo_type in todos
        assert todos[todo_type]["ownerModule"] == "graduation"
    assert todos["GD_FORMAL_REVIEW"]["slaHours"] is None
    assert "review-tasks" in todos["GD_FORMAL_REVIEW"]["deepLinkPattern"]


def test_w76_gate_regressions_keep_batch_scope_and_upgrade_only_legacy_test_evidence():
    priority = text("backend/app/modules/graduation/services/graduation_review_center_priority_service.py")
    legacy = text("backend/tests/graduation_legacy_review_archive_plugin.py")
    closure = text("backend/app/modules/graduation/services/graduation_review_closure_service.py")

    # W7.3 page rows remain SQL batch-scoped and carry the proven batch into the DTO.
    assert '"batch_id": int(batch_id)' in priority
    assert "_base_params(batch_id, scope_ids)" in priority
    assert "Python never reorders a paged subset" in priority

    # Old graduation_client fixtures are upgraded through the real material-center writers;
    # production W7.1 must keep requiring canonical FileVersion evidence.
    assert "_prepare_formal_review_evidence" in legacy
    assert "adopt_legacy_file_in_session" in legacy
    assert "prepare_all" in legacy
    assert 'material_code == "THESIS_FINAL"' in closure
    assert "material.current_version_id" in closure
    assert "FileVersion.asset_id == int(material.asset_id)" in closure
    assert 'str(version.status or "").upper() != "APPROVED"' in closure

from __future__ import annotations

import inspect

from app.modules.internship.services import internship_volunteer_retry as retry
from app.modules.internship.services import internship_volunteer_service as svc


def test_fixed_slots_no_delete_or_temporary_swap():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    assert "list(range(1, len(volunteers) + 1))" in source
    assert ".order_by(InternshipApplication.volunteer_no.asc()).with_for_update()" in source
    assert "row.position_id = p.id" in source
    assert "db.delete" not in source
    assert "volunteer_no =" not in source
    assert "temporary" not in source.lower()


def test_lock_order_record_group_then_applications():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    record_at = source.index("InternshipRecord")
    group_at = source.index("get_or_create_group_in_tx")
    apps_at = source.index("InternshipApplication.tenant_id")
    assert record_at < group_at < apps_at


def test_all_positions_are_rechecked_before_any_slot_mutation():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    recheck = source.index("evaluate_position_for_student_in_tx")
    supersede = source.index("supersede_group_active_decisions_in_tx")
    mutation = source.index("row.position_id = p.id")
    assert recheck < supersede < mutation
    assert "len(set(position_ids))" in source


def test_record_group_and_application_versions_are_all_required():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    assert "expected_record_version" in source
    assert "expected_group_version" in source
    assert "expected_application_versions" in source
    assert "学生实习记录已变化" in source
    assert "志愿组版本已变化" in source
    assert "expectedApplicationVersion" in source


def test_application_statement_policy_is_checked_before_any_slot_mutation():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    policy_source = inspect.getsource(svc._assert_application_statements)
    assert "applicationStatementRequired" in policy_source
    assert "minStatementLength" in policy_source
    assert "APPLICATION_MATERIAL_INCOMPLETE" in policy_source
    policy_at = source.index("_assert_application_statements(")
    mutation_at = source.index("row.position_id = p.id")
    assert policy_at < mutation_at


def test_one_snapshot_is_shared_across_submitted_slots():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    assert source.count("create_material_snapshot_in_tx(") == 1
    assert "row.material_snapshot_id = snapshot.id" in source
    assert "VOLUNTEER_GROUP_SUBMIT" in source


def test_public_student_wrapper_parses_consent_and_uses_whole_transaction_retry():
    source = inspect.getsource(svc.save_my_volunteers)
    assert "_parse_consent_at" in source
    assert "run_with_bounded_mysql_retry" in source
    assert "expectedRecordVersion" in source
    assert "expectedGroupVersion" in source
    assert "expectedApplicationVersions" in source


def test_mysql_retry_is_bounded_to_1205_1213_and_whole_transaction():
    source = inspect.getsource(retry.run_with_bounded_mysql_retry)
    assert retry._RETRYABLE_MYSQL_CODES == frozenset({1205, 1213})
    assert retry._MAX_TRANSACTION_ATTEMPTS == 3
    assert "db.rollback()" in source
    assert "db.commit()" in source
    assert "while True" not in source

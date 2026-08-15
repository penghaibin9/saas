from __future__ import annotations

import inspect
from pathlib import Path

from app.models import InternshipApplication
from app.modules.internship.services import internship_application_service as legacy_app_svc
from app.modules.internship.services import internship_student_application_context_service as legacy_context_svc
from app.modules.internship.services import internship_student_selection_actions_service as actions_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.modules.internship.services import internship_volunteer_retry as retry
from app.modules.internship.services import internship_volunteer_service as svc

ROOT = Path(__file__).resolve().parents[1]
M8 = ROOT / "alembic/versions/20260816_internship_e_m8_application_campaign_scope.py"


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


def test_recruitment_application_slots_are_campaign_scoped_end_to_end():
    source = inspect.getsource(svc.save_or_submit_in_tx)
    assert "InternshipApplication.campaign_id == campaign.id" in source
    assert "campaign_id=campaign.id" in source
    wrapper = inspect.getsource(svc.get_my_volunteers)
    assert "InternshipApplication.campaign_id == _as_id(campaign_id)" in wrapper
    facade = inspect.getsource(selection_svc.get_my_volunteers)
    assert "InternshipApplication.campaign_id == campaign.id" in facade
    submit = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    assert "InternshipApplication.campaign_id == campaign.id" in submit
    action_lock = inspect.getsource(actions_svc._lock_applications_in_tx)
    assert "InternshipApplication.campaign_id == campaign_id" in action_lock


def test_application_model_and_m8_preserve_round_history_and_legacy_uniqueness():
    constraints = {constraint.name for constraint in InternshipApplication.__table__.constraints if constraint.name}
    assert "uk_intern_application_record_campaign_volunteer" in constraints
    assert "uk_intern_application_legacy_record_volunteer" in constraints
    assert "campaign_id" in InternshipApplication.__table__.columns
    assert "legacy_record_id" in InternshipApplication.__table__.columns

    migration = M8.read_text(encoding="utf-8")
    assert 'revision = "20260816_internship_e_m8"' in migration
    assert 'down_revision = "20260815_internship_e_m7"' in migration
    assert "t_internship_application_material_snapshot" in migration
    assert "t_internship_volunteer_group" in migration
    assert "g.campaign_id = p.campaign_id" in migration
    assert "uk_intern_application_record_volunteer" in migration
    assert "cannot downgrade internship E M8" in migration


def test_context_resolution_does_not_pin_closed_editable_drafts_over_new_open_round():
    assert selection_svc._CONTEXT_PINNING_GROUP_STATUSES == ("SUBMITTED", "LOCKED", "APPROVED")
    source = inspect.getsource(selection_svc._resolve_context_in_tx)
    assert "status.in_(_CONTEXT_PINNING_GROUP_STATUSES)" in source
    assert 'InternshipRecruitmentCampaign.status == "OPEN"' in source
    assert "DRAFT" not in selection_svc._CONTEXT_PINNING_GROUP_STATUSES
    assert "NEEDS_REVISION" not in selection_svc._CONTEXT_PINNING_GROUP_STATUSES


def test_legacy_single_application_writer_isolated_from_campaign_rows():
    list_source = inspect.getsource(legacy_context_svc.list_my)
    save_source = inspect.getsource(legacy_context_svc.save)
    submit_source = inspect.getsource(legacy_context_svc.submit)
    withdraw_source = inspect.getsource(legacy_context_svc.withdraw)

    assert "InternshipApplication.campaign_id.is_(None)" in list_source
    assert save_source.count("InternshipApplication.campaign_id.is_(None)") >= 3
    assert "campaign_id=None" in save_source
    assert "InternshipApplication.campaign_id.is_(None)" in submit_source
    assert "InternshipApplication.campaign_id.is_(None)" in withdraw_source
    assert "实习申请不存在" in save_source
    assert "实习申请不存在" in submit_source
    assert "实习申请不存在" in withdraw_source


def test_all_registered_legacy_application_authorities_are_null_campaign_scoped():
    list_source = inspect.getsource(legacy_app_svc.my_applications)
    save_source = inspect.getsource(legacy_app_svc.save_my)
    submit_source = inspect.getsource(legacy_app_svc.submit_my)
    withdraw_source = inspect.getsource(legacy_app_svc.withdraw_my)
    loader_source = inspect.getsource(legacy_app_svc._get_legacy_student_application)
    legacy_position_source = inspect.getsource(legacy_app_svc._legacy_position)

    assert "InternshipApplication.campaign_id.is_(None)" in list_source
    assert save_source.count("InternshipApplication.campaign_id.is_(None)") >= 2
    assert "campaign_id=None" in save_source
    assert "_get_legacy_student_application" in save_source
    assert "_get_legacy_student_application" in submit_source
    assert "_get_legacy_student_application" in withdraw_source
    assert "InternshipApplication.campaign_id.is_(None)" in loader_source
    assert "_legacy_position" in save_source
    assert "_legacy_position" in submit_source
    assert "pos.campaign_id is not None" in legacy_position_source
    assert "招聘季岗位必须通过三志愿原子接口" in legacy_position_source
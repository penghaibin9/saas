"""A03 post-submit authority contracts shared by student PC and mobile surfaces."""
from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.api.v1 import mobile_internship_selection as mobile_facade
from app.modules.internship.services import internship_student_selection_actions_service as action_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.student_portal import internship_selection_router as portal_facade


def _route_contract(router):
    return {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
        if isinstance(route, APIRoute)
    }


def _suffix_contract(router, prefix: str):
    return {(path.removeprefix(prefix), methods) for path, methods in _route_contract(router)}


def test_pc_and_mobile_post_submit_facades_are_strictly_symmetric():
    portal = _suffix_contract(portal_facade.router, "/portal/internship")
    mobile = _suffix_contract(mobile_facade.router, "/mobile/internship")
    assert portal == mobile
    required = {
        ("/context/volunteers/withdraw", frozenset({"POST"})),
        ("/context/volunteers/unlock-request", frozenset({"POST"})),
        ("/context/volunteers/submissions", frozenset({"GET"})),
        ("/context/volunteers/submissions/{submission_version}", frozenset({"GET"})),
        ("/context/volunteers/contact-consent/revoke", frozenset({"POST"})),
    }
    assert required <= portal


def test_post_submit_mutations_are_group_cas_guarded_and_lock_canonical_rows():
    withdraw = inspect.getsource(action_svc.withdraw_my_submission)
    unlock = inspect.getsource(action_svc.request_my_unlock)
    revoke = inspect.getsource(action_svc.revoke_my_contact_consent)
    for source in (withdraw, unlock, revoke):
        assert "_expected_group_version(payload)" in source
        assert "_resolve_and_lock_group_in_tx(" in source
        assert "_lock_applications_in_tx(" in source
        assert "run_with_bounded_mysql_retry" in source
    assert withdraw.index("int(group.version or 0) != expected_group") < withdraw.index('group.status = "DRAFT"')
    assert unlock.index("current_version != expected_group") < unlock.index("group_svc.request_unlock_in_tx")
    assert revoke.index("int(group.version or 0) != expected_group") < revoke.index("group.contact_consent_revoked_at = now")


def test_withdraw_blocks_locked_group_and_preserves_immutable_submission_history():
    source = inspect.getsource(action_svc.withdraw_my_submission)
    assert 'group.status != "SUBMITTED"' in source
    assert 'group.status == "LOCKED"' in source
    assert "VOLUNTEER_GROUP_LOCKED" in source
    assert 'row.status = "DRAFT"' in source
    assert 'group.status = "DRAFT"' in source
    assert "group.current_material_snapshot_id = None" in source
    assert "previousMaterialSnapshotId" in source
    assert "delete(" not in source.lower()

    history = inspect.getsource(action_svc.list_my_submissions)
    detail = inspect.getsource(action_svc.get_my_submission)
    assert "InternshipApplicationMaterialSnapshot" in history
    assert "submission_version.desc()" in history
    assert "snapshot_public_dict(snapshot)" in history
    assert "snapshot_public_dict(snapshot)" in detail
    assert "delete(" not in history.lower()
    assert "delete(" not in detail.lower()


def test_contact_revoke_is_current_grant_only_idempotent_and_versioned():
    source = inspect.getsource(action_svc.revoke_my_contact_consent)
    assert "group.current_material_snapshot_id is None" in source
    assert "group.contact_consent_revoked_at is not None" in source
    assert "group.contact_consent_revoked_at = now" in source
    assert "group.version = int(group.version or 0) + 1" in source
    assert "STUDENT_REVOKE_CONTACT_CONSENT" in source
    assert "materialSnapshotId" in source
    assert "submissionVersion" in source


def test_new_explicit_submit_consent_replaces_old_current_grant_revocation_in_same_transaction():
    source = inspect.getsource(selection_svc.submit_my_saved_volunteers)
    policy_at = source.index("material_svc._assert_contact_mode_allowed")
    clear_at = source.index("group.contact_consent_revoked_at = None")
    delegate_at = source.index("return volunteer_svc.save_or_submit_in_tx(")
    assert policy_at < clear_at < delegate_at
    assert "with session() as db:" in source
    assert "run_with_bounded_mysql_retry" in source

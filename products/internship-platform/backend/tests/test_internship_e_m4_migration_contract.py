"""E-A01 M4 migration contract for volunteer-group coordination."""
from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "20260815_internship_e_m4_volunteer_group.py"


def test_m4_is_linear_after_material_snapshot_and_adds_only_coordination_fact():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260815_internship_e_m4"' in source
    assert 'down_revision = "20260815_internship_e_m3"' in source
    assert '"t_internship_volunteer_group"' in source
    assert '"teacher_confirm_sla_hours"' in source
    assert '"contact_consent_revoked_at"' in source
    assert "t_student_volunteer" not in source
    assert "t_recruitment_application" not in source


def test_m4_does_not_modify_canonical_application_slot_identity():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "t_internship_application" not in source
    assert "volunteer_no" not in source
    assert "position_id" not in source


def test_m4_has_timeout_and_record_lookup_indexes():
    source = MIGRATION.read_text(encoding="utf-8")
    for name in (
        "uk_intern_volunteer_group_record_campaign",
        "ix_intern_volunteer_group_student_status",
        "ix_intern_volunteer_group_campaign_deadline",
        "ix_intern_volunteer_group_record_status",
        "ix_t_internship_volunteer_group_tenant_id",
    ):
        assert name in source

"""E-A01 M1 migration contract: four E1 tables, one linear Alembic head."""
from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "20260815_internship_e_m1_authority.py"


def test_e1_m1_is_linear_and_owns_exactly_the_four_e1_authority_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "20260815_internship_e_m1"' in source
    assert 'down_revision = "20260814_merge_ix_v93_main"' in source
    for table in (
        "t_internship_recruitment_campaign",
        "t_internship_campaign_enterprise",
        "t_internship_enterprise_member",
        "t_internship_enterprise_access_grant",
    ):
        assert f'if not insp.has_table("{table}")' in source
        assert f'"{table}",' in source
    for forbidden in (
        "t_enterprise_company",
        "t_enterprise_job",
        "t_student_volunteer",
        "t_placement_result",
        "t_recruitment_application",
    ):
        assert forbidden not in source


def test_e1_m1_preserves_v3_unique_and_index_contracts():
    source = MIGRATION.read_text(encoding="utf-8")
    for name in (
        "uk_intern_recruit_campaign_code",
        "uk_intern_recruit_campaign_round",
        "uk_intern_campaign_enterprise",
        "uk_intern_enterprise_member",
        "uk_intern_enterprise_access_grant",
        "ix_intern_recruit_campaign_batch_status",
        "ix_intern_recruit_campaign_select_window",
        "ix_intern_campaign_enterprise_campaign_status",
        "ix_intern_campaign_enterprise_company_status",
        "ix_intern_enterprise_member_user_status",
        "ix_intern_enterprise_member_company_status",
        "ix_intern_enterprise_grant_member_validity",
        "ix_intern_enterprise_grant_company_validity",
    ):
        assert name in source


def test_e1_m1_is_mysql_only_and_additive():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'dialect.name != "mysql"' in source
    assert "op.alter_column(" not in source
    assert "op.drop_column(" not in source
    assert "EmpCompany" in source
    assert "InternshipPosition" in source
    assert "InternshipApplication" in source
    assert "InternshipRecord" in source

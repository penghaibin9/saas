"""E-A01 M5: enterprise decision + immutable placement evidence.
Revision ID: 20260815_internship_e_m5
Revises: 20260815_internship_e_position_campaign
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
revision="20260815_internship_e_m5"
down_revision="20260815_internship_e_position_campaign"
branch_labels=depends_on=None

def _mysql():
    if op.get_bind().dialect.name!="mysql": raise RuntimeError("20260815_internship_e_m5 requires MySQL")

def _common():
    return [sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("created_by",sa.BigInteger()),sa.Column("updated_at",sa.DateTime(),nullable=False),sa.Column("updated_by",sa.BigInteger()),sa.Column("is_deleted",sa.Boolean(),nullable=False),sa.Column("version",sa.Integer(),nullable=False)]

def upgrade():
    _mysql(); bind=op.get_bind(); i=inspect(bind)
    if not i.has_table("t_internship_enterprise_application_decision"):
        op.create_table("t_internship_enterprise_application_decision",
            sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column("tenant_id",sa.BigInteger(),nullable=False),
            sa.Column("application_id",sa.BigInteger(),nullable=False),sa.Column("volunteer_group_id",sa.BigInteger(),nullable=False),sa.Column("campaign_id",sa.BigInteger(),nullable=False),sa.Column("batch_id",sa.BigInteger(),nullable=False),sa.Column("company_id",sa.BigInteger(),nullable=False),sa.Column("position_id",sa.BigInteger(),nullable=False),sa.Column("material_snapshot_id",sa.BigInteger(),nullable=False),sa.Column("submission_version",sa.Integer(),nullable=False),sa.Column("decision_status",sa.String(30),nullable=False),sa.Column("effect_status",sa.String(20),nullable=False,server_default="ACTIVE"),sa.Column("valid_until",sa.DateTime()),sa.Column("superseded_reason",sa.String(500)),sa.Column("interview_at",sa.DateTime()),sa.Column("interview_note",sa.String(1000)),sa.Column("decision_reason",sa.String(1000)),sa.Column("decided_by_member_id",sa.BigInteger()),sa.Column("decided_by_user_id",sa.BigInteger()),sa.Column("decided_at",sa.DateTime()),*_common(),sa.UniqueConstraint("tenant_id","application_id","material_snapshot_id",name="uk_intern_enterprise_decision_app_snapshot"),mysql_engine="InnoDB")
        op.create_index("ix_t_internship_enterprise_application_decision_tenant_id","t_internship_enterprise_application_decision",["tenant_id"])
        op.create_index("ix_intern_enterprise_decision_company_campaign_status","t_internship_enterprise_application_decision",["tenant_id","company_id","campaign_id","decision_status","is_deleted"])
        op.create_index("ix_intern_enterprise_decision_application","t_internship_enterprise_application_decision",["tenant_id","application_id","is_deleted"])
        op.create_index("ix_intern_enterprise_decision_effect","t_internship_enterprise_application_decision",["tenant_id","volunteer_group_id","effect_status","valid_until","is_deleted"])
    if not i.has_table("t_internship_placement_snapshot"):
        cols=[sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column("tenant_id",sa.BigInteger(),nullable=False),sa.Column("record_id",sa.BigInteger(),nullable=False),sa.Column("placement_seq",sa.Integer(),nullable=False),sa.Column("application_id",sa.BigInteger()),sa.Column("enterprise_decision_id",sa.BigInteger()),sa.Column("campaign_id",sa.BigInteger()),sa.Column("batch_id",sa.BigInteger(),nullable=False),sa.Column("company_id",sa.BigInteger(),nullable=False),sa.Column("position_id",sa.BigInteger(),nullable=False),sa.Column("company_name",sa.String(200),nullable=False),sa.Column("company_credit_code",sa.String(50)),sa.Column("position_title",sa.String(200),nullable=False),sa.Column("position_category",sa.String(50)),sa.Column("work_location",sa.String(200)),sa.Column("work_address",sa.String(300)),sa.Column("work_content",sa.Text()),sa.Column("major_requirement",sa.String(200)),sa.Column("grade_requirement",sa.String(100)),sa.Column("salary_range",sa.String(50)),sa.Column("subsidy",sa.String(50)),sa.Column("remuneration_type",sa.String(30)),sa.Column("remuneration_amount",sa.Float()),sa.Column("remuneration_cycle",sa.String(30)),sa.Column("daily_hours",sa.Float()),sa.Column("weekly_hours",sa.Float()),sa.Column("shift_type",sa.String(30)),sa.Column("night_shift",sa.Boolean()),sa.Column("overtime_allowed",sa.Boolean()),sa.Column("rest_days",sa.String(50)),sa.Column("rest_days_per_week",sa.Float()),sa.Column("accommodation_provided",sa.Boolean()),sa.Column("meal_provided",sa.Boolean()),sa.Column("hazardous_flag",sa.Boolean()),sa.Column("special_equipment",sa.String(200)),sa.Column("prohibited_reason",sa.String(500)),sa.Column("enterprise_mentor_name",sa.String(100)),sa.Column("rights_status",sa.String(30)),sa.Column("rights_rule_version",sa.String(64)),sa.Column("rights_checked_at",sa.DateTime()),sa.Column("position_version",sa.Integer(),nullable=False),sa.Column("position_updated_at",sa.DateTime()),sa.Column("snapshot_json",sa.JSON(),nullable=False),sa.Column("snapshot_sha256",sa.String(64),nullable=False),sa.Column("captured_at",sa.DateTime(),nullable=False),sa.Column("captured_by_user_id",sa.BigInteger()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("created_by",sa.BigInteger()),sa.UniqueConstraint("tenant_id","record_id","placement_seq",name="uk_intern_placement_snapshot_seq")]
        op.create_table("t_internship_placement_snapshot",*cols,mysql_engine="InnoDB")
        op.create_index("ix_t_internship_placement_snapshot_tenant_id","t_internship_placement_snapshot",["tenant_id"]); op.create_index("ix_t_internship_placement_snapshot_snapshot_sha256","t_internship_placement_snapshot",["snapshot_sha256"]); op.create_index("ix_intern_placement_snapshot_record_time","t_internship_placement_snapshot",["tenant_id","record_id","captured_at"]); op.create_index("ix_intern_placement_snapshot_position_time","t_internship_placement_snapshot",["tenant_id","position_id","captured_at"])
    if "current_placement_snapshot_id" not in {c["name"] for c in i.get_columns("t_internship_record")}:
        op.add_column("t_internship_record",sa.Column("current_placement_snapshot_id",sa.BigInteger(),nullable=True))
    op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_update"); op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_delete")
    op.execute("CREATE TRIGGER trg_intern_placement_snapshot_no_update BEFORE UPDATE ON t_internship_placement_snapshot FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INTERNSHIP_PLACEMENT_SNAPSHOT_IMMUTABLE'")
    op.execute("CREATE TRIGGER trg_intern_placement_snapshot_no_delete BEFORE DELETE ON t_internship_placement_snapshot FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INTERNSHIP_PLACEMENT_SNAPSHOT_IMMUTABLE'")

def downgrade():
    _mysql(); i=inspect(op.get_bind()); op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_update"); op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_delete")
    if "current_placement_snapshot_id" in {c["name"] for c in i.get_columns("t_internship_record")}: op.drop_column("t_internship_record","current_placement_snapshot_id")
    if i.has_table("t_internship_placement_snapshot"): op.drop_table("t_internship_placement_snapshot")
    if i.has_table("t_internship_enterprise_application_decision"): op.drop_table("t_internship_enterprise_application_decision")

"""O3 canonical orientation pre-arrival self service.

Revision ID: 20260901_orientation_self_o3
Revises: 20260901_dorm_allocation_d3
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_orientation_self_o3"
down_revision = "20260901_dorm_allocation_d3"
branch_labels = None
depends_on = None


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def upgrade() -> None:
    if _scalar("""
        SELECT COUNT(*)
        FROM t_orientation_material m
        LEFT JOIN t_orientation_student s ON s.id=m.ori_student_id
        WHERE s.id IS NULL OR s.tenant_id<>m.tenant_id
    """):
        raise RuntimeError("O3 preflight failed: orientation material parent is missing or cross-tenant")
    if _scalar("""
        SELECT COUNT(*) FROM t_orientation_material
        WHERE status NOT IN ('UPLOADED','APPROVED','RETURNED','REJECTED')
    """):
        raise RuntimeError("O3 preflight failed: unsupported orientation material status")

    op.add_column(
        "t_orientation_material",
        sa.Column(
            "student_id", sa.BigInteger(), nullable=True,
            comment="稳定学生 Authority → t_student_profile.id；历史未绑定可空",
        ),
    )
    op.add_column("t_orientation_material", sa.Column("submission_no", sa.Integer(), nullable=True))
    op.add_column("t_orientation_material", sa.Column("is_current", sa.Boolean(), nullable=True))
    op.add_column("t_orientation_material", sa.Column("supersedes_material_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "t_orientation_material",
        sa.Column(
            "source_type", sa.String(50), nullable=True,
            comment="LEGACY_BACKFILL/STUDENT_SELF_SERVICE",
        ),
    )
    op.add_column("t_orientation_material", sa.Column("client_submission_id", sa.String(100), nullable=True))
    op.add_column("t_orientation_material", sa.Column("asset_id", sa.BigInteger(), nullable=True))
    op.add_column("t_orientation_material", sa.Column("file_version_id", sa.BigInteger(), nullable=True))

    op.execute(sa.text("""
        UPDATE t_orientation_material m
        JOIN t_orientation_student s
          ON s.id=m.ori_student_id AND s.tenant_id=m.tenant_id
        SET m.student_id=s.student_id,
            m.source_type='LEGACY_BACKFILL'
    """))
    op.execute(sa.text("""
        UPDATE t_orientation_material m
        JOIN (
          SELECT id,
                 ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, ori_student_id, material_type ORDER BY id
                 ) AS seq,
                 ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, ori_student_id, material_type ORDER BY id DESC
                 ) AS reverse_seq
          FROM t_orientation_material
        ) ranked ON ranked.id=m.id
        SET m.submission_no=ranked.seq,
            m.is_current=(ranked.reverse_seq=1)
    """))
    op.alter_column("t_orientation_material", "submission_no", existing_type=sa.Integer(), nullable=False)
    op.alter_column("t_orientation_material", "is_current", existing_type=sa.Boolean(), nullable=False)
    op.alter_column(
        "t_orientation_material", "source_type", existing_type=sa.String(50),
        nullable=False, comment="LEGACY_BACKFILL/STUDENT_SELF_SERVICE",
    )
    op.create_unique_constraint(
        "uk_ori_material_client_submission", "t_orientation_material",
        ["tenant_id", "client_submission_id"],
    )
    op.create_check_constraint(
        "ck_ori_material_status", "t_orientation_material",
        "status IN ('UPLOADED','APPROVED','RETURNED','REJECTED')",
    )
    op.create_check_constraint(
        "ck_ori_material_submission_no", "t_orientation_material", "submission_no > 0"
    )
    op.create_index(
        "ix_ori_material_student_current", "t_orientation_material",
        ["tenant_id", "student_id", "material_type", "is_current", "is_deleted"],
    )
    op.create_index("ix_t_orientation_material_student_id", "t_orientation_material", ["student_id"])
    op.create_index("ix_t_orientation_material_asset_id", "t_orientation_material", ["asset_id"])
    op.create_index(
        "ix_t_orientation_material_file_version_id", "t_orientation_material", ["file_version_id"]
    )

    op.create_table(
        "t_orientation_arrival_plan",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", sa.BigInteger(), nullable=False,
            comment="租户(学校)ID，行级隔离",
        ),
        sa.Column("ori_student_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "student_id", sa.BigInteger(), nullable=False,
            comment="稳定学生 Authority → t_student_profile.id",
        ),
        sa.Column("arrival_mode", sa.String(30), nullable=False),
        sa.Column("planned_arrival_at", sa.DateTime(), nullable=False),
        sa.Column("station_name", sa.String(200), nullable=True),
        sa.Column("transport_no", sa.String(100), nullable=True),
        sa.Column("pickup_required", sa.Boolean(), nullable=False),
        sa.Column("companion_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False,
            comment="逻辑删除",
        ),
        sa.Column(
            "version", sa.Integer(), nullable=False,
            comment="乐观锁",
        ),
        sa.UniqueConstraint("tenant_id", "ori_student_id", name="uk_ori_arrival_student"),
        sa.CheckConstraint(
            "arrival_mode IN ('TRAIN','AIR','COACH','SELF_DRIVE','CITY_TRANSIT','OTHER')",
            name="ck_ori_arrival_mode",
        ),
        sa.CheckConstraint("status IN ('SUBMITTED','CANCELLED')", name="ck_ori_arrival_status"),
        sa.CheckConstraint(
            "companion_count >= 0 AND companion_count <= 20",
            name="ck_ori_arrival_companion_count",
        ),
        sa.CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_at IS NOT NULL",
            name="ck_ori_arrival_submit_time",
        ),
    )
    op.create_index(
        "ix_t_orientation_arrival_plan_tenant_id", "t_orientation_arrival_plan", ["tenant_id"]
    )
    op.create_index(
        "ix_t_orientation_arrival_plan_ori_student_id", "t_orientation_arrival_plan", ["ori_student_id"]
    )
    op.create_index(
        "ix_t_orientation_arrival_plan_student_id", "t_orientation_arrival_plan", ["student_id"]
    )
    op.create_index(
        "ix_ori_arrival_student_profile", "t_orientation_arrival_plan",
        ["tenant_id", "student_id", "status", "is_deleted"],
    )


def downgrade() -> None:
    if _scalar("SELECT COUNT(*) FROM t_orientation_arrival_plan") or _scalar("""
        SELECT COUNT(*) FROM t_orientation_material
        WHERE source_type='STUDENT_SELF_SERVICE' OR client_submission_id IS NOT NULL
    """):
        raise RuntimeError(
            "O3 downgrade blocked: pre-arrival runtime data exists; archive/export it before downgrade"
        )
    op.drop_index("ix_ori_arrival_student_profile", table_name="t_orientation_arrival_plan")
    op.drop_index("ix_t_orientation_arrival_plan_student_id", table_name="t_orientation_arrival_plan")
    op.drop_index("ix_t_orientation_arrival_plan_ori_student_id", table_name="t_orientation_arrival_plan")
    op.drop_index("ix_t_orientation_arrival_plan_tenant_id", table_name="t_orientation_arrival_plan")
    op.drop_table("t_orientation_arrival_plan")
    op.drop_index("ix_t_orientation_material_file_version_id", table_name="t_orientation_material")
    op.drop_index("ix_t_orientation_material_asset_id", table_name="t_orientation_material")
    op.drop_index("ix_t_orientation_material_student_id", table_name="t_orientation_material")
    op.drop_index("ix_ori_material_student_current", table_name="t_orientation_material")
    op.drop_constraint("ck_ori_material_submission_no", "t_orientation_material", type_="check")
    op.drop_constraint("ck_ori_material_status", "t_orientation_material", type_="check")
    op.drop_constraint("uk_ori_material_client_submission", "t_orientation_material", type_="unique")
    op.drop_column("t_orientation_material", "client_submission_id")
    op.drop_column("t_orientation_material", "file_version_id")
    op.drop_column("t_orientation_material", "asset_id")
    op.drop_column("t_orientation_material", "source_type")
    op.drop_column("t_orientation_material", "supersedes_material_id")
    op.drop_column("t_orientation_material", "is_current")
    op.drop_column("t_orientation_material", "submission_no")
    op.drop_column("t_orientation_material", "student_id")

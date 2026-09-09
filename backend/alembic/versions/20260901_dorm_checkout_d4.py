"""D4 canonical dorm stay lifecycle and formal checkout workflow.

Revision ID: 20260901_dorm_checkout_d4
Revises: 20260901_orientation_self_o3
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_dorm_checkout_d4"
down_revision = "20260901_orientation_self_o3"
branch_labels = None
depends_on = None

STAY = "t_affairs_dorm_stay"
BED = "t_affairs_dorm_bed"
CHECKOUT = "t_affairs_dorm_checkout_request"


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def _preflight() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260901_dorm_checkout_d4 requires MySQL")
    tables = set(inspect(op.get_bind()).get_table_names())
    missing = sorted({STAY, BED} - tables)
    if missing:
        raise RuntimeError("D4 requires existing authority tables: " + ",".join(missing))
    if CHECKOUT in tables:
        raise RuntimeError("D4 checkout table already exists outside this revision")

    unsupported = _scalar(f"""
        SELECT COUNT(*) FROM {STAY}
        WHERE is_deleted=0
          AND status NOT IN ('RESERVED','ACTIVE','ENDED','CANCELLED')
    """)
    invalid_lifecycle = _scalar(f"""
        SELECT COUNT(*) FROM {STAY}
        WHERE is_deleted=0 AND (
          (status IN ('RESERVED','ACTIVE') AND checkout_at IS NOT NULL)
          OR (status='ENDED' AND checkout_at IS NULL)
        )
    """)
    active_mismatch = _scalar(f"""
        SELECT COUNT(*)
        FROM {STAY} s
        LEFT JOIN {BED} b
          ON b.id=s.bed_id AND b.tenant_id=s.tenant_id AND b.is_deleted=0
        WHERE s.status='ACTIVE' AND s.is_deleted=0
          AND (b.id IS NULL OR b.status<>'OCCUPIED' OR b.student_id<>s.student_id)
    """)
    occupied_without_stay = _scalar(f"""
        SELECT COUNT(*)
        FROM {BED} b
        LEFT JOIN {STAY} s
          ON s.tenant_id=b.tenant_id AND s.bed_id=b.id
         AND s.student_id=b.student_id AND s.status='ACTIVE' AND s.is_deleted=0
        WHERE b.status='OCCUPIED' AND b.student_id IS NOT NULL AND b.is_deleted=0
          AND s.id IS NULL
    """)
    duplicate_active_student = _scalar(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, student_id FROM {STAY}
          WHERE status='ACTIVE' AND is_deleted=0
          GROUP BY tenant_id, student_id HAVING COUNT(*)>1
        ) d
    """)
    duplicate_active_bed = _scalar(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, bed_id FROM {STAY}
          WHERE status='ACTIVE' AND is_deleted=0
          GROUP BY tenant_id, bed_id HAVING COUNT(*)>1
        ) d
    """)
    if any((unsupported, invalid_lifecycle, active_mismatch, occupied_without_stay,
            duplicate_active_student, duplicate_active_bed)):
        raise RuntimeError(
            "D4 stay/bed preflight failed before DDL: "
            f"unsupported={unsupported}, invalid_lifecycle={invalid_lifecycle}, "
            f"active_mismatch={active_mismatch}, occupied_without_stay={occupied_without_stay}, "
            f"duplicate_active_student={duplicate_active_student}, "
            f"duplicate_active_bed={duplicate_active_bed}"
        )


def upgrade() -> None:
    _preflight()

    op.create_check_constraint(
        "ck_dorm_stay_status", STAY,
        "status IN ('RESERVED','ACTIVE','ENDED','CANCELLED')",
    )
    op.create_check_constraint(
        "ck_dorm_stay_lifecycle", STAY,
        "(status IN ('RESERVED','ACTIVE') AND checkout_at IS NULL) "
        "OR (status='ENDED' AND checkout_at IS NOT NULL) "
        "OR status='CANCELLED'",
    )

    op.create_table(
        CHECKOUT,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", sa.BigInteger(), nullable=False,
            comment="租户(学校)ID，行级隔离",
        ),
        sa.Column(
            "student_id", sa.BigInteger(), nullable=False,
            comment="学生 Authority → t_student_profile.id",
        ),
        sa.Column(
            "stay_id", sa.BigInteger(), nullable=False,
            comment="发起时 ACTIVE DormStay 稳定 ID",
        ),
        sa.Column(
            "bed_id", sa.BigInteger(), nullable=False,
            comment="发起时当前床位稳定 ID",
        ),
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "request_type", sa.String(50), nullable=False,
            comment="GRADUATION/LEAVE_OF_ABSENCE/WITHDRAWAL/DAY_STUDENT/SPECIAL",
        ),
        sa.Column(
            "source_type", sa.String(50), nullable=False,
            comment="MANUAL/GRADUATION_BATCH",
        ),
        sa.Column(
            "source_biz_id", sa.String(100), nullable=True,
            comment="毕业批退等上游稳定来源键；人工发起为空",
        ),
        sa.Column("client_request_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("blockers_json", sa.JSON(), nullable=True),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="PENDING_CONFIRMATION/BLOCKED/CONFIRMED/CANCELLED",
        ),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_by", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除",
        ),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
        sa.UniqueConstraint(
            "tenant_id", "client_request_id", name="uk_dorm_checkout_client_request",
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_type", "source_biz_id", name="uk_dorm_checkout_source",
        ),
        sa.CheckConstraint(
            "request_type IN ('GRADUATION','LEAVE_OF_ABSENCE','WITHDRAWAL','DAY_STUDENT','SPECIAL')",
            name="ck_dorm_checkout_request_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('MANUAL','GRADUATION_BATCH')",
            name="ck_dorm_checkout_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_CONFIRMATION','BLOCKED','CONFIRMED','CANCELLED')",
            name="ck_dorm_checkout_status",
        ),
        sa.CheckConstraint(
            "status <> 'CONFIRMED' OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)",
            name="ck_dorm_checkout_confirmed",
        ),
        sa.CheckConstraint(
            "status <> 'CANCELLED' OR (cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL)",
            name="ck_dorm_checkout_cancelled",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        f"ix_{CHECKOUT}_tenant_id", CHECKOUT, ["tenant_id"],
    )
    op.create_index(
        "ix_dorm_checkout_student_status", CHECKOUT,
        ["tenant_id", "student_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_checkout_building_status", CHECKOUT,
        ["tenant_id", "building_id", "status", "is_deleted"],
    )


def downgrade() -> None:
    if _scalar(f"SELECT COUNT(*) FROM {CHECKOUT}"):
        raise RuntimeError(
            "D4 downgrade blocked: checkout workflow data exists; archive/export it before downgrade"
        )
    op.drop_index("ix_dorm_checkout_building_status", table_name=CHECKOUT)
    op.drop_index("ix_dorm_checkout_student_status", table_name=CHECKOUT)
    op.drop_index(f"ix_{CHECKOUT}_tenant_id", table_name=CHECKOUT)
    op.drop_table(CHECKOUT)
    op.drop_constraint("ck_dorm_stay_lifecycle", STAY, type_="check")
    op.drop_constraint("ck_dorm_stay_status", STAY, type_="check")

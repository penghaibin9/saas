"""Dorm D2: canonical stay history and allocation batch foundation.

Revision ID: 20260901_dorm_stay_alloc_d2
Revises: 20260901_orientation_batch_o1

Only stable, same-tenant occupied-bed chains are backfilled.  Legacy
``t_cs_dorm_record`` strings are deliberately excluded because they cannot
prove a building/room/bed identity.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260901_dorm_stay_alloc_d2"
down_revision = "20260901_orientation_batch_o1"
branch_labels = None
depends_on = None

assert len(revision) <= 32

STAY = "t_affairs_dorm_stay"
ALLOCATION_BATCH = "t_affairs_dorm_allocation_batch"
ALLOCATION_ITEM = "t_affairs_dorm_allocation_item"
BED = "t_affairs_dorm_bed"
ROOM = "t_affairs_dorm_room"
BUILDING = "t_affairs_dorm_building"
STUDENT = "t_student_profile"
ORIENTATION_BATCH = "t_orientation_batch"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260901_dorm_stay_alloc_d2 requires MySQL")


def _common_columns() -> list[sa.Column]:
    return [
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
    ]


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", sa.BigInteger(), nullable=False,
            comment="租户(学校)ID，行级隔离",
        ),
    ]


def _preflight_legacy_occupancy() -> None:
    """Fail before MySQL non-transactional DDL when current occupancy is ambiguous."""
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    required = {BED, ROOM, BUILDING, STUDENT, ORIENTATION_BATCH}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("D2 requires existing authority tables: " + ",".join(missing))
    invalid_chain = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {BED} b
        LEFT JOIN {ROOM} r
          ON r.id=b.room_id AND r.tenant_id=b.tenant_id
         AND r.building_id=b.building_id AND r.is_deleted=0
        LEFT JOIN {BUILDING} g
          ON g.id=b.building_id AND g.tenant_id=b.tenant_id AND g.is_deleted=0
        LEFT JOIN {STUDENT} s
          ON s.id=b.student_id AND s.tenant_id=b.tenant_id AND s.is_deleted=0
        WHERE b.status='OCCUPIED' AND b.is_deleted=0
          AND (b.student_id IS NULL OR r.id IS NULL OR g.id IS NULL OR s.id IS NULL)
    """)).scalar() or 0)
    duplicate_student = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, student_id
          FROM {BED}
          WHERE status='OCCUPIED' AND is_deleted=0 AND student_id IS NOT NULL
          GROUP BY tenant_id, student_id
          HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0)
    if invalid_chain or duplicate_student:
        raise RuntimeError(
            "D2 legacy occupancy preflight failed before DDL: "
            f"invalid_occupied_chain={invalid_chain}, "
            f"duplicate_occupied_student={duplicate_student}"
        )


def _expand() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    required = {BED, ROOM, BUILDING, STUDENT, ORIENTATION_BATCH}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("D2 requires existing authority tables: " + ",".join(missing))
    collisions = sorted({STAY, ALLOCATION_BATCH, ALLOCATION_ITEM} & tables)
    if collisions:
        raise RuntimeError("D2 target tables already exist outside this revision: " + ",".join(collisions))

    op.create_table(
        STAY,
        *_identity_columns(),
        sa.Column(
            "student_id", sa.BigInteger(), nullable=False,
            comment="学生 Authority → t_student_profile.id",
        ),
        sa.Column(
            "bed_id", sa.BigInteger(), nullable=False,
            comment="床位 Authority → t_affairs_dorm_bed.id",
        ),
        sa.Column(
            "building_id", sa.BigInteger(), nullable=False,
            comment="楼栋稳定 ID 快照",
        ),
        sa.Column(
            "room_id", sa.BigInteger(), nullable=False,
            comment="房间稳定 ID 快照",
        ),
        sa.Column(
            "stay_type", sa.String(50), nullable=False,
            comment="CURRENT_OCCUPANCY/ALLOCATION/TRANSFER/HISTORY_IMPORT",
        ),
        sa.Column(
            "source_type", sa.String(50), nullable=False,
            comment="DORM_BED_BACKFILL/ALLOCATION/TRANSFER/MANUAL",
        ),
        sa.Column(
            "source_biz_id", sa.String(100), nullable=False,
            comment="来源业务稳定键",
        ),
        sa.Column("checkin_at", sa.DateTime(), nullable=True),
        sa.Column("checkout_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="RESERVED/ACTIVE/ENDED/CANCELLED",
        ),
        sa.Column("checkin_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("checkout_operator_id", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "source_type", "source_biz_id",
            name="uk_dorm_stay_source",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{STAY}_tenant_id", STAY, ["tenant_id"])
    op.create_index(
        "ix_dorm_stay_student_status",
        STAY,
        ["tenant_id", "student_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_stay_bed_status",
        STAY,
        ["tenant_id", "bed_id", "status", "is_deleted"],
    )

    op.create_table(
        ALLOCATION_BATCH,
        *_identity_columns(),
        sa.Column("batch_no", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column(
            "source_type", sa.String(50), nullable=False,
            comment="ORIENTATION/GENERAL/ROLLING",
        ),
        sa.Column(
            "orientation_batch_id", sa.BigInteger(), nullable=True,
            comment="可选迎新批次 Authority → t_orientation_batch.id",
        ),
        sa.Column(
            "mode", sa.String(50), nullable=False,
            comment="ADMIN_AUTO/ADMIN_MANUAL/STUDENT_SELECT/POST_CHECKIN_PUBLISH",
        ),
        sa.Column("open_at", sa.DateTime(), nullable=False),
        sa.Column("close_at", sa.DateTime(), nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="DRAFT/PUBLISHED/CLOSED/CANCELLED",
        ),
        sa.Column("rules_json", sa.JSON(), nullable=True),
        sa.Column("resource_scope_json", sa.JSON(), nullable=True),
        sa.Column("student_scope_json", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "batch_no", name="uk_dorm_alloc_batch_no",
        ),
        sa.CheckConstraint(
            "open_at < close_at", name="ck_dorm_alloc_batch_window",
        ),
        sa.CheckConstraint(
            "mode IN ('ADMIN_AUTO','ADMIN_MANUAL','STUDENT_SELECT','POST_CHECKIN_PUBLISH')",
            name="ck_dorm_alloc_batch_mode",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','CLOSED','CANCELLED')",
            name="ck_dorm_alloc_batch_status",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        f"ix_{ALLOCATION_BATCH}_tenant_id", ALLOCATION_BATCH, ["tenant_id"],
    )
    op.create_index(
        "ix_dorm_alloc_batch_orientation",
        ALLOCATION_BATCH,
        ["tenant_id", "orientation_batch_id", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_alloc_batch_status_window",
        ALLOCATION_BATCH,
        ["tenant_id", "status", "open_at", "close_at", "is_deleted"],
    )

    op.create_table(
        ALLOCATION_ITEM,
        *_identity_columns(),
        sa.Column(
            "allocation_batch_id", sa.BigInteger(), nullable=False,
            comment="住宿分配批次稳定 ID",
        ),
        sa.Column(
            "student_id", sa.BigInteger(), nullable=False,
            comment="学生 Authority → t_student_profile.id",
        ),
        sa.Column(
            "bed_id", sa.BigInteger(), nullable=True,
            comment="提议/预留/确认的床位稳定 ID",
        ),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="PENDING/PROPOSED/RESERVED/CONFIRMED/CONFLICT/CANCELLED",
        ),
        sa.Column(
            "source", sa.String(50), nullable=False,
            comment="AUTO/MANUAL/STUDENT_SELECT/IMPORT",
        ),
        sa.Column("conflict_code", sa.String(100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "allocation_batch_id", "student_id",
            name="uk_dorm_alloc_item_student",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','PROPOSED','RESERVED','CONFIRMED','CONFLICT','CANCELLED')",
            name="ck_dorm_alloc_item_status",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        f"ix_{ALLOCATION_ITEM}_tenant_id", ALLOCATION_ITEM, ["tenant_id"],
    )
    op.create_index(
        "ix_dorm_alloc_item_bed_status",
        ALLOCATION_ITEM,
        ["tenant_id", "bed_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_alloc_item_batch_status",
        ALLOCATION_ITEM,
        ["tenant_id", "allocation_batch_id", "status", "is_deleted"],
    )


def _backfill() -> None:
    bind = op.get_bind()
    bind.execute(text(f"""
        INSERT INTO {STAY} (
          tenant_id, student_id, bed_id, building_id, room_id,
          stay_type, source_type, source_biz_id,
          checkin_at, checkout_at, status,
          checkin_operator_id, checkout_operator_id,
          created_at, created_by, updated_at, updated_by, is_deleted, version
        )
        SELECT
          b.tenant_id, b.student_id, b.id, b.building_id, b.room_id,
          'CURRENT_OCCUPANCY', 'DORM_BED_BACKFILL', CAST(b.id AS CHAR),
          COALESCE(b.occupied_at, b.created_at), NULL, 'ACTIVE',
          COALESCE(b.updated_by, b.created_by), NULL,
          COALESCE(b.occupied_at, b.created_at), b.created_by,
          COALESCE(b.updated_at, b.occupied_at, b.created_at), b.updated_by,
          0, 0
        FROM {BED} b
        JOIN {ROOM} r
          ON r.id=b.room_id AND r.tenant_id=b.tenant_id
         AND r.building_id=b.building_id AND r.is_deleted=0
        JOIN {BUILDING} g
          ON g.id=b.building_id AND g.tenant_id=b.tenant_id AND g.is_deleted=0
        JOIN {STUDENT} s
          ON s.id=b.student_id AND s.tenant_id=b.tenant_id AND s.is_deleted=0
        WHERE b.status='OCCUPIED' AND b.is_deleted=0 AND b.student_id IS NOT NULL
    """))


def _validate_and_switch() -> None:
    bind = op.get_bind()
    invalid_occupied_chain = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {BED} b
        LEFT JOIN {ROOM} r
          ON r.id=b.room_id AND r.tenant_id=b.tenant_id
         AND r.building_id=b.building_id AND r.is_deleted=0
        LEFT JOIN {BUILDING} g
          ON g.id=b.building_id AND g.tenant_id=b.tenant_id AND g.is_deleted=0
        LEFT JOIN {STUDENT} s
          ON s.id=b.student_id AND s.tenant_id=b.tenant_id AND s.is_deleted=0
        WHERE b.status='OCCUPIED' AND b.is_deleted=0
          AND (b.student_id IS NULL OR r.id IS NULL OR g.id IS NULL OR s.id IS NULL)
    """)).scalar() or 0)
    duplicate_occupied_student = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, student_id
          FROM {BED}
          WHERE status='OCCUPIED' AND is_deleted=0 AND student_id IS NOT NULL
          GROUP BY tenant_id, student_id
          HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0)
    occupied_count = int(bind.execute(text(
        f"SELECT COUNT(*) FROM {BED} "
        "WHERE status='OCCUPIED' AND is_deleted=0"
    )).scalar() or 0)
    backfill_count = int(bind.execute(text(
        f"SELECT COUNT(*) FROM {STAY} "
        "WHERE status='ACTIVE' AND is_deleted=0 "
        "AND source_type='DORM_BED_BACKFILL'"
    )).scalar() or 0)
    invalid_stay_chain = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {STAY} d
        LEFT JOIN {BED} b
          ON b.id=d.bed_id AND b.tenant_id=d.tenant_id AND b.is_deleted=0
        LEFT JOIN {ROOM} r
          ON r.id=d.room_id AND r.tenant_id=d.tenant_id
         AND r.building_id=d.building_id AND r.is_deleted=0
        LEFT JOIN {BUILDING} g
          ON g.id=d.building_id AND g.tenant_id=d.tenant_id AND g.is_deleted=0
        LEFT JOIN {STUDENT} s
          ON s.id=d.student_id AND s.tenant_id=d.tenant_id AND s.is_deleted=0
        WHERE d.is_deleted=0
          AND (b.id IS NULL OR r.id IS NULL OR g.id IS NULL OR s.id IS NULL
               OR b.room_id<>d.room_id OR b.building_id<>d.building_id)
    """)).scalar() or 0)
    duplicate_active_student = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, student_id
          FROM {STAY}
          WHERE status='ACTIVE' AND is_deleted=0
          GROUP BY tenant_id, student_id
          HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0)
    duplicate_active_bed = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, bed_id
          FROM {STAY}
          WHERE status='ACTIVE' AND is_deleted=0
          GROUP BY tenant_id, bed_id
          HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0)
    if (
        invalid_occupied_chain
        or duplicate_occupied_student
        or occupied_count != backfill_count
        or invalid_stay_chain
        or duplicate_active_student
        or duplicate_active_bed
    ):
        raise RuntimeError(
            "D2 validation failed: "
            f"invalid_occupied_chain={invalid_occupied_chain}, "
            f"duplicate_occupied_student={duplicate_occupied_student}, "
            f"occupied={occupied_count}, backfilled={backfill_count}, "
            f"invalid_stay_chain={invalid_stay_chain}, "
            f"duplicate_active_student={duplicate_active_student}, "
            f"duplicate_active_bed={duplicate_active_bed}"
        )


def upgrade() -> None:
    _require_mysql()
    _preflight_legacy_occupancy()
    _expand()
    _backfill()
    _validate_and_switch()


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if ALLOCATION_ITEM in tables:
        item_count = int(bind.execute(text(
            f"SELECT COUNT(*) FROM {ALLOCATION_ITEM}"
        )).scalar() or 0)
        if item_count:
            raise RuntimeError("D2 downgrade blocked: allocation items already exist")
    if ALLOCATION_BATCH in tables:
        batch_count = int(bind.execute(text(
            f"SELECT COUNT(*) FROM {ALLOCATION_BATCH}"
        )).scalar() or 0)
        if batch_count:
            raise RuntimeError("D2 downgrade blocked: allocation batches already exist")
    if STAY in tables:
        non_backfill_count = int(bind.execute(text(
            f"SELECT COUNT(*) FROM {STAY} "
            "WHERE source_type<>'DORM_BED_BACKFILL'"
        )).scalar() or 0)
        if non_backfill_count:
            raise RuntimeError("D2 downgrade blocked: non-backfill stay history already exists")

    for table in (ALLOCATION_ITEM, ALLOCATION_BATCH, STAY):
        if table in set(inspect(bind).get_table_names()):
            op.drop_table(table)

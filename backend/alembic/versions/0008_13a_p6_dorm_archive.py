"""13A-P6: 建宿舍房源 6 表(building/room/bed/transfer/check_task/check_record) + 归档 2 表

Revision ID: 0008_13a_p6_dorm_archive
Revises: 0007_13a_p5_talk_family
Create Date: 2026-07-06

房源三级(楼/房/床),床位占用变更事务内回写 t_cs_dorm_record(应用层)。
room/bed 唯一键防重复铺床。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0008_13a_p6_dorm_archive"
down_revision = "0007_13a_p5_talk_family"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
BUILDING = "t_affairs_dorm_building"
ROOM = "t_affairs_dorm_room"
BED = "t_affairs_dorm_bed"
TRANSFER = "t_affairs_dorm_transfer"
CHECK_TASK = "t_affairs_dorm_check_task"
CHECK_REC = "t_affairs_dorm_check_record"
ARCH_BATCH = "t_affairs_archive_batch"
ARCH_PKG = "t_affairs_archive_package"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _pk_tenant(*extra):
    return [
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        *extra,
    ]


def _common_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _create(bind, table, cols, indexes=(), uniques=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix_col in indexes:
        op.create_index(f"ix_{table}_{ix_col}", table, [ix_col])
    for name, ucols in uniques:
        op.create_unique_constraint(name, table, list(ucols))


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, BUILDING, _pk_tenant(
        sa.Column("building_name", sa.String(length=100), nullable=False),
        sa.Column("building_code", sa.String(length=50), nullable=True),
        sa.Column("gender_limit", sa.String(length=20), nullable=False),
        sa.Column("manager_teacher_key", sa.String(length=100), nullable=True),
        sa.Column("floor_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "building_code"))

    _create(bind, ROOM, _pk_tenant(
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("floor_no", sa.Integer(), nullable=False),
        sa.Column("room_no", sa.String(length=50), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("room_type", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "building_id"),
       uniques=(("uk_dorm_room_building_no", ("tenant_id", "building_id", "room_no")),))

    _create(bind, BED, _pk_tenant(
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("bed_no", sa.String(length=50), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("occupied_at", sa.DateTime(), nullable=True),
        sa.Column("cs_dorm_record_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "building_id", "room_id", "student_id"),
       uniques=(("uk_dorm_bed_room_no", ("tenant_id", "room_id", "bed_no")),))

    _create(bind, TRANSFER, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("from_bed_id", sa.BigInteger(), nullable=True),
        sa.Column("to_bed_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_node", sa.String(length=50), nullable=True),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "student_id", "status", "workflow_instance_id"))

    _create(bind, CHECK_TASK, _pk_tenant(
        sa.Column("task_name", sa.String(length=200), nullable=False),
        sa.Column("building_id", sa.BigInteger(), nullable=True),
        sa.Column("check_type", sa.String(length=50), nullable=False),
        sa.Column("checker_key", sa.String(length=100), nullable=True),
        sa.Column("planned_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "building_id", "status"))

    _create(bind, CHECK_REC, _pk_tenant(
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=True),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("issue_type", sa.String(length=50), nullable=True),
        sa.Column("detail", sa.String(length=1000), nullable=True),
        sa.Column("rectify_deadline", sa.DateTime(), nullable=True),
        sa.Column("related_exception_id", sa.BigInteger(), nullable=True),
        sa.Column("related_risk_id", sa.BigInteger(), nullable=True),
        sa.Column("student_ids_json", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "task_id", "room_id", "status"))

    _create(bind, ARCH_BATCH, _pk_tenant(
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("year_code", sa.String(length=50), nullable=True),
        sa.Column("scope_json", sa.String(length=2000), nullable=True),
        sa.Column("confirm_by", sa.String(length=100), nullable=True),
        sa.Column("confirm_at", sa.DateTime(), nullable=True),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "year_code", "status"))

    _create(bind, ARCH_PKG, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("missing_items_json", sa.String(length=2000), nullable=True),
        sa.Column("package_file_id", sa.BigInteger(), nullable=True),
        sa.Column("export_task_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "student_id", "status"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (ARCH_PKG, ARCH_BATCH, CHECK_REC, CHECK_TASK, TRANSFER, BED, ROOM, BUILDING):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)

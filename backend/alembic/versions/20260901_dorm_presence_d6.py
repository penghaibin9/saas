"""D6 dorm presence provider boundary and normalized access events.

Revision ID: 20260901_dorm_presence_d6
Revises: 20260901_dorm_inspection_d5
"""
from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_dorm_presence_d6"
down_revision = "20260901_dorm_inspection_d5"
branch_labels = None
depends_on = None

EVENT = "t_affairs_dorm_access_event"
CONFIG_DEFINITION = "t_config_definition"
CONFIG_OVERRIDE = "t_config_override"
CONFIG_ACTIVATION = "t_config_activation"
SYS_CONFIG = "t_sys_config"
CONFIG_KEY = "DORM_PRESENCE_POLICY"

DEFAULT_POLICY = {
    "policyVersion": 1,
    "provider": "NONE",
    "curfewTime": "22:30",
    "lateGraceMinutes": 15,
    "notReturnTime": "23:30",
    "noEventHours": 24,
    "consecutiveAnomalyThreshold": 3,
}


def _scalar(sql: str, params: dict | None = None) -> int:
    return int(op.get_bind().execute(sa.text(sql), params or {}).scalar() or 0)


def _preflight() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260901_dorm_presence_d6 requires MySQL")
    tables = set(inspect(bind).get_table_names())
    required = {
        "t_affairs_dorm_bed", "t_affairs_dorm_building", "t_student_profile", "t_cs_leave",
        CONFIG_DEFINITION, CONFIG_OVERRIDE, CONFIG_ACTIVATION, SYS_CONFIG,
    }
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("D6 requires existing authority tables: " + ",".join(missing))
    if EVENT in tables:
        raise RuntimeError("D6 access event table already exists outside this revision")
    invalid_config = _scalar(
        f"SELECT COUNT(*) FROM {CONFIG_DEFINITION} "
        "WHERE config_key=:key AND (is_deleted<>0 OR value_type<>'JSON' OR status<>'ACTIVE')",
        {"key": CONFIG_KEY},
    )
    if invalid_config:
        raise RuntimeError(f"D6 preflight failed before DDL: invalid_config={invalid_config}")


def _register_default_policy() -> None:
    if _scalar(f"SELECT COUNT(*) FROM {CONFIG_DEFINITION} WHERE config_key=:key", {"key": CONFIG_KEY}):
        return
    now = datetime.utcnow()
    table = sa.table(
        CONFIG_DEFINITION,
        sa.column("config_key", sa.String()), sa.column("domain_code", sa.String()),
        sa.column("config_name", sa.String()), sa.column("value_type", sa.String()),
        sa.column("validation_json", sa.JSON()), sa.column("default_json", sa.JSON()),
        sa.column("platform_floor_json", sa.JSON()), sa.column("school_editable", sa.Boolean()),
        sa.column("owner_code", sa.String()), sa.column("consumer_json", sa.JSON()),
        sa.column("cache_scope", sa.String()), sa.column("risk_level", sa.String()),
        sa.column("status", sa.String()), sa.column("created_at", sa.DateTime()),
        sa.column("created_by", sa.BigInteger()), sa.column("updated_at", sa.DateTime()),
        sa.column("updated_by", sa.BigInteger()), sa.column("is_deleted", sa.Boolean()),
        sa.column("version", sa.Integer()),
    )
    op.bulk_insert(table, [{
        "config_key": CONFIG_KEY,
        "domain_code": "STUDENT_AFFAIRS",
        "config_name": "宿舍归寝 Provider 与研判规则",
        "value_type": "JSON",
        "validation_json": {"requiredKeys": [
            "policyVersion", "provider", "curfewTime", "lateGraceMinutes",
            "notReturnTime", "noEventHours", "consecutiveAnomalyThreshold",
        ]},
        "default_json": {"value": DEFAULT_POLICY},
        "platform_floor_json": {},
        "school_editable": True,
        "owner_code": "DORM_D6",
        "consumer_json": {"items": [
            "dorm_presence_service.provider_status",
            "dorm_presence_service.evaluate_presence",
        ]},
        "cache_scope": "TENANT",
        "risk_level": "HIGH",
        "status": "ACTIVE",
        "created_at": now, "created_by": None, "updated_at": now, "updated_by": None,
        "is_deleted": False, "version": 1,
    }])


def upgrade() -> None:
    _preflight()
    op.create_table(
        EVENT,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("device_ref", sa.String(160), nullable=True),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("raw_ref_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
        sa.UniqueConstraint("tenant_id", "provider", "provider_event_id", name="uk_dorm_access_provider_event"),
        sa.CheckConstraint(
            "provider IN ('MANUAL','ACCESS_GATE','FACE_GATE','THIRD_PARTY_CAMPUS')",
            name="ck_dorm_access_provider",
        ),
        sa.CheckConstraint("event_type IN ('IN','OUT')", name="ck_dorm_access_event_type"),
        sa.CheckConstraint("student_id > 0 AND building_id > 0", name="ck_dorm_access_real_subject"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_dorm_access_student_time", EVENT, ["tenant_id", "student_id", "event_time", "is_deleted"])
    op.create_index("ix_dorm_access_building_time", EVENT, ["tenant_id", "building_id", "event_time", "is_deleted"])
    op.create_index("ix_dorm_access_provider_time", EVENT, ["tenant_id", "provider", "event_time", "is_deleted"])
    _register_default_policy()


def downgrade() -> None:
    runtime_events = _scalar(f"SELECT COUNT(*) FROM {EVENT}")
    config_state = _scalar(
        f"SELECT COUNT(*) FROM {CONFIG_OVERRIDE} WHERE config_key=:key AND is_deleted=0", {"key": CONFIG_KEY}
    ) + _scalar(
        f"SELECT COUNT(*) FROM {CONFIG_ACTIVATION} WHERE config_key=:key", {"key": CONFIG_KEY}
    ) + _scalar(
        f"SELECT COUNT(*) FROM {SYS_CONFIG} WHERE config_key=:key AND is_deleted=0", {"key": CONFIG_KEY}
    )
    if runtime_events or config_state:
        raise RuntimeError(
            "D6 downgrade blocked: normalized events or school policy state exists; "
            f"events={runtime_events}, config_state={config_state}"
        )
    op.execute(sa.text(
        f"DELETE FROM {CONFIG_DEFINITION} WHERE config_key=:key AND owner_code='DORM_D6'"
    ).bindparams(key=CONFIG_KEY))
    op.drop_index("ix_dorm_access_provider_time", table_name=EVENT)
    op.drop_index("ix_dorm_access_building_time", table_name=EVENT)
    op.drop_index("ix_dorm_access_student_time", table_name=EVENT)
    op.drop_table(EVENT)

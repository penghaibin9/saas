"""Orientation O2: versioned flow and canonical student-step authority.

Revision ID: 20260901_orientation_flow_o2
Revises: 20260901_dorm_stay_alloc_d2

The tenant flow-config rows are copied into a published immutable version.
Legacy ``steps_json`` values are mapped through an explicit allow-list; they
remain only as a compatibility projection after this revision.
"""
from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260901_orientation_flow_o2"
down_revision = "20260901_dorm_stay_alloc_d2"
branch_labels = None
depends_on = None

assert len(revision) <= 32

FLOW_CONFIG = "t_orientation_flow_config"
FLOW_VERSION = "t_orientation_flow_version"
FLOW_STEP = "t_orientation_flow_step"
STUDENT_STEP = "t_orientation_student_step"
BATCH = "t_orientation_batch"
STUDENT = "t_orientation_student"

DEFAULT_STEPS = (
    ("ACTIVATE", "账号激活"),
    ("INFO", "信息核对"),
    ("MATERIAL", "材料上传"),
    ("PAYMENT", "缴费/绿色通道"),
    ("DORM", "宿舍确认"),
    ("CHECKIN", "现场报到"),
    ("CONFIRM", "学院确认"),
)

LEGACY_STATUS_MAP = {
    "TODO": "NOT_STARTED",
    "NOT_STARTED": "NOT_STARTED",
    "DOING": "IN_PROGRESS",
    "IN_PROGRESS": "IN_PROGRESS",
    "BLOCKED": "BLOCKED",
    "DONE": "DONE",
    "NOT_REQUIRED": "NOT_REQUIRED",
}


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260901_orientation_flow_o2 requires MySQL")


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", sa.BigInteger(), nullable=False,
            comment="租户(学校)ID，行级隔离",
        ),
    ]


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
    ]


def _json_object(value: object, student_id: int) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"O2 legacy steps_json is invalid for orientation_student_id={student_id}"
            ) from exc
        if isinstance(decoded, dict):
            return decoded
    raise RuntimeError(
        f"O2 legacy steps_json must be an object for orientation_student_id={student_id}"
    )


def _preflight_legacy_steps() -> None:
    """Refuse ambiguous projection data before MySQL non-transactional DDL."""
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    required = {FLOW_CONFIG, BATCH, STUDENT}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("O2 requires existing orientation tables: " + ",".join(missing))
    collisions = sorted({FLOW_VERSION, FLOW_STEP, STUDENT_STEP} & tables)
    if collisions:
        raise RuntimeError(
            "O2 target tables already exist outside this revision: " + ",".join(collisions)
        )

    invalid_batch_link = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {STUDENT} o
        LEFT JOIN {BATCH} b ON b.id=o.batch_id AND b.tenant_id=o.tenant_id
        WHERE b.id IS NULL
    """)).scalar() or 0)
    invalid_config = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {FLOW_CONFIG}
        WHERE is_deleted=0
          AND (step_key IS NULL OR TRIM(step_key)='' OR step_name IS NULL OR TRIM(step_name)=''
               OR sort_order < 0)
    """)).scalar() or 0)

    invalid_status: list[str] = []
    unsupported_waiver: list[int] = []
    rows = bind.execute(text(
        f"SELECT id, steps_json FROM {STUDENT} ORDER BY id"
    )).mappings()
    for row in rows:
        student_id = int(row["id"])
        raw = _json_object(row["steps_json"], student_id)
        for key, value in raw.items():
            normalized = str(value or "").strip().upper()
            if normalized == "WAIVED":
                unsupported_waiver.append(student_id)
            elif normalized not in LEGACY_STATUS_MAP:
                invalid_status.append(f"{student_id}:{str(key)[:50]}:{normalized[:30]}")
    if invalid_batch_link or invalid_config or invalid_status or unsupported_waiver:
        raise RuntimeError(
            "O2 legacy preflight failed before DDL: "
            f"invalid_batch_link={invalid_batch_link}, invalid_config={invalid_config}, "
            f"invalid_status={invalid_status[:10]}, "
            f"waived_without_evidence={unsupported_waiver[:10]}"
        )


def _expand() -> None:
    op.create_table(
        FLOW_VERSION,
        *_identity_columns(),
        sa.Column("version_no", sa.Integer(), nullable=False, comment="租户内递增版本号"),
        sa.Column("version_name", sa.String(200), nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="DRAFT/PUBLISHED/RETIRED",
        ),
        sa.Column(
            "source_type", sa.String(50), nullable=False,
            comment="MANUAL/LEGACY_CONFIG_BACKFILL",
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.BigInteger(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint("tenant_id", "version_no", name="uk_ori_flow_version_no"),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_ori_flow_version_status",
        ),
        sa.CheckConstraint(
            "status <> 'PUBLISHED' OR published_at IS NOT NULL",
            name="ck_ori_flow_version_publish_time",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{FLOW_VERSION}_tenant_id", FLOW_VERSION, ["tenant_id"])
    op.create_index(
        "ix_ori_flow_version_status",
        FLOW_VERSION,
        ["tenant_id", "status", "is_deleted", "version_no"],
    )

    op.create_table(
        FLOW_STEP,
        *_identity_columns(),
        sa.Column(
            "flow_version_id", sa.BigInteger(), nullable=False,
            comment="流程版本 Authority → t_orientation_flow_version.id",
        ),
        sa.Column("step_key", sa.String(50), nullable=False),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("remark", sa.String(500), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "flow_version_id", "step_key",
            name="uk_ori_flow_step_version_key",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_ori_flow_step_sort_order"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{FLOW_STEP}_tenant_id", FLOW_STEP, ["tenant_id"])
    op.create_index(
        "ix_ori_flow_step_version_order",
        FLOW_STEP,
        ["tenant_id", "flow_version_id", "sort_order", "is_deleted"],
    )

    op.create_table(
        STUDENT_STEP,
        *_identity_columns(),
        sa.Column(
            "orientation_student_id", sa.BigInteger(), nullable=False,
            comment="迎新学生过程实例 → t_orientation_student.id",
        ),
        sa.Column(
            "flow_version_id", sa.BigInteger(), nullable=False,
            comment="该学生冻结的流程版本",
        ),
        sa.Column(
            "flow_step_id", sa.BigInteger(), nullable=False,
            comment="冻结流程步骤 → t_orientation_flow_step.id",
        ),
        sa.Column("step_key", sa.String(50), nullable=False, comment="步骤业务键快照"),
        sa.Column(
            "status", sa.String(50), nullable=False,
            comment="NOT_STARTED/IN_PROGRESS/BLOCKED/DONE/WAIVED/NOT_REQUIRED",
        ),
        sa.Column(
            "status_source", sa.String(50), nullable=False,
            comment="LEGACY_STEPS_JSON/PROCESS_FACT/MANUAL_WAIVER/RULE",
        ),
        sa.Column("source_biz_id", sa.String(100), nullable=True),
        sa.Column("blocked_reason", sa.String(500), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(), nullable=False),
        sa.Column("waived_at", sa.DateTime(), nullable=True),
        sa.Column("waived_by", sa.BigInteger(), nullable=True),
        sa.Column("waive_reason", sa.String(500), nullable=True),
        sa.Column("waive_evidence_ref", sa.String(200), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "orientation_student_id", "step_key",
            name="uk_ori_student_step_key",
        ),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED','IN_PROGRESS','BLOCKED','DONE','WAIVED','NOT_REQUIRED')",
            name="ck_ori_student_step_status",
        ),
        sa.CheckConstraint(
            "status <> 'WAIVED' OR (waived_at IS NOT NULL AND waived_by IS NOT NULL "
            "AND waive_evidence_ref IS NOT NULL AND CHAR_LENGTH(TRIM(waive_reason)) >= 5)",
            name="ck_ori_student_step_waiver_evidence",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{STUDENT_STEP}_tenant_id", STUDENT_STEP, ["tenant_id"])
    op.create_index(
        "ix_ori_student_step_student_status",
        STUDENT_STEP,
        ["tenant_id", "orientation_student_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_ori_student_step_flow_status",
        STUDENT_STEP,
        ["tenant_id", "flow_version_id", "status", "is_deleted"],
    )

    op.add_column(
        BATCH,
        sa.Column(
            "flow_version_id", sa.BigInteger(), nullable=True,
            comment="冻结的迎新流程版本 → t_orientation_flow_version.id；草稿发布前可空",
        ),
    )
    op.create_index(
        "ix_ori_batch_flow_active",
        BATCH,
        ["tenant_id", "flow_version_id", "status", "is_deleted"],
    )


def _tenant_steps(tenant_id: int) -> list[dict[str, object]]:
    bind = op.get_bind()
    rows = list(bind.execute(text(f"""
        SELECT step_key, step_name, enabled, required, sort_order, remark
        FROM {FLOW_CONFIG}
        WHERE tenant_id=:tenant_id AND is_deleted=0
        ORDER BY sort_order, id
    """), {"tenant_id": tenant_id}).mappings())
    if rows:
        return [dict(row) for row in rows]
    return [
        {
            "step_key": key,
            "step_name": name,
            "enabled": True,
            "required": True,
            "sort_order": index,
            "remark": "O2 default flow because no legacy config existed",
        }
        for index, (key, name) in enumerate(DEFAULT_STEPS)
    ]


def _backfill() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()
    tenants = [int(row[0]) for row in bind.execute(text(f"""
        SELECT tenant_id FROM {BATCH}
        UNION SELECT tenant_id FROM {STUDENT}
        UNION SELECT tenant_id FROM {FLOW_CONFIG}
        ORDER BY tenant_id
    """))]

    for tenant_id in tenants:
        result = bind.execute(text(f"""
            INSERT INTO {FLOW_VERSION}
              (tenant_id,version_no,version_name,status,source_type,published_at,published_by,
               remark,created_at,created_by,updated_at,updated_by,is_deleted,version)
            VALUES
              (:tenant_id,1,'O2 迁移发布版','PUBLISHED','LEGACY_CONFIG_BACKFILL',:now,NULL,
               'O2 copied the tenant flow-config snapshot; immutable compatibility version',
               :now,NULL,:now,NULL,0,0)
        """), {"tenant_id": tenant_id, "now": now})
        flow_version_id = int(result.lastrowid)

        step_ids: dict[str, int] = {}
        step_defs = _tenant_steps(tenant_id)
        for step in step_defs:
            result = bind.execute(text(f"""
                INSERT INTO {FLOW_STEP}
                  (tenant_id,flow_version_id,step_key,step_name,enabled,required,sort_order,remark,
                   created_at,created_by,updated_at,updated_by,is_deleted,version)
                VALUES
                  (:tenant_id,:flow_version_id,:step_key,:step_name,:enabled,:required,:sort_order,
                   :remark,:now,NULL,:now,NULL,0,0)
            """), {
                "tenant_id": tenant_id,
                "flow_version_id": flow_version_id,
                "step_key": str(step["step_key"]),
                "step_name": str(step["step_name"]),
                "enabled": bool(step["enabled"]),
                "required": bool(step["required"]),
                "sort_order": int(step["sort_order"]),
                "remark": step.get("remark"),
                "now": now,
            })
            step_ids[str(step["step_key"])] = int(result.lastrowid)

        bind.execute(text(f"""
            UPDATE {BATCH}
            SET flow_version_id=:flow_version_id
            WHERE tenant_id=:tenant_id AND flow_version_id IS NULL
        """), {"tenant_id": tenant_id, "flow_version_id": flow_version_id})

        students = bind.execute(text(f"""
            SELECT o.id, o.steps_json, o.blocked_step, o.blocked_reason, o.updated_at
            FROM {STUDENT} o
            JOIN {BATCH} b
              ON b.id=o.batch_id AND b.tenant_id=o.tenant_id
             AND b.flow_version_id=:flow_version_id
            WHERE o.tenant_id=:tenant_id
            ORDER BY o.id
        """), {
            "tenant_id": tenant_id,
            "flow_version_id": flow_version_id,
        }).mappings()
        for student in students:
            student_id = int(student["id"])
            projection = _json_object(student["steps_json"], student_id)
            normalized_projection = {
                str(key): str(value or "").strip().upper()
                for key, value in projection.items()
            }
            for step in step_defs:
                step_key = str(step["step_key"])
                raw_status = normalized_projection.get(step_key)
                if not bool(step["enabled"]) and raw_status in (None, "TODO", "NOT_STARTED"):
                    status = "NOT_REQUIRED"
                elif raw_status is None:
                    status = "NOT_STARTED"
                else:
                    status = LEGACY_STATUS_MAP[raw_status]
                blocked_reason = (
                    student["blocked_reason"]
                    if status == "BLOCKED" and student["blocked_step"] == step_key
                    else None
                )
                changed_at = student["updated_at"] or now
                bind.execute(text(f"""
                    INSERT INTO {STUDENT_STEP}
                      (tenant_id,orientation_student_id,flow_version_id,flow_step_id,step_key,
                       status,status_source,source_biz_id,blocked_reason,status_changed_at,
                       waived_at,waived_by,waive_reason,waive_evidence_ref,
                       created_at,created_by,updated_at,updated_by,is_deleted,version)
                    VALUES
                      (:tenant_id,:student_id,:flow_version_id,:flow_step_id,:step_key,
                       :status,'LEGACY_STEPS_JSON',:source_biz_id,:blocked_reason,:changed_at,
                       NULL,NULL,NULL,NULL,:now,NULL,:now,NULL,0,0)
                """), {
                    "tenant_id": tenant_id,
                    "student_id": student_id,
                    "flow_version_id": flow_version_id,
                    "flow_step_id": step_ids[step_key],
                    "step_key": step_key,
                    "status": status,
                    "source_biz_id": f"{student_id}:{step_key}",
                    "blocked_reason": blocked_reason,
                    "changed_at": changed_at,
                    "now": now,
                })


def _validate_and_contract() -> None:
    bind = op.get_bind()
    invalid_batch = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {BATCH} b
        LEFT JOIN {FLOW_VERSION} v
          ON v.id=b.flow_version_id AND v.tenant_id=b.tenant_id
        WHERE b.flow_version_id IS NULL OR v.id IS NULL OR v.status<>'PUBLISHED'
    """)).scalar() or 0)
    invalid_chain = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {STUDENT_STEP} ss
        LEFT JOIN {STUDENT} o
          ON o.id=ss.orientation_student_id AND o.tenant_id=ss.tenant_id
        LEFT JOIN {BATCH} b
          ON b.id=o.batch_id AND b.tenant_id=ss.tenant_id
        LEFT JOIN {FLOW_STEP} fs
          ON fs.id=ss.flow_step_id AND fs.tenant_id=ss.tenant_id
         AND fs.flow_version_id=ss.flow_version_id AND fs.step_key=ss.step_key
        WHERE o.id IS NULL OR b.id IS NULL OR fs.id IS NULL
           OR b.flow_version_id<>ss.flow_version_id
    """)).scalar() or 0)
    incomplete_students = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT o.id,
                 (SELECT COUNT(*) FROM {FLOW_STEP} fs
                   WHERE fs.tenant_id=o.tenant_id
                     AND fs.flow_version_id=b.flow_version_id AND fs.is_deleted=0) expected_count,
                 (SELECT COUNT(*) FROM {STUDENT_STEP} ss
                   WHERE ss.tenant_id=o.tenant_id
                     AND ss.orientation_student_id=o.id AND ss.is_deleted=0) actual_count
          FROM {STUDENT} o
          JOIN {BATCH} b ON b.id=o.batch_id AND b.tenant_id=o.tenant_id
        ) counts
        WHERE expected_count<>actual_count
    """)).scalar() or 0)
    invalid_waiver = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {STUDENT_STEP}
        WHERE status='WAIVED'
          AND (waived_at IS NULL OR waived_by IS NULL OR waive_evidence_ref IS NULL
               OR CHAR_LENGTH(TRIM(waive_reason)) < 5)
    """)).scalar() or 0)
    if invalid_batch or invalid_chain or incomplete_students or invalid_waiver:
        raise RuntimeError(
            "O2 validation failed: "
            f"invalid_batch={invalid_batch}, invalid_chain={invalid_chain}, "
            f"incomplete_students={incomplete_students}, invalid_waiver={invalid_waiver}"
        )

    op.create_check_constraint(
        "ck_ori_batch_active_flow",
        BATCH,
        "status = 'DRAFT' OR flow_version_id IS NOT NULL",
    )


def upgrade() -> None:
    _require_mysql()
    _preflight_legacy_steps()
    _expand()
    _backfill()
    _validate_and_contract()


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if FLOW_VERSION not in tables:
        return

    unsafe_student_steps = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {STUDENT_STEP}
        WHERE status_source<>'LEGACY_STEPS_JSON' OR version<>0 OR is_deleted<>0
    """)).scalar() or 0)
    unsafe_versions = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {FLOW_VERSION}
        WHERE source_type<>'LEGACY_CONFIG_BACKFILL' OR version<>0 OR is_deleted<>0
    """)).scalar() or 0)
    unsafe_steps = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {FLOW_STEP} WHERE version<>0 OR is_deleted<>0
    """)).scalar() or 0)
    unsafe_batch_link = int(bind.execute(text(f"""
        SELECT COUNT(*)
        FROM {BATCH} b
        LEFT JOIN {FLOW_VERSION} v
          ON v.id=b.flow_version_id AND v.tenant_id=b.tenant_id
         AND v.source_type='LEGACY_CONFIG_BACKFILL'
        WHERE b.flow_version_id IS NOT NULL AND v.id IS NULL
    """)).scalar() or 0)
    if unsafe_student_steps or unsafe_versions or unsafe_steps or unsafe_batch_link:
        raise RuntimeError(
            "O2 downgrade blocked: canonical flow/student-step data changed after backfill; "
            f"student_steps={unsafe_student_steps}, versions={unsafe_versions}, "
            f"flow_steps={unsafe_steps}, batch_links={unsafe_batch_link}"
        )

    op.drop_constraint("ck_ori_batch_active_flow", BATCH, type_="check")
    bind.execute(text(f"DELETE FROM {STUDENT_STEP}"))
    bind.execute(text(f"UPDATE {BATCH} SET flow_version_id=NULL"))
    op.drop_index("ix_ori_batch_flow_active", table_name=BATCH)
    op.drop_column(BATCH, "flow_version_id")
    op.drop_table(STUDENT_STEP)
    op.drop_table(FLOW_STEP)
    op.drop_table(FLOW_VERSION)

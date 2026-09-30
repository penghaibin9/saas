"""O4 material requirements, payment truth, green evidence and qualification decisions.

Revision ID: 20260901_orientation_qualification_o4
Revises: 20260901_dorm_checkout_d4
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_orientation_qualification_o4"
down_revision = "20260901_dorm_checkout_d4"
branch_labels = None
depends_on = None

STUDENT = "t_orientation_student"
GREEN = "t_green_channel_application"
FLOW_VERSION = "t_orientation_flow_version"
REQUIREMENT = "t_orientation_material_requirement"
PAYMENT = "t_orientation_payment_account"
DECISION = "t_orientation_qualification_decision"


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
    ]


def _preflight() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260901_orientation_qualification_o4 requires MySQL")
    tables = set(inspect(bind).get_table_names())
    missing = sorted({STUDENT, GREEN, FLOW_VERSION} - tables)
    if missing:
        raise RuntimeError("O4 requires existing authority tables: " + ",".join(missing))
    collisions = sorted({REQUIREMENT, PAYMENT, DECISION} & tables)
    if collisions:
        raise RuntimeError("O4 target tables already exist outside this revision: " + ",".join(collisions))
    cross_tenant_green = _scalar(f"""
        SELECT COUNT(*) FROM {GREEN} g
        LEFT JOIN {STUDENT} s ON s.id=g.ori_student_id AND s.tenant_id=g.tenant_id
        WHERE s.id IS NULL
    """)
    unsupported_green = _scalar(f"""
        SELECT COUNT(*) FROM {GREEN}
        WHERE status NOT IN ('SUBMITTED','REVIEWING','APPROVED','RETURNED','REJECTED','WITHDRAWN')
           OR COALESCE(apply_amount,0) < 0
    """)
    unsupported_payment = _scalar(f"""
        SELECT COUNT(*) FROM {STUDENT}
        WHERE payment_status NOT IN ('UNPAID','PARTIAL','PAID','WAIVED','DEFERRED','GREEN_CHANNEL')
           OR COALESCE(payable_amount,0) < 0 OR COALESCE(paid_amount,0) < 0
           OR (payment_status='PAID' AND COALESCE(paid_amount,0) < COALESCE(payable_amount,0))
    """)
    missing_flow = _scalar(f"""
        SELECT COUNT(*) FROM {STUDENT} s
        LEFT JOIN t_orientation_batch b
          ON b.id=s.batch_id AND b.tenant_id=s.tenant_id AND b.is_deleted=0
        LEFT JOIN {FLOW_VERSION} v
          ON v.id=b.flow_version_id AND v.tenant_id=s.tenant_id AND v.is_deleted=0
        WHERE s.is_deleted=0 AND (b.id IS NULL OR v.id IS NULL)
    """)
    if any((cross_tenant_green, unsupported_green, unsupported_payment, missing_flow)):
        raise RuntimeError(
            "O4 preflight failed before DDL: "
            f"cross_tenant_green={cross_tenant_green}, unsupported_green={unsupported_green}, "
            f"unsupported_payment={unsupported_payment}, missing_flow={missing_flow}"
        )


def upgrade() -> None:
    _preflight()

    op.add_column(
        GREEN,
        sa.Column(
            "student_id", sa.BigInteger(), nullable=True,
            comment="稳定学生 Authority → t_student_profile.id；旧未绑定记录可空",
        ),
    )
    op.add_column(
        GREEN,
        sa.Column("client_request_id", sa.String(100), nullable=True, comment="学生端提交幂等号；旧记录可空"),
    )
    op.execute(sa.text(f"""
        UPDATE {GREEN} g
        JOIN {STUDENT} s ON s.id=g.ori_student_id AND s.tenant_id=g.tenant_id
        SET g.student_id=s.student_id
    """))
    op.create_unique_constraint(
        "uk_ori_green_client_request", GREEN, ["tenant_id", "client_request_id"]
    )
    op.create_check_constraint(
        "ck_ori_green_status", GREEN,
        "status IN ('SUBMITTED','REVIEWING','APPROVED','RETURNED','REJECTED','WITHDRAWN')",
    )
    op.create_check_constraint("ck_ori_green_amount", GREEN, "apply_amount >= 0")
    op.create_index("ix_t_green_channel_application_student_id", GREEN, ["student_id"])
    op.create_index(
        "ix_ori_green_student_status", GREEN,
        ["tenant_id", "student_id", "status", "is_deleted"],
    )

    op.create_table(
        REQUIREMENT,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("flow_version_id", sa.BigInteger(), nullable=False, comment="冻结流程版本 → t_orientation_flow_version.id"),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("material_name", sa.String(100), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("requires_scan_clean", sa.Boolean(), nullable=False),
        sa.Column("allowed_exts_json", sa.JSON(), nullable=True),
        sa.Column("max_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, comment="DEFAULT_BACKFILL/MANUAL"),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "flow_version_id", "material_type",
            name="uk_ori_material_requirement_type",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_ori_material_requirement_sort"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{REQUIREMENT}_tenant_id", REQUIREMENT, ["tenant_id"])
    op.create_index(
        "ix_ori_material_requirement_flow", REQUIREMENT,
        ["tenant_id", "flow_version_id", "required", "is_deleted"],
    )
    op.execute(sa.text(f"""
        INSERT INTO {REQUIREMENT}
          (tenant_id,flow_version_id,material_type,material_name,required,requires_scan_clean,
           allowed_exts_json,max_size_bytes,sort_order,source_type,
           created_at,created_by,updated_at,updated_by,is_deleted,version)
        SELECT v.tenant_id,v.id,d.material_type,d.material_name,d.required,1,
               JSON_ARRAY('pdf','png','jpg','jpeg'),10485760,d.sort_order,'DEFAULT_BACKFILL',
               UTC_TIMESTAMP(),NULL,UTC_TIMESTAMP(),NULL,0,1
        FROM {FLOW_VERSION} v
        JOIN (
          SELECT 'ID_CARD' material_type,'身份证明' material_name,1 required,10 sort_order
          UNION ALL SELECT 'ADMISSION_LETTER','录取通知书',1,20
          UNION ALL SELECT 'PHOTO','证件照',0,30
          UNION ALL SELECT 'ARCHIVE','纸质档案凭证',0,40
        ) d
        WHERE v.is_deleted=0
    """))

    op.create_table(
        PAYMENT,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("payable_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_biz_id", sa.String(160), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint("tenant_id", "orientation_student_id", name="uk_ori_payment_student"),
        sa.UniqueConstraint("tenant_id", "source_type", "source_biz_id", name="uk_ori_payment_source"),
        sa.CheckConstraint(
            "status IN ('UNPAID','PARTIAL','PAID','WAIVED','DEFERRED')",
            name="ck_ori_payment_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('FINANCE_SYNC','MANUAL_VERIFIED','LEGACY_BACKFILL')",
            name="ck_ori_payment_source_type",
        ),
        sa.CheckConstraint("payable_amount >= 0 AND paid_amount >= 0", name="ck_ori_payment_amount"),
        sa.CheckConstraint("status <> 'PAID' OR paid_amount >= payable_amount", name="ck_ori_payment_paid_amount"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{PAYMENT}_tenant_id", PAYMENT, ["tenant_id"])
    op.create_index(f"ix_{PAYMENT}_student_id", PAYMENT, ["student_id"])
    op.create_index(
        "ix_ori_payment_student_status", PAYMENT,
        ["tenant_id", "student_id", "status", "is_deleted"],
    )
    op.execute(sa.text(f"""
        INSERT INTO {PAYMENT}
          (tenant_id,orientation_student_id,student_id,payable_amount,paid_amount,status,
           source_type,source_biz_id,synced_at,verified_by,
           created_at,created_by,updated_at,updated_by,is_deleted,version)
        SELECT tenant_id,id,student_id,COALESCE(payable_amount,0),COALESCE(paid_amount,0),
               CASE WHEN payment_status='GREEN_CHANNEL' THEN 'DEFERRED' ELSE payment_status END,
               'LEGACY_BACKFILL',CONCAT('orientation-student:',id),UTC_TIMESTAMP(),NULL,
               UTC_TIMESTAMP(),NULL,UTC_TIMESTAMP(),NULL,0,1
        FROM {STUDENT}
    """))

    op.create_table(
        DECISION,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("blockers_json", sa.JSON(), nullable=True),
        sa.Column("facts_json", sa.JSON(), nullable=True),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("evaluated_by", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_qualification_student"
        ),
        sa.CheckConstraint(
            "verdict IN ('QUALIFIED','NOT_QUALIFIED','MANUAL_REVIEW')",
            name="ck_ori_qualification_verdict",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(f"ix_{DECISION}_tenant_id", DECISION, ["tenant_id"])
    op.create_index(f"ix_{DECISION}_student_id", DECISION, ["student_id"])
    op.create_index(
        "ix_ori_qualification_verdict", DECISION,
        ["tenant_id", "verdict", "evaluated_at", "is_deleted"],
    )


def downgrade() -> None:
    if _scalar(f"SELECT COUNT(*) FROM {DECISION}"):
        raise RuntimeError("O4 downgrade blocked: qualification decisions exist")
    if _scalar(f"SELECT COUNT(*) FROM {PAYMENT} WHERE source_type<>'LEGACY_BACKFILL' OR version<>1"):
        raise RuntimeError("O4 downgrade blocked: runtime payment facts exist")
    if _scalar(f"SELECT COUNT(*) FROM {REQUIREMENT} WHERE source_type<>'DEFAULT_BACKFILL' OR version<>1"):
        raise RuntimeError("O4 downgrade blocked: material requirements were changed")
    if _scalar(f"SELECT COUNT(*) FROM {GREEN} WHERE client_request_id IS NOT NULL"):
        raise RuntimeError("O4 downgrade blocked: idempotent green-channel runtime data exists")

    op.drop_index("ix_ori_qualification_verdict", table_name=DECISION)
    op.drop_index(f"ix_{DECISION}_student_id", table_name=DECISION)
    op.drop_index(f"ix_{DECISION}_tenant_id", table_name=DECISION)
    op.drop_table(DECISION)
    op.drop_index("ix_ori_payment_student_status", table_name=PAYMENT)
    op.drop_index(f"ix_{PAYMENT}_student_id", table_name=PAYMENT)
    op.drop_index(f"ix_{PAYMENT}_tenant_id", table_name=PAYMENT)
    op.drop_table(PAYMENT)
    op.drop_index("ix_ori_material_requirement_flow", table_name=REQUIREMENT)
    op.drop_index(f"ix_{REQUIREMENT}_tenant_id", table_name=REQUIREMENT)
    op.drop_table(REQUIREMENT)
    op.drop_index("ix_ori_green_student_status", table_name=GREEN)
    op.drop_index("ix_t_green_channel_application_student_id", table_name=GREEN)
    op.drop_constraint("ck_ori_green_amount", GREEN, type_="check")
    op.drop_constraint("ck_ori_green_status", GREEN, type_="check")
    op.drop_constraint("uk_ori_green_client_request", GREEN, type_="unique")
    op.drop_column(GREEN, "client_request_id")
    op.drop_column(GREEN, "student_id")

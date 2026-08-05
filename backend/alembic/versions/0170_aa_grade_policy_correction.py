"""教务P0：租户级有效成绩策略与追加式成绩更正。

Revision ID: 0170_aa_grade_policy_correction
Revises: 0169_change_management
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0170_aa_grade_policy_correction"
down_revision = "0169_change_management"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0170_aa_grade_policy_correction requires MySQL")


def _common():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "t_aa_effective_grade_policy" not in tables:
        op.create_table(
            "t_aa_effective_grade_policy",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("policy_code", sa.String(80), nullable=False),
            sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("attempt_strategy", sa.String(40), nullable=False),
            sa.Column("makeup_strategy", sa.String(40), nullable=False, server_default="CAP_AND_OVERRIDE"),
            sa.Column("makeup_cap", sa.Integer()),
            sa.Column("retake_strategy", sa.String(40), nullable=False, server_default="REPLACE_IF_PASSED"),
            sa.Column("recognition_priority", sa.Integer(), nullable=False, server_default="75"),
            sa.Column("effective_from_term_id", sa.BigInteger()),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("activated_at", sa.DateTime()),
            *_common(),
            sa.UniqueConstraint("tenant_id", "policy_code", name="uk_aa_effective_grade_policy_code"),
        )
        op.create_index(
            "ix_aa_effective_grade_policy_active",
            "t_aa_effective_grade_policy",
            ["tenant_id", "status", "effective_from_term_id"],
        )
        # 把迁移前全租户固定规则显式固化为可追溯V1，避免升级后历史业务突然不可发布。
        if "t_tenant" in tables:
            op.execute(sa.text("""
                INSERT INTO t_aa_effective_grade_policy
                    (tenant_id, policy_code, policy_version, attempt_strategy, makeup_strategy,
                     makeup_cap, retake_strategy, recognition_priority, effective_from_term_id,
                     status, activated_at, created_at, updated_at, is_deleted, version)
                SELECT id, 'LEGACY_LATEST_ATTEMPT_V1', 1, 'LATEST_ATTEMPT', 'CAP_AND_OVERRIDE',
                       60, 'REPLACE_IF_PASSED', 75, NULL, 'ACTIVE', NOW(), NOW(), NOW(), 0, 0
                FROM t_tenant
            """))

    if "t_aa_grade_correction" not in tables:
        op.create_table(
            "t_aa_grade_correction",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("recheck_id", sa.BigInteger(), nullable=False),
            sa.Column("original_grade_id", sa.BigInteger(), nullable=False),
            sa.Column("corrected_grade_id", sa.BigInteger(), nullable=False),
            sa.Column("before_score", sa.Integer()),
            sa.Column("after_score", sa.Integer()),
            sa.Column("pass_line", sa.Integer(), nullable=False),
            sa.Column("rule_snapshot_json", sa.Text(), nullable=False),
            sa.Column("reason", sa.String(500)),
            sa.Column("operator", sa.String(100)),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            *_common(),
            sa.UniqueConstraint("tenant_id", "recheck_id", name="uk_aa_grade_correction_recheck"),
        )
        op.create_index("ix_aa_grade_correction_original", "t_aa_grade_correction", ["tenant_id", "original_grade_id"])
        op.create_index("ix_aa_grade_correction_corrected", "t_aa_grade_correction", ["tenant_id", "corrected_grade_id"])

    # 独立权限点：查看权限不得再执行持久化写入。
    permission_codes = (
        ("academicAffairs.stats.snapshot.view", "查看教务统计快照", "view"),
        ("academicAffairs.stats.snapshot.create", "创建教务统计快照", "create"),
        ("academicAffairs.stats.snapshot.manage", "管理教务统计快照", "manage"),
        ("academicAffairs.grade.policy.view", "查看有效成绩策略", "view"),
        ("academicAffairs.grade.policy.manage", "管理有效成绩策略", "manage"),
    )
    if "t_permission" in tables:
        for code, name, action in permission_codes:
            bind.execute(sa.text(
                "INSERT INTO t_permission (permission_code, permission_name, module_code, action, created_at) "
                "SELECT :code, :name, :module, :action, NOW() "
                "WHERE NOT EXISTS (SELECT 1 FROM t_permission WHERE permission_code=:code)"
            ), {"code": code, "name": name, "module": code.rsplit(".", 1)[0], "action": action})
    if {"t_role", "t_role_permission", "t_permission"}.issubset(tables):
        grants = {
            "SCHOOL_ADMIN": {code for code, _name, _action in permission_codes},
            "ACADEMIC_ADMIN": {code for code, _name, _action in permission_codes},
            "COLLEGE_ADMIN": {permission_codes[0][0], permission_codes[1][0]},
            "COLLEGE_SA": {permission_codes[0][0], permission_codes[1][0]},
        }
        for role_code, codes in grants.items():
            for code in codes:
                bind.execute(sa.text(
                    "INSERT INTO t_role_permission "
                    "(tenant_id, role_id, permission_id, status, created_at, updated_at, is_deleted, version) "
                    "SELECT r.tenant_id, r.id, p.id, 'ACTIVE', NOW(), NOW(), 0, 0 "
                    "FROM t_role r JOIN t_permission p ON p.permission_code=:permission_code "
                    "WHERE r.role_code=:role_code AND r.is_deleted=0 "
                    "AND NOT EXISTS (SELECT 1 FROM t_role_permission rp "
                    "WHERE rp.tenant_id=r.tenant_id AND rp.role_id=r.id "
                    "AND rp.permission_id=p.id AND rp.is_deleted=0)"
                ), {"role_code": role_code, "permission_code": code})

    if "t_acad_student" in tables:
        student_cols = {c["name"]: c for c in inspect(bind).get_columns("t_acad_student")}
        required_col = student_cols.get("required_credits")
        if required_col and not required_col.get("nullable", True):
            op.alter_column(
                "t_acad_student", "required_credits",
                existing_type=sa.Numeric(6, 1), nullable=True,
                existing_nullable=False, existing_server_default=None,
            )

    grade_cols = {c["name"] for c in inspect(bind).get_columns("t_acad_grade")}
    for name, column in (
        ("effective_policy_code", sa.Column("effective_policy_code", sa.String(80))),
        ("effective_policy_version", sa.Column("effective_policy_version", sa.Integer())),
        ("effective_attempt_strategy", sa.Column("effective_attempt_strategy", sa.String(40))),
        ("pass_line_snapshot", sa.Column("pass_line_snapshot", sa.Integer())),
    ):
        if name not in grade_cols:
            op.add_column("t_acad_grade", column)


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    permission_codes = [
        "academicAffairs.stats.snapshot.view",
        "academicAffairs.stats.snapshot.create",
        "academicAffairs.stats.snapshot.manage",
        "academicAffairs.grade.policy.view",
        "academicAffairs.grade.policy.manage",
    ]
    tables = set(insp.get_table_names())
    if {"t_role_permission", "t_permission"}.issubset(tables):
        bind.execute(sa.text(
            "DELETE rp FROM t_role_permission rp "
            "JOIN t_permission p ON p.id=rp.permission_id "
            "WHERE p.permission_code IN :codes"
        ).bindparams(sa.bindparam("codes", expanding=True)), {"codes": permission_codes})
        bind.execute(sa.text(
            "DELETE FROM t_permission WHERE permission_code IN :codes"
        ).bindparams(sa.bindparam("codes", expanding=True)), {"codes": permission_codes})
    if "t_acad_grade" in insp.get_table_names():
        cols = {c["name"] for c in inspect(bind).get_columns("t_acad_grade")}
        for name in ("pass_line_snapshot", "effective_attempt_strategy", "effective_policy_version", "effective_policy_code"):
            if name in cols:
                op.drop_column("t_acad_grade", name)
    for table in ("t_aa_grade_correction", "t_aa_effective_grade_policy"):
        if table in inspect(bind).get_table_names():
            op.drop_table(table)

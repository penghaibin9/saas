"""毕业设计核心表基线补建（修复迁移链缺口）。

历史欠账：t_gd_batch / t_gd_student / t_gd_topic / t_gd_proposal / t_gd_final /
t_gd_defense_group / t_gd_audit_trail 七张核心表当年由 metadata.create_all() 直建，
从未进入迁移链（0017/0018/0043/0045 仅对已存在的表 ALTER，表缺失时安全跳过）。
后果：全新 MySQL 库 `alembic upgrade head` 建不出这七张表，新校部署即失败。

本迁移按当前 ORM（app/models/graduation.py @ 本次提交）显式 create_table 冻结列定义，
含 0026/0043/0045 已补的列与复合索引；已存在的表一律跳过（存量库幂等）。
链上早于本迁移的条件迁移在全新库上跳过，由本迁移一次建全。

Downgrade 警告：按 0026 先例对七张表 DROP TABLE IF EXISTS，仅用于全新部署回滚；
存量生产库禁止 downgrade 本迁移（会删除真实业务数据表）。

Revision ID: 0051_gd_core_table_baseline
Revises: 0050_internship_trusted_checkin
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0051_gd_core_table_baseline"
down_revision = "0050_internship_trusted_checkin"
branch_labels = None
depends_on = None

CORE_TABLES = [
    "t_gd_batch", "t_gd_student", "t_gd_topic", "t_gd_proposal",
    "t_gd_final", "t_gd_defense_group", "t_gd_audit_trail",
]


def _common_columns(*, with_version: bool = True) -> list[sa.Column]:
    """PKMixin + TenantMixin + CommonMixin 公共列（与 app/models/base.py 对齐）。

    注意：GraduationProposal / GraduationFinal 在模型里用 `version String(20)`（业务版本号
    v1/v2）覆盖了 CommonMixin 的乐观锁 `version Integer`，这两张表须传 with_version=False
    并各自声明字符串版本列。"""
    cols = [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
    ]
    if with_version:
        cols.append(sa.Column("version", sa.Integer(), nullable=False))
    return cols


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    if "t_gd_batch" not in existing:
        op.create_table(
            "t_gd_batch",
            *_common_columns(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("batch_no", sa.String(100), nullable=False),
            sa.Column("academic_year", sa.String(20), nullable=True),
            sa.Column("grade_year", sa.String(20), nullable=True),
            sa.Column("college_scope", sa.String(200), nullable=True),
            sa.Column("start_date", sa.DateTime(), nullable=True),
            sa.Column("end_date", sa.DateTime(), nullable=True),
            sa.Column("planned_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("stage_config", sa.JSON(), nullable=True),
            sa.Column("rules_config", sa.JSON(), nullable=True),
            sa.Column("previous_status", sa.String(50), nullable=True),
            sa.Column("last_transition_at", sa.DateTime(), nullable=True),
            sa.Column("last_transition_by", sa.String(100), nullable=True),
            sa.Column("transition_reason", sa.String(500), nullable=True),
            sa.Column("archive_status", sa.String(50), nullable=False),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("archived_by", sa.String(100), nullable=True),
            sa.Column("void_reason", sa.String(500), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            sa.UniqueConstraint("tenant_id", "batch_no", name="uk_gd_batch_no"),
        )
        op.create_index("ix_t_gd_batch_tenant_id", "t_gd_batch", ["tenant_id"])

    if "t_gd_student" not in existing:
        op.create_table(
            "t_gd_student",
            *_common_columns(),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("topic_id", sa.BigInteger(), nullable=True),
            sa.Column("student_no", sa.String(50), nullable=True),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("class_id", sa.String(50), nullable=True),
            sa.Column("class_name", sa.String(100), nullable=True),
            sa.Column("topic_title", sa.String(300), nullable=True),
            sa.Column("topic_source", sa.String(100), nullable=True),
            sa.Column("advisor_name", sa.String(100), nullable=True),
            sa.Column("stage", sa.String(50), nullable=False),
            sa.Column("material_summary", sa.String(200), nullable=True),
            sa.Column("plagiarism_rate", sa.String(20), nullable=True),
            sa.Column("risk_level", sa.String(50), nullable=False),
            sa.Column("phone_encrypted", sa.String(500), nullable=True),
            sa.Column("midterm_conclusion", sa.String(100), nullable=True),
            sa.Column("defense_group", sa.String(100), nullable=True),
            sa.Column("defense_group_id", sa.BigInteger(), nullable=True),
            sa.Column("eligibility_status", sa.String(50), nullable=False),
            sa.Column("mentor_id", sa.BigInteger(), nullable=True),
            sa.Column("student_group", sa.String(100), nullable=True),
            sa.Column("grad_qual_status", sa.String(50), nullable=False),
            sa.Column("grad_qual_note", sa.String(500), nullable=True),
            sa.Column("record_status", sa.String(50), nullable=False),
            sa.Column("void_reason", sa.String(500), nullable=True),
        )
        for col in ("tenant_id", "batch_id", "topic_id", "student_no", "student_id",
                    "defense_group_id", "mentor_id"):
            op.create_index(f"ix_t_gd_student_{col}", "t_gd_student", [col])
        op.create_index("ix_gd_student_tenant_stage_active", "t_gd_student",
                        ["tenant_id", "stage", "record_status", "is_deleted"])

    if "t_gd_topic" not in existing:
        op.create_table(
            "t_gd_topic",
            *_common_columns(),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("topic_no", sa.String(50), nullable=True),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("source", sa.String(50), nullable=True),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("advisor_name", sa.String(100), nullable=True),
            sa.Column("college_id", sa.String(50), nullable=True),
            sa.Column("major_id", sa.String(50), nullable=True),
            sa.Column("major_name", sa.String(100), nullable=True),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("difficulty", sa.String(30), nullable=True),
            sa.Column("enterprise_name", sa.String(200), nullable=True),
            sa.Column("requirements", sa.String(2000), nullable=True),
            sa.Column("outcome", sa.String(2000), nullable=True),
            sa.Column("skills", sa.String(500), nullable=True),
            sa.Column("attachments_json", sa.JSON(), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=False),
            sa.Column("selected", sa.Integer(), nullable=False),
            sa.Column("review_status", sa.String(50), nullable=False),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("students_json", sa.JSON(), nullable=True),
            sa.Column("disabled_note", sa.String(300), nullable=True),
            sa.Column("archive_reason", sa.String(500), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
        )
        for col in ("tenant_id", "batch_id", "topic_no"):
            op.create_index(f"ix_t_gd_topic_{col}", "t_gd_topic", [col])

    if "t_gd_proposal" not in existing:
        op.create_table(
            "t_gd_proposal",
            *_common_columns(with_version=False),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
            sa.Column("version", sa.String(20), nullable=True),
            sa.Column("is_resubmit", sa.Boolean(), nullable=False),
            sa.Column("submit_at", sa.DateTime(), nullable=True),
            sa.Column("background", sa.String(2000), nullable=True),
            sa.Column("plan", sa.String(2000), nullable=True),
            sa.Column("outcome", sa.String(2000), nullable=True),
            sa.Column("attachments_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("reviewer", sa.String(100), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("review_time", sa.DateTime(), nullable=True),
            sa.Column("defense_result", sa.String(20), nullable=True),
            sa.Column("defense_comment", sa.String(500), nullable=True),
            sa.Column("defense_at", sa.DateTime(), nullable=True),
        )
        for col in ("tenant_id", "gd_student_id"):
            op.create_index(f"ix_t_gd_proposal_{col}", "t_gd_proposal", [col])

    if "t_gd_final" not in existing:
        op.create_table(
            "t_gd_final",
            *_common_columns(with_version=False),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
            sa.Column("final_type", sa.String(20), nullable=False),
            sa.Column("version", sa.String(20), nullable=True),
            sa.Column("submit_at", sa.DateTime(), nullable=True),
            sa.Column("plagiarism_rate", sa.String(20), nullable=True),
            sa.Column("plagiarism_status", sa.String(50), nullable=True),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("reviewer", sa.String(100), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("review_time", sa.DateTime(), nullable=True),
            sa.Column("attachments_json", sa.JSON(), nullable=True),
        )
        for col in ("tenant_id", "gd_student_id"):
            op.create_index(f"ix_t_gd_final_{col}", "t_gd_final", [col])
        op.create_index("ix_gd_final_tenant_student_status", "t_gd_final",
                        ["tenant_id", "gd_student_id", "status", "is_deleted"])

    if "t_gd_defense_group" not in existing:
        op.create_table(
            "t_gd_defense_group",
            *_common_columns(),
            sa.Column("group_name", sa.String(50), nullable=False),
            sa.Column("defense_date", sa.String(50), nullable=True),
            sa.Column("location", sa.String(100), nullable=True),
            sa.Column("chair", sa.String(100), nullable=True),
            sa.Column("members_json", sa.JSON(), nullable=True),
            sa.Column("secretary", sa.String(100), nullable=True),
            sa.Column("student_count", sa.Integer(), nullable=False),
            sa.Column("conflict", sa.String(300), nullable=True),
            sa.Column("published", sa.Boolean(), nullable=False),
        )
        op.create_index("ix_t_gd_defense_group_tenant_id", "t_gd_defense_group", ["tenant_id"])

    if "t_gd_audit_trail" not in existing:
        # 审计链 append-only：无 updated_at/updated_by/is_deleted/version
        op.create_table(
            "t_gd_audit_trail",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("biz_type", sa.String(50), nullable=False),
            sa.Column("biz_id", sa.String(50), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("operator", sa.String(100), nullable=True),
            sa.Column("role_name", sa.String(100), nullable=True),
            sa.Column("detail", sa.String(1000), nullable=True),
            sa.Column("before_val", sa.String(200), nullable=True),
            sa.Column("after_val", sa.String(200), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("request_id", sa.String(64), nullable=True),
            sa.Column("request_path", sa.String(500), nullable=True),
            sa.Column("client_ip", sa.String(64), nullable=True),
        )
        op.create_index("ix_t_gd_audit_trail_tenant_id", "t_gd_audit_trail", ["tenant_id"])
        op.create_index("ix_gd_audit_request_id", "t_gd_audit_trail", ["tenant_id", "request_id"])


def downgrade() -> None:
    # 仅供全新部署回滚；存量库禁 downgrade（见文件头警告）
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    for t in reversed(CORE_TABLES):
        if t in existing:
            op.execute(f"DROP TABLE IF EXISTS `{t}`")

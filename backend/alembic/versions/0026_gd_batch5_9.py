"""毕业设计中心 Batch 2-9 新增表与列纳入 Alembic 迁移链。

新表：t_gd_template（模板中心）、t_gd_mentor_eval（导师评价）、t_gd_peer_review（成果互查）、
      t_gd_defense_expert（答辩专家库）、t_gd_grade_appeal（成绩更正申诉）。
新列：t_gd_proposal.defense_result/defense_comment/defense_at（开题答辩）、t_gd_student.mentor_id（毕设导师）。

幂等：inspect 已存在的表/列则跳过（dev 库此前经 create_all + inspector 同步已建，本迁移仅补记迁移链）。
"""
from alembic import op
from sqlalchemy import inspect

revision = "0026_gd_batch5_9"
down_revision = "0025_internship_match"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "t_gd_template", "t_gd_mentor_eval", "t_gd_peer_review",
    "t_gd_defense_expert", "t_gd_grade_appeal",
]
NEW_COLS = [
    ("t_gd_proposal", "defense_result", "VARCHAR(20) NULL"),
    ("t_gd_proposal", "defense_comment", "VARCHAR(500) NULL"),
    ("t_gd_proposal", "defense_at", "DATETIME NULL"),
    ("t_gd_student", "mentor_id", "BIGINT NULL"),
]


def upgrade() -> None:
    from app.models import Base  # 复用模型定义建表，保持与 ORM 同步
    bind = op.get_bind()
    insp = inspect(bind)
    existing = set(insp.get_table_names())
    for t in NEW_TABLES:
        if t not in existing and t in Base.metadata.tables:
            Base.metadata.tables[t].create(bind, checkfirst=True)
    existing = set(inspect(bind).get_table_names())
    for tbl, col, typ in NEW_COLS:
        if tbl in existing:
            cols = {c["name"] for c in inspect(bind).get_columns(tbl)}
            if col not in cols:
                op.execute(f"ALTER TABLE `{tbl}` ADD COLUMN `{col}` {typ}")


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = set(insp.get_table_names())
    for tbl, col, _typ in NEW_COLS:
        if tbl in existing and col in {c["name"] for c in inspect(bind).get_columns(tbl)}:
            op.execute(f"ALTER TABLE `{tbl}` DROP COLUMN `{col}`")
    for t in reversed(NEW_TABLES):
        if t in existing:
            op.execute(f"DROP TABLE IF EXISTS `{t}`")

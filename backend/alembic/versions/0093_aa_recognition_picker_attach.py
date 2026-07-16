"""成绩认定增强:目标课程外键 + 佐证附件(对标正方"选择校内课程 + *附件")。

- t_aa_grade_recognition.target_course_id      → t_aa_course(课程选择器,替代手填)
- t_aa_grade_recognition.attachment_file_ids   佐证附件 file_id 列表 JSON(→ t_file_object)

均可空,历史数据零影响(既有记录 target 仍靠 target_course_name 文本)。
回滚 drop 两列;幂等 inspect 判列。

Revision ID: 0093_aa_recognition_picker_attach
Revises: 0092_aa_level_exam
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0093_aa_recognition_picker_attach"
down_revision = "0092_aa_level_exam"
branch_labels = None
depends_on = None

TABLE = "t_aa_grade_recognition"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    if cols and "target_course_id" not in cols:
        op.add_column(TABLE, sa.Column("target_course_id", sa.BigInteger(), nullable=True,
                                       comment="→ t_aa_course 目标校内课程"))
        op.create_index("ix_aa_recog_target_course", TABLE, ["target_course_id"])
    if cols and "attachment_file_ids" not in cols:
        op.add_column(TABLE, sa.Column("attachment_file_ids", sa.String(500), nullable=True,
                                       comment="佐证附件 file_id 列表 JSON"))


def downgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    if "attachment_file_ids" in cols:
        op.drop_column(TABLE, "attachment_file_ids")
    if "target_course_id" in cols:
        op.drop_index("ix_aa_recog_target_course", TABLE)
        op.drop_column(TABLE, "target_course_id")

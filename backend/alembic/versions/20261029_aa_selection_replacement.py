"""取消课程与补选成功记录一一关联；历史记录保持空值，不推算回填。"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_aa_sel_replacement"
down_revision = "20261005_aa_task_source_handoff"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("t_aa_selection_record", sa.Column(
        "replacement_record_id", sa.BigInteger(), nullable=True,
        comment="取消课程对应的补选记录；成功后保留，不重复授予补选资格",
    ))
    op.create_unique_constraint("uk_aa_selection_replacement", "t_aa_selection_record", ["tenant_id", "replacement_record_id"])


def downgrade():
    raise RuntimeError("补选关联属于业务历史，请保留字段并采用兼容代码回退，不删除已形成的关联。")

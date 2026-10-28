"""Keep every historical binding while enforcing one active account per student."""
from alembic import op
import sqlalchemy as sa

revision='ix0036'
down_revision='ix0035'
branch_labels=None
depends_on=None


def upgrade():
    for key,source in [('active_student_id','student_id'),('active_user_id','user_id')]:
        op.add_column('t_student_account_link',sa.Column(key,sa.BigInteger(),sa.Computed(
            f"CASE WHEN link_status = 'ACTIVE' AND is_deleted = 0 THEN {source} ELSE NULL END",persisted=True),nullable=True))
    op.create_unique_constraint('uk_sal_tenant_active_student','t_student_account_link',['tenant_id','active_student_id'])
    op.create_unique_constraint('uk_sal_tenant_active_user','t_student_account_link',['tenant_id','active_user_id'])
    op.drop_constraint('uk_sal_tenant_student_status','t_student_account_link',type_='unique')
    op.drop_constraint('uk_sal_tenant_user_status','t_student_account_link',type_='unique')


def downgrade():
    raise RuntimeError('保留历次绑定纠正记录；回退应用时保留兼容字段与有效绑定唯一约束')

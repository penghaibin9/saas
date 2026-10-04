"""Add minimal encrypted internship employment declaration and immutable revision facts."""
from alembic import op
import sqlalchemy as sa

revision = 'ix0027'
down_revision = 'ix0026'
branch_labels = None
depends_on = None

def _identity():
    return [sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by', sa.BigInteger(), nullable=True)]

def upgrade():
    op.create_table('t_internship_employment_registration', *_identity(),
        sa.Column('internship_id', sa.BigInteger(), nullable=False),
        sa.Column('student_id', sa.BigInteger(), nullable=False),
        sa.Column('batch_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='SUBMITTED'),
        sa.Column('current_submission_id', sa.BigInteger(), nullable=True),
        sa.Column('revision_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('tenant_id', 'internship_id', name='uk_ix_employment_record'))
    op.create_index('ix_ix_employment_batch_status', 't_internship_employment_registration', ['tenant_id','batch_id','status','is_deleted'])
    op.create_index('ix_ix_employment_student', 't_internship_employment_registration', ['tenant_id','student_id','is_deleted'])
    op.create_table('t_internship_employment_submission', *_identity(),
        sa.Column('registration_id', sa.BigInteger(), nullable=False),
        sa.Column('revision_no', sa.Integer(), nullable=False),
        sa.Column('registration_mode', sa.String(30), nullable=False),
        sa.Column('source_company_id', sa.BigInteger(), nullable=True),
        sa.Column('details_encrypted', sa.Text(), nullable=False),
        sa.Column('attachments_json', sa.JSON(), nullable=False),
        sa.Column('correction_reason_encrypted', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('submitted_by', sa.BigInteger(), nullable=False),
        sa.UniqueConstraint('tenant_id','registration_id','revision_no',name='uk_ix_employment_submission'))
    op.create_index('ix_ix_employment_submission_lookup','t_internship_employment_submission',['tenant_id','registration_id','revision_no'])
    op.create_table('t_internship_employment_review', *_identity(),
        sa.Column('registration_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('comment_encrypted', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=False),
        sa.Column('reviewer_name', sa.String(100), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id','submission_id',name='uk_ix_employment_review'))
    op.create_index('ix_ix_employment_review_lookup','t_internship_employment_review',['tenant_id','registration_id','submission_id'])
    for table in ('t_internship_employment_registration','t_internship_employment_submission','t_internship_employment_review'):
        op.create_index('ix_'+table+'_tenant_id',table,['tenant_id'])

def downgrade():
    tables = ('t_internship_employment_review','t_internship_employment_submission','t_internship_employment_registration')
    for table in tables:
        if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM '+table)).scalar():
            raise RuntimeError('Employment declaration facts must be retained; destructive downgrade is forbidden')
    for table in tables:
        op.drop_table(table)

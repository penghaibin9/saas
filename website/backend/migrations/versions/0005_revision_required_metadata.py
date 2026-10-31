"""Enforce the revision responsibility contract at the database boundary."""
from alembic import op
import sqlalchemy as sa
revision='0005_revision_required_metadata'
down_revision='0004_editorial_workflow'
branch_labels=depends_on=None

def upgrade():
    op.execute("UPDATE t_website_news_revision SET rights_evidence='' WHERE rights_evidence IS NULL")
    op.execute("UPDATE t_website_news_revision SET related_products=JSON_ARRAY() WHERE related_products IS NULL")
    op.alter_column('t_website_news_revision','rights_evidence',existing_type=sa.Text(),nullable=False)
    op.alter_column('t_website_news_revision','related_products',existing_type=sa.JSON(),nullable=False)

def downgrade():
    raise RuntimeError('保留新闻版本资料约束，不自动回退')

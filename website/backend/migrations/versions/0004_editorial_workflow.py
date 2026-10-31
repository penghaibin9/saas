"""Independent editorial responsibility and private revisions; preserve old public rows."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT
revision = '0004_editorial_workflow'
down_revision = '0003_public_rate'
branch_labels = depends_on = None

def editorial_columns():
    return [sa.Column(name, sa.String(length), nullable=False, server_default=default)
            for name, length, default in [('source_type',24,'unverified'),('author_name',120,''),
            ('editor_name',120,''),('rights_basis',1000,''),('rights_scope',1000,''),
            ('editorial_state',24,'DRAFT'),('review_reason',1000,'')]] + [
        sa.Column('rights_evidence',sa.Text(),nullable=True),
        sa.Column('rights_valid_until',sa.DateTime()),
        sa.Column('related_products',sa.JSON(),nullable=True),
        sa.Column('approved_digest',sa.String(64))]

def upgrade():
    for column in editorial_columns(): op.add_column('t_website_news_article',column)
    op.execute("UPDATE t_website_news_article SET rights_evidence='', related_products=JSON_ARRAY(), editorial_state='LEGACY'")
    op.alter_column('t_website_news_article','rights_evidence',existing_type=sa.Text(),nullable=False)
    op.alter_column('t_website_news_article','related_products',existing_type=sa.JSON(),nullable=False)
    op.create_table('t_website_news_revision',
        sa.Column('id',sa.String(32),primary_key=True),
        sa.Column('article_id',sa.String(32),sa.ForeignKey('t_website_news_article.id'),nullable=False),
        sa.Column('number',sa.Integer(),nullable=False),sa.Column('base_digest',sa.String(64),nullable=False),
        sa.Column('title',sa.String(240),nullable=False),sa.Column('summary',sa.String(600),nullable=False),
        sa.Column('body',MEDIUMTEXT(),nullable=False),sa.Column('category',sa.String(40),nullable=False),
        sa.Column('sources',sa.JSON(),nullable=False),sa.Column('media_map',sa.JSON(),nullable=False),
        sa.Column('cover_id',sa.String(64)),sa.Column('ai_assisted',sa.Boolean(),nullable=False),
        sa.Column('content_kind',sa.String(24),nullable=False),sa.Column('state',sa.String(24),nullable=False),
        sa.Column('issue',sa.String(1000),nullable=False),sa.Column('scheduled_at',sa.DateTime()),
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.Column('applied_at',sa.DateTime()),*editorial_columns(),
        sa.UniqueConstraint('article_id','number',name='uq_news_revision_number'),
        mysql_engine='InnoDB',mysql_charset='utf8mb4')
    op.create_index('ix_news_revision_due','t_website_news_revision',['editorial_state','scheduled_at'])

def downgrade():
    raise RuntimeError('保留新闻来源及修订历史，不自动执行破坏性回退')

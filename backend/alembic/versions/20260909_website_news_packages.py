"""Platform-owned news package ingestion and durable publication queue.
Frozen DDL; never imports live models. Downgrade refuses to discard real content.
"""
from alembic import op
import sqlalchemy as sa
revision = "20260909_website_news_packages"
down_revision = "20260906_fee_reduction_four_end"
branch_labels = None
depends_on = None
DDL = ['CREATE TABLE t_website_news_audit (\n\tid VARCHAR(32) NOT NULL, \n\tevent_key VARCHAR(100) NOT NULL, \n\tpackage_id VARCHAR(32) NOT NULL, \n\tarticle_id VARCHAR(32), \n\tactor VARCHAR(64) NOT NULL, \n\taction VARCHAR(40) NOT NULL, \n\tdetail JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (event_key)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE INDEX ix_news_audit_package ON t_website_news_audit (package_id, created_at)', 'CREATE TABLE t_website_news_dispatch (\n\tid INTEGER NOT NULL AUTO_INCREMENT, \n\tnext_slot DATETIME, \n\theartbeat_at DATETIME, \n\tlast_error VARCHAR(600) NOT NULL, \n\tPRIMARY KEY (id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE TABLE t_website_news_media (\n\tid VARCHAR(64) NOT NULL, \n\tcontent LONGBLOB NOT NULL, \n\tmime VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE TABLE t_website_news_package (\n\tid VARCHAR(32) NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\ttitle VARCHAR(200) NOT NULL, \n\tfilename VARCHAR(200) NOT NULL, \n\tstate VARCHAR(24) NOT NULL, \n\tversion INTEGER NOT NULL, \n\treview_digest VARCHAR(64) NOT NULL, \n\tapproval_signature VARCHAR(64), \n\timported_by VARCHAR(64) NOT NULL, \n\treviewed_by VARCHAR(64), \n\tcreated_at DATETIME NOT NULL, \n\treviewed_at DATETIME, \n\tPRIMARY KEY (id), \n\tUNIQUE (sha256)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE INDEX ix_news_package_created ON t_website_news_package (created_at, id)', 'CREATE TABLE t_website_news_article (\n\tid VARCHAR(32) NOT NULL, \n\tpackage_id VARCHAR(32) NOT NULL, \n\tordinal INTEGER NOT NULL, \n\ttitle VARCHAR(240) NOT NULL, \n\tsummary VARCHAR(600) NOT NULL, \n\tbody MEDIUMTEXT NOT NULL, \n\tcategory VARCHAR(40) NOT NULL, \n\tslug VARCHAR(96) NOT NULL, \n\tstate VARCHAR(24) NOT NULL, \n\tissue VARCHAR(1000) NOT NULL, \n\tdedupe_key VARCHAR(64), \n\tsources JSON NOT NULL, \n\tmedia_map JSON NOT NULL, \n\tcover_id VARCHAR(64), \n\tai_assisted BOOL NOT NULL, \n\tcontent_kind VARCHAR(24) NOT NULL, \n\tscheduled_at DATETIME, \n\tpublished_at DATETIME, \n\tupdated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_news_package_ordinal UNIQUE (package_id, ordinal), \n\tFOREIGN KEY(package_id) REFERENCES t_website_news_package (id), \n\tUNIQUE (slug), \n\tUNIQUE (dedupe_key)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE INDEX ix_news_public ON t_website_news_article (state, category, published_at, id)', 'CREATE INDEX ix_news_due ON t_website_news_article (state, scheduled_at, id)', 'CREATE TABLE t_website_news_media_link (\n\tarticle_id VARCHAR(32) NOT NULL, \n\tmedia_id VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (article_id, media_id), \n\tFOREIGN KEY(article_id) REFERENCES t_website_news_article (id), \n\tFOREIGN KEY(media_id) REFERENCES t_website_news_media (id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', 'CREATE INDEX ix_news_media_usage ON t_website_news_media_link (media_id, article_id)']
TABLES = ['t_website_news_audit', 't_website_news_dispatch', 't_website_news_media', 't_website_news_package', 't_website_news_article', 't_website_news_media_link']

def upgrade():
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("Website news schema requires MySQL")
    for statement in DDL:
        op.execute(sa.text(statement))
    op.execute(sa.text("INSERT INTO t_website_news_dispatch (id, last_error) VALUES (1, '')"))

def downgrade():
    connection=op.get_bind()
    for table in TABLES:
        if table != "t_website_news_dispatch" and connection.scalar(sa.text("SELECT COUNT(*) FROM " + table)):
            raise RuntimeError("News data exists; rollback code without dropping content tables")
    for table in reversed(TABLES):
        op.drop_table(table)

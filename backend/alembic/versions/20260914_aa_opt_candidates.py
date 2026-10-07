"""Isolated candidate snapshot/job tables; parent pinned to verified source archive.
Do not apply to a newer workspace without Alembic head reconciliation.
"""
from alembic import op

revision = "20260914_aa_opt_candidates"
down_revision = "20260914_aa_grade_analysis_perf"
branch_labels = None
depends_on = None

DDL = ('\nCREATE TABLE t_aa_optimizer_snapshot (\n\tid BIGINT NOT NULL AUTO_INCREMENT, \n\ttenant_id BIGINT NOT NULL, \n\tterm_id BIGINT NOT NULL, \n\tbatch_id BIGINT NOT NULL, \n\tinput_hash VARCHAR(64) NOT NULL, \n\tsource_revision VARCHAR(128) NOT NULL, \n\tpayload_zlib MEDIUMBLOB NOT NULL, \n\tpayload_bytes INTEGER NOT NULL, \n\tcreated_at DATETIME(6) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uk_aa_opt_snapshot_hash UNIQUE (tenant_id, input_hash), \n\tCONSTRAINT uk_aa_opt_snapshot_tenant_id UNIQUE (tenant_id, id)\n)ENGINE=InnoDB CHARSET=utf8mb4\n\n', '\nCREATE TABLE t_aa_optimizer_job (\n\tid BIGINT NOT NULL AUTO_INCREMENT, \n\ttenant_id BIGINT NOT NULL, \n\tterm_id BIGINT NOT NULL, \n\tbatch_id BIGINT NOT NULL, \n\tsnapshot_id BIGINT NOT NULL, \n\trequested_by VARCHAR(128) NOT NULL, \n\trequested_reason VARCHAR(500) NOT NULL, \n\tactor_context_json JSON NOT NULL, \n\tidempotency_key VARCHAR(64) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\toptions_json JSON NOT NULL, \n\tstate VARCHAR(32) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tlease_token VARCHAR(36), \n\tlease_until DATETIME(6), \n\tattempts INTEGER NOT NULL, \n\tcancel_requested BOOL NOT NULL, \n\tresult_json JSON, \n\tlast_error VARCHAR(100), \n\tcreated_at DATETIME(6) NOT NULL, \n\tupdated_at DATETIME(6) NOT NULL, \n\tcompleted_at DATETIME(6), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uk_aa_opt_job_idempotency UNIQUE (tenant_id, batch_id, idempotency_key), \n\tCONSTRAINT fk_aa_opt_job_snapshot_tenant FOREIGN KEY(tenant_id, snapshot_id) REFERENCES t_aa_optimizer_snapshot (tenant_id, id) ON DELETE RESTRICT\n)ENGINE=InnoDB CHARSET=utf8mb4\n\n', 'CREATE INDEX ix_aa_opt_job_due ON t_aa_optimizer_job (tenant_id, state, lease_until, id)')

def upgrade():
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL")
    for statement in DDL:
        op.execute(statement)

def downgrade():
    raise RuntimeError("Candidate evidence is retained; use an approved backup/restore procedure instead of destructive downgrade")

"""Disposable migrated MySQL exit-review scope and non-mutation acceptance."""
from __future__ import annotations

import pytest
from sqlalchemy import event, select

from app.core.exceptions import AppException
from tests.test_module_commerce_m12_runtime import _seed_tenant

TID = 1000000000000006801


@pytest.fixture
def review_job(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleOffboardingJob, TenantModuleState
    _seed_tenant(TID)
    _seed_tenant(TID + 1)
    with get_sessionmaker()() as db:
        assert db.get_bind().dialect.name == 'mysql'
        state = TenantModuleState(tenant_id=TID, module_key='internship', generation=1,
                                  data_state='FROZEN', lifecycle_version=2)
        job = TenantModuleOffboardingJob(tenant_id=TID, module_key='internship', module_generation=1,
            expected_lifecycle_version=1, state='FROZEN', reason='隔离测试库退出检查任务',
            retention_days=30, retention_policy_version='TEST_ONLY', scope_hash='d'*64, version=0)
        db.add_all([state, job]); db.commit()
        return int(job.id)


def test_exit_review_mysql_reads_only_and_keeps_fixed_prohibitions(review_job):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import TenantModuleOffboardingJob, TenantModuleState
    from app.services.module_commerce_m6_preflight import preview_module_purge
    engine = get_engine(); statements = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split(None, 1)[0].upper())
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        result = preview_module_purge(review_job, tenant_id=TID, expected_generation=1, expected_version=0)
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert statements and set(statements).issubset({'SELECT', 'SHOW'})
    assert result['tenantId'] == str(TID) and result['jobVersion'] == 0
    assert result['dryRunOnly'] is True and result['deletionAuthorized'] is False
    assert result['canExecutePhysicalPurge'] is False and result['destructiveStatements'] == []
    assert 'MODULE_PURGE_EXECUTION_DISABLED' in result['blockerCodes']
    assert 'VERIFIED_EXPORT_EVIDENCE_MISSING' in result['blockerCodes']
    with get_sessionmaker()() as db:
        job = db.get(TenantModuleOffboardingJob, review_job)
        state = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == TID, TenantModuleState.module_key == 'internship')).one()
        assert (job.state, job.version, job.export_file_id) == ('FROZEN', 0, None)
        assert (state.data_state, state.generation, state.lifecycle_version) == ('FROZEN', 1, 2)


def test_exit_review_mysql_wrong_school_cannot_read_foreign_task(review_job):
    from app.services.module_commerce_m6_preflight import preview_module_purge
    with pytest.raises(AppException) as caught:
        preview_module_purge(review_job, tenant_id=TID + 1, expected_generation=1, expected_version=0)
    assert caught.value.http_status == 404


@pytest.mark.parametrize('generation,version', [(2, 0), (1, 1)])
def test_exit_review_mysql_old_context_cannot_be_reused(review_job, generation, version):
    from app.services.module_commerce_m6_preflight import preview_module_purge
    with pytest.raises(AppException) as caught:
        preview_module_purge(review_job, tenant_id=TID, expected_generation=generation, expected_version=version)
    assert caught.value.http_status == 409


def test_exit_review_mysql_recreated_module_remains_blocked(review_job):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState
    from app.services.module_commerce_m6_preflight import preview_module_purge
    with get_sessionmaker()() as db:
        state = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == TID, TenantModuleState.module_key == 'internship')).one()
        state.generation = 2; db.commit()
    report = preview_module_purge(review_job, tenant_id=TID, expected_generation=1, expected_version=0)
    assert 'MODULE_GENERATION_CONFLICT' in report['blockerCodes']
    assert report['deletionAuthorized'] is False

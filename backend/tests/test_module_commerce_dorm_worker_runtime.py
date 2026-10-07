"""Real MySQL housing transactions behind M4 durable-generation fences.

The established dorm fixture supplies legacy school authorization; these cases test
lifecycle fencing, not payment activation. No entitlement or final-commit guard is
mocked. Only login identity resolution is isolated by the existing dorm fixture.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from tests.test_dorm_allocation_publish_job import prepare
from tests.test_dorm_d3_allocation import BASE, TID


def _clear_context():
    from app.core.context import set_request_meta, set_tenant, set_trace_id
    set_request_meta(None)
    set_trace_id("-")
    set_tenant(None)


def _set_lifecycle(*, generation=1, data_state="AVAILABLE"):
    _clear_context()
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState
    with get_sessionmaker()() as db:
        row = db.scalar(select(TenantModuleState).where(
            TenantModuleState.tenant_id == TID,
            TenantModuleState.module_key == "studentAffairs",
        ).with_for_update())
        if row is None:
            row = TenantModuleState(tenant_id=TID, module_key="studentAffairs",
                                    generation=generation, data_state=data_state,
                                    lifecycle_version=1)
            db.add(row)
        else:
            row.generation = generation
            row.data_state = data_state
            row.lifecycle_version += 1
        db.commit()


def _enqueue(client, headers, batch, version):
    response = client.post(f"{BASE}/{batch}/publish-jobs", headers=headers,
                           json={"version": version})
    assert response.status_code == 200, response.text
    return response.json()["data"]["jobId"]


def _assert_no_housing_facts(batch):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormStay
    with get_sessionmaker()() as db:
        assert db.get(DormAllocationBatch, int(batch)).status == "DRAFT"
        assert db.scalar(select(func.count()).select_from(DormStay).where(
            DormStay.tenant_id == TID,
        )) == 0


def test_m4_dorm_job_persists_generation_and_success_with_housing(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormStay
    from app.models.affairs_operations import AffairsBatchJob
    from app.services import dorm_allocation_publish_job as jobs
    from app.services.module_commerce_access_guard import _active_fences
    _, headers, batch, version, _ = prepare(client, monkeypatch)
    _set_lifecycle()
    job_id = _enqueue(client, headers, batch, version)
    assert _enqueue(client, headers, batch, version) == job_id
    with get_sessionmaker()() as db:
        job = db.get(AffairsBatchJob, int(job_id))
        assert job.request_json["moduleGeneration"] == 1
        assert job.idempotency_key.endswith(":module:1")
    _clear_context()
    assert jobs.run_one()["status"] == "SUCCESS"
    assert _active_fences() == []
    with get_sessionmaker()() as db:
        assert db.get(AffairsBatchJob, int(job_id)).status == "SUCCESS"
        assert db.get(DormAllocationBatch, int(batch)).status == "PUBLISHED"
        assert db.scalar(select(func.count()).select_from(DormStay).where(
            DormStay.tenant_id == TID,
        )) == 3


@pytest.mark.parametrize("change", ["generation", "frozen", "missing", "zero"])
def test_m4_dorm_stale_or_unbound_job_cannot_publish(client, db_mode, monkeypatch, change):
    from app.db.session import get_sessionmaker
    from app.models.affairs_operations import AffairsBatchJob
    from app.services import dorm_allocation_publish_job as jobs
    from app.services.module_commerce_access_guard import _active_fences
    _, headers, batch, version, _ = prepare(client, monkeypatch)
    _set_lifecycle()
    job_id = _enqueue(client, headers, batch, version)
    if change == "generation":
        _set_lifecycle(generation=2)
    elif change == "frozen":
        _set_lifecycle(data_state="FROZEN")
    else:
        # Simulate a pre-M4 durable payload; never replace it at execution time.
        with get_sessionmaker()() as db:
            job = db.get(AffairsBatchJob, int(job_id))
            payload = dict(job.request_json)
            payload.pop("moduleGeneration")
            if change == "zero":
                payload["moduleGeneration"] = 0
            job.request_json = payload
            db.commit()
    _clear_context()
    result = jobs.run_one()
    assert result["status"] == "FAILED", result
    assert _active_fences() == []
    _assert_no_housing_facts(batch)
    with get_sessionmaker()() as db:
        job = db.get(AffairsBatchJob, int(job_id))
        assert job.status == "FAILED" and job.success_count == 0
    assert jobs.run_one()["processed"] is False
    if change == "generation":
        # A fresh human enqueue can create a new task at the reviewed generation;
        # the old idempotency key cannot trap the plan in a stale failed job.
        new_job_id = _enqueue(client, headers, batch, version)
        assert new_job_id != job_id
        _clear_context()
        assert jobs.run_one()["status"] == "SUCCESS"


def test_m4_dorm_freeze_during_publication_rolls_back_actual_housing(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem
    from app.services import dorm_allocation_publish_job as jobs
    from app.services.module_commerce_access_guard import _active_fences
    _, headers, batch, version, _ = prepare(client, monkeypatch)
    _set_lifecycle()
    job_id = _enqueue(client, headers, batch, version)
    original = jobs.allocation.publish_in_transaction

    def freeze_after_housing_write(db, *args, **kwargs):
        result = original(db, *args, **kwargs)
        db.flush()
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(_set_lifecycle, data_state="FROZEN").result(timeout=15)
        return result

    monkeypatch.setattr(jobs.allocation, "publish_in_transaction", freeze_after_housing_write)
    _clear_context()
    result = jobs.run_one()
    assert result["status"] == "FAILED", result
    assert _active_fences() == []
    _assert_no_housing_facts(batch)
    with get_sessionmaker()() as db:
        job = db.get(AffairsBatchJob, int(job_id))
        item = db.scalar(select(AffairsBatchJobItem).where(
            AffairsBatchJobItem.tenant_id == TID,
            AffairsBatchJobItem.batch_job_id == int(job_id),
        ))
        assert job.status == "FAILED" and job.success_count == 0
        assert item.status == "FAILED" and item.error_code == "NO_PERMISSION"

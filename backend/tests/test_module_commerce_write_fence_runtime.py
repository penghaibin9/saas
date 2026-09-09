from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException

BASE = 1000000000000021000


def _clear_request_context():
    from app.core.context import set_request_meta, set_tenant, set_trace_id
    set_trace_id("-")
    set_request_meta(None)
    set_tenant(None)


@pytest.fixture(autouse=True)
def _isolate_http_write_fence_context():
    """Each test is one synthetic HTTP request boundary.

    Production requests get a fresh trace/request context from middleware. These direct
    service tests bypass that middleware, so clear the commercial ContextVar before and
    after every case; otherwise a successful previous request can fence db_mode setup for
    the next test and manufacture cross-test DATA_CONFLICT/lock timeouts.
    """
    from app.services import module_commerce_access_guard as guard

    guard._write_fence_ctx.set(None)
    _clear_request_context()
    yield
    guard._write_fence_ctx.set(None)
    _clear_request_context()


def _seed(tid: int):
    _clear_request_context()
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant
    db = get_sessionmaker()()
    try:
        db.add(Tenant(id=tid, tenant_code=f"m4-fence-{tid}", school_name=f"M4Fence-{tid}",
                      deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
        db.add(PlatformConfig(
            tenant_id=tid, config_type="TENANT_META", config_key="-",
            config_json={"status": "trial", "packageCode": "trial", "environment": "test"},
            enabled=True, status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()


def _sku(code: str):
    from app.services import commercial_catalog_service as catalog
    payload = {
        "skuCode": code, "revision": 1, "name": code, "productType": "MODULE",
        "moduleKey": "internship", "features": {"internship": True}, "quotas": {},
        "pricePolicy": {"unitPrice": "100.00", "currency": "CNY", "taxTreatment": "UNSPECIFIED"},
        "lifecyclePolicyVersion": "M4-FENCE-1",
    }
    published = catalog.publish_sku(payload, reason="M4最终提交栅栏测试")
    return catalog.get_sku_snapshot(published["skuCode"], published["revision"])


def _pay(tid: int, code: str):
    from app.services import commercial_order_item_service as orders, platform_service
    snapshot = _sku(code)
    sku = snapshot.as_dict()
    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    end = start + timedelta(days=30)
    created = orders.create_itemized_order({
        "tenantId": str(tid), "currency": "CNY", "totalAmount": "100.00", "orderType": "NEW",
        "remark": "M4最终提交栅栏测试",
        "items": [{
            "lineNo": 1, "skuCode": sku["skuCode"], "skuRevision": sku["revision"],
            "skuContentHash": snapshot.content_hash, "quantity": 1, "unitPrice": "100.00",
            "discountAmount": "0.00", "netAmount": "100.00",
            "startAt": start.isoformat(), "endAt": end.isoformat(), "requestedGeneration": 1,
        }],
    }, idempotency_key=f"m4-fence-{tid}", actor_id="0")
    paid = platform_service.order_action(
        created["orderNo"], "mark-paid", expected_version=created["version"],
        reason="M4支付激活栅栏测试",
    )
    assert paid["readerVersion"] == "MODULE_V2" and paid["repairTaskRequired"] is False


def _request_context(tid: int, trace: str, method: str = "POST"):
    from app.core.context import set_request_meta, set_tenant, set_trace_id
    set_tenant(tid)
    set_trace_id(trace)
    set_request_meta({"method": method, "path": "/api/v1/internship/batches"})


def _business_session(tid: int, suffix: str):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    db = get_sessionmaker()()
    row = InternshipBatch(
        tenant_id=tid, batch_name=f"M4 fence {suffix}", batch_no=f"M4-FENCE-{tid}-{suffix}",
        planned_count=0, status="DRAFT", remark="final commit fence",
    )
    db.add(row)
    return db, row


def _source_state(tid: int):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState, TenantModuleSubscriptionSource
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == tid,
            TenantModuleSubscriptionSource.module_key == "internship",
            TenantModuleSubscriptionSource.is_deleted.is_(False),
        )).one()
        state = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == tid,
            TenantModuleState.module_key == "internship",
            TenantModuleState.is_deleted.is_(False),
        )).one()
        return int(source.id), int(source.version or 0), int(state.lifecycle_version or 0)
    finally:
        db.close()


def _cancel_source(tid: int):
    from app.core.context import set_tenant, set_trace_id, set_request_meta
    from app.services import module_subscription_service as subscriptions
    set_tenant(tid); set_trace_id(f"cancel-{tid}"); set_request_meta({"method": "POST", "path": "/api/v1/platform/commercial"})
    source_id, version, _ = _source_state(tid)
    subscriptions.cancel_subscription_source_now(
        tid, source_id, expected_version=version, reason="M4测试立即结束模块来源",
    )


def _freeze(tid: int):
    from app.core.context import set_tenant, set_trace_id, set_request_meta
    from app.services import module_commerce_lifecycle_service as lifecycle
    set_tenant(tid); set_trace_id(f"freeze-{tid}"); set_request_meta({"method": "POST", "path": "/api/v1/platform/commercial"})
    _, _, lifecycle_version = _source_state(tid)
    _cancel_source(tid)
    lifecycle.request_module_offboarding(
        {"userId": "0"}, tid, "internship", expected_lifecycle_version=lifecycle_version,
        reason="M4测试冻结岗位实习模块并验证旧事务回滚",
        retention_days=30, retention_policy_version="M4-FENCE-TEST",
    )


def _change_generation(tid: int, generation: int):
    from app.core.context import set_request_meta, set_tenant, set_trace_id
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState
    set_tenant(tid); set_trace_id(f"generation-{tid}"); set_request_meta({"method": "POST", "path": "/internal/test"})
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == tid,
            TenantModuleState.module_key == "internship",
        ).with_for_update()).one()
        row.generation = generation
        row.lifecycle_version = int(row.lifecycle_version or 0) + 1
        db.commit()
    finally:
        db.close()


def _assert_batch_absent(tid: int, batch_no: str):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    db = get_sessionmaker()()
    try:
        assert db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == tid, InternshipBatch.batch_no == batch_no,
        )).first() is None
    finally:
        db.close()


def test_m4_unsafe_http_commit_succeeds_when_generation_source_and_state_are_unchanged(db_mode):
    from app.services import module_access_service
    tid = BASE + 1
    _seed(tid); _pay(tid, "M4-FENCE-OK")
    _request_context(tid, "m4-ok")
    module_access_service.assert_module_access(tid, "internship", write=False)
    db, row = _business_session(tid, "ok")
    try:
        db.commit()
        assert row.id is not None
    finally:
        db.close()


def test_m4_transaction_that_passed_gate_before_freeze_cannot_commit_after_freeze(db_mode):
    from app.services import module_access_service
    tid = BASE + 2
    _seed(tid); _pay(tid, "M4-FENCE-FROZEN")
    _request_context(tid, "m4-frozen")
    module_access_service.assert_module_access(tid, "internship", write=False)
    db, row = _business_session(tid, "frozen")
    batch_no = row.batch_no
    thread = threading.Thread(target=_freeze, args=(tid,))
    thread.start(); thread.join(30); assert not thread.is_alive()
    try:
        with pytest.raises(AppException) as caught:
            db.commit()
        assert caught.value.http_status == 403
        db.rollback()
    finally:
        db.close()
    _assert_batch_absent(tid, batch_no)


def test_m4_transaction_that_passed_gate_cannot_commit_after_generation_changes(db_mode):
    from app.services import module_access_service
    tid = BASE + 3
    _seed(tid); _pay(tid, "M4-FENCE-GENERATION")
    _request_context(tid, "m4-generation")
    module_access_service.assert_module_access(tid, "internship", write=False)
    db, row = _business_session(tid, "generation")
    batch_no = row.batch_no
    thread = threading.Thread(target=_change_generation, args=(tid, 2))
    thread.start(); thread.join(30); assert not thread.is_alive()
    try:
        with pytest.raises(AppException) as caught:
            db.commit()
        assert caught.value.code == "DATA_CONFLICT" and caught.value.http_status == 409
        db.rollback()
    finally:
        db.close()
    _assert_batch_absent(tid, batch_no)


def test_m4_transaction_that_passed_gate_cannot_commit_after_paid_source_is_cancelled(db_mode):
    from app.services import module_access_service
    tid = BASE + 4
    _seed(tid); _pay(tid, "M4-FENCE-SOURCE")
    _request_context(tid, "m4-source")
    module_access_service.assert_module_access(tid, "internship", write=False)
    db, row = _business_session(tid, "source")
    batch_no = row.batch_no
    thread = threading.Thread(target=_cancel_source, args=(tid,))
    thread.start(); thread.join(30); assert not thread.is_alive()
    try:
        with pytest.raises(AppException) as caught:
            db.commit()
        assert caught.value.http_status == 403
        db.rollback()
    finally:
        db.close()
    _assert_batch_absent(tid, batch_no)


def test_m4_get_request_does_not_install_write_commit_fence(db_mode):
    from app.services import module_access_service
    tid = BASE + 5
    _seed(tid); _pay(tid, "M4-FENCE-GET")
    _request_context(tid, "m4-get", method="GET")
    module_access_service.assert_module_access(tid, "internship", write=False)
    from app.services.module_commerce_access_guard import _active_fences
    assert _active_fences() == []


def test_m4_worker_context_rejects_stale_generation_and_resets_after_exit(db_mode):
    from app.services.module_commerce_access_guard import _active_fences, module_write_fence
    tid = BASE + 6
    _seed(tid); _pay(tid, "M4-FENCE-WORKER")
    db, row = _business_session(tid, "worker")
    batch_no = row.batch_no
    with module_write_fence(tid, "internship", 1):
        assert _active_fences()[0]["generation"] == 1
        thread = threading.Thread(target=_change_generation, args=(tid, 2))
        thread.start(); thread.join(30); assert not thread.is_alive()
        try:
            with pytest.raises(AppException) as caught:
                db.commit()
            assert caught.value.http_status == 409
            db.rollback()
        finally:
            db.close()
    assert _active_fences() == []
    _assert_batch_absent(tid, batch_no)


@pytest.mark.parametrize('field,value,status', [('data_state', 'FROZEN', 403), ('generation', 2, 409)])
def test_m4_locked_read_refreshes_resident_module_state(db_mode, field, value, status):
    """Two real MySQL transactions; keep the old ORM instance strongly referenced."""
    from app.models import TenantModuleState
    from app.services.module_commerce_access_guard import module_write_fence
    tid = BASE + (11 if field == 'data_state' else 12)
    _seed(tid); _pay(tid, f'M4-RESIDENT-{field}')
    db, batch = _business_session(tid, f'resident-{field}')
    batch_no = batch.batch_no
    try:
        assert db.get_bind().dialect.name == 'mysql'
        with db.no_autoflush:
            resident = db.scalars(select(TenantModuleState).where(
                TenantModuleState.tenant_id == tid, TenantModuleState.module_key == 'internship',
            )).one()
        assert resident.data_state == 'AVAILABLE' and resident.generation == 1
        # Disposable test data only: isolate final-fence freshness from the
        # independently covered cancellation/offboarding state machine.
        with db.get_bind().begin() as other:
            other.execute(TenantModuleState.__table__.update().where(
                TenantModuleState.tenant_id == tid, TenantModuleState.module_key == 'internship',
            ).values(**{field: value}))
        assert getattr(resident, field) != value  # the identity map really is stale
        with module_write_fence(tid, 'internship', 1), pytest.raises(AppException) as caught:
            db.commit()
        assert caught.value.http_status == status
        db.rollback()
    finally:
        db.close()
    _assert_batch_absent(tid, batch_no)


def test_m4_current_profile_cannot_be_hidden_by_resident_legacy_reader(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantCommercialProfile, TenantModuleSubscriptionSource
    from app.services.module_commerce_access_guard import module_write_fence
    tid = BASE + 13
    _seed(tid); _pay(tid, 'M4-RESIDENT-PROFILE')
    with get_sessionmaker()() as setup_session:
        engine = setup_session.get_bind()
    with engine.begin() as setup:
        setup.execute(TenantCommercialProfile.__table__.update().where(
            TenantCommercialProfile.tenant_id == tid).values(reader_version='LEGACY'))
    db, batch = _business_session(tid, 'resident-profile')
    batch_no = batch.batch_no
    try:
        assert engine.dialect.name == 'mysql'
        with db.no_autoflush:
            resident = db.scalars(select(TenantCommercialProfile).where(
                TenantCommercialProfile.tenant_id == tid)).one()
        assert resident.reader_version == 'LEGACY'
        with engine.begin() as other:
            other.execute(TenantCommercialProfile.__table__.update().where(
                TenantCommercialProfile.tenant_id == tid).values(reader_version='MODULE_V2'))
            other.execute(TenantModuleSubscriptionSource.__table__.update().where(
                TenantModuleSubscriptionSource.tenant_id == tid,
                TenantModuleSubscriptionSource.module_key == 'internship',
            ).values(status='CANCELLED'))
        assert resident.reader_version == 'LEGACY'
        with module_write_fence(tid, 'internship', 1), pytest.raises(AppException) as caught:
            db.commit()
        assert caught.value.http_status == 403
        db.rollback()
    finally:
        db.close()
    _assert_batch_absent(tid, batch_no)


@pytest.mark.parametrize('contended_table', [
    't_tenant_module_subscription_source', 't_tenant_commercial_profile',
])
def test_m4_expiry_after_lock_response_rolls_back_real_mysql_business_write(db_mode, monkeypatch, contended_table):
    """Real SQL/rollback, deterministic clock advance instead of timing-sensitive sleep.

    This proves the time check is after the database response; it does not pretend
    the event hook measures InnoDB's real lock-wait duration.
    """
    from types import SimpleNamespace
    from sqlalchemy import event
    from app.models import TenantModuleSubscriptionSource
    from app.services import module_commerce_access_guard as guard
    tid = BASE + (14 if contended_table.endswith('source') else 15)
    _seed(tid); _pay(tid, f'M4-LOCK-TIME-{tid}')
    db, batch = _business_session(tid, 'post-lock-expiry')
    batch_no = batch.batch_no
    connection = None
    hook = None
    try:
        assert db.get_bind().dialect.name == 'mysql'
        with db.no_autoflush:
            source = db.scalars(select(TenantModuleSubscriptionSource).where(
                TenantModuleSubscriptionSource.tenant_id == tid,
                TenantModuleSubscriptionSource.module_key == 'internship',
            )).one()
        clock = SimpleNamespace(now=source.ends_at - timedelta(seconds=1), advanced=False)
        end = source.ends_at
        monkeypatch.setattr(guard, 'datetime', SimpleNamespace(utcnow=lambda: clock.now))
        connection = db.connection()
        def hook(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and contended_table in statement:
                clock.now = end + timedelta(seconds=1)
                clock.advanced = True
        event.listen(connection, 'after_cursor_execute', hook)
        with guard.module_write_fence(tid, 'internship', 1), pytest.raises(AppException) as caught:
            db.commit()
        assert clock.advanced is True and caught.value.http_status == 403
        db.rollback()
    finally:
        if connection is not None and hook is not None:
            event.remove(connection, 'after_cursor_execute', hook)
        db.close()
    _assert_batch_absent(tid, batch_no)

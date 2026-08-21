from __future__ import annotations

import inspect


def test_w3_snapshot_service_keeps_payload_hash_immutable_and_reason_outside_payload():
    from app.modules.academic_affairs.services import academic_affairs_stats_snapshot_service as service

    source = inspect.getsource(service.create_snapshot)
    assert '"snapshotType": kind' in source
    assert '"indicators": data.get("indicators") or []' in source
    assert "payload_hash(frozen)" in source
    assert 'status="FROZEN"' in source
    assert "reason_text" in source
    # Freeze reason belongs to append-only audit/read-model display, never to canonical payload/hash.
    frozen_block = source.split("frozen = {", 1)[1].split("}", 1)[0]
    assert '"reason"' not in frozen_block
    assert "update_snapshot" not in inspect.getsource(service)
    assert "delete_snapshot" not in inspect.getsource(service)


def test_w3_snapshot_reason_is_recovered_from_create_audit_without_schema_write():
    from app.modules.academic_affairs.services import academic_affairs_stats_snapshot_service as service

    source = inspect.getsource(service._creation_reasons)
    assert 'AffairsAuditTrail.action == "STATS_SNAPSHOT_CREATE"' in source
    assert 'marker = ";reason="' in source
    assert "AaStatsSnapshot" not in source
    assert "db.add(" not in source
    assert "db.commit(" not in source


def test_w3_verify_is_server_side_read_and_never_accepts_client_hash():
    from app.modules.academic_affairs.routers import stats_snapshot_router

    source = inspect.getsource(stats_snapshot_router.stats_snapshot_verify)
    assert "service.get_snapshot(user, snapshot_id)" in source
    assert '"payloadHash": snapshot["payloadHash"]' in source
    assert '"integrityValid": True' in source
    assert '"immutable": True' in source
    assert "payloadHash" not in inspect.signature(stats_snapshot_router.stats_snapshot_verify).parameters
    assert "db.add(" not in source
    assert "db.commit(" not in source


def test_w3_detail_hash_mismatch_still_fails_closed():
    from app.modules.academic_affairs.services import academic_affairs_stats_snapshot_service as service

    source = inspect.getsource(service.get_snapshot)
    assert "payload_hash(parsed) != row.payload_hash" in source
    assert '"APPROVAL_VERSION_CONFLICT"' in source
    assert "http_status=409" in source
    assert "_creation_reasons" in source

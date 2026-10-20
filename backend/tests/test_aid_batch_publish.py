from datetime import datetime, timedelta

from test_affairs_aid import BASE, _hdr, _seed


def test_draft_publish_is_versioned_scoped_and_visible_in_both_student_clients(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidBatch
    from app.services import affairs_aid_service as aid
    from app.student_portal.services import affairs_service as portal
    from test_affairs_four_end_hardening import _set_ctx, _clear_ctx
    from test_affairs_aid import TID

    _seed(db_mode)
    admin, counselor = _hdr(client, "school_admin01"), _hdr(client, "counselor01")
    response = client.post(f"{BASE}/aid/batches", headers=admin, json={
        "batchName": "隔离验收草稿批次", "schoolYear": "2026-2027", "publish": False})
    assert response.status_code == 200, response.text
    draft = response.json()["data"]
    batch_id = draft["batchId"]
    url = f"{BASE}/aid/batches/{batch_id}/publish"
    student = {"userId": "u-A001", "studentNo": "A001", "realName": "甲一",
               "userType": "STUDENT", "currentRoleCode": "STUDENT", "tenantId": str(TID)}

    def visible():
        _set_ctx(student)
        try:
            return [x["batchId"] for x in portal.aid_batches_open(student)["items"]]
        finally:
            _clear_ctx()

    assert batch_id not in visible()
    assert client.post(url, headers=counselor, json={"version": draft["version"]}).status_code == 403
    assert client.post(url, headers=admin, json={}).status_code == 400
    assert client.post(url, headers=admin, json={"version": draft["version"] + 1}).status_code == 409
    with get_sessionmaker()() as db:
        assert db.get(AidBatch, int(batch_id)).status == "DRAFT"
    published = client.post(url, headers=admin, json={"version": draft["version"]})
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "OPEN"
    assert published.json()["data"]["version"] == draft["version"] + 1
    assert batch_id in visible()
    assert client.post(url, headers=admin, json={"version": draft["version"]}).status_code == 409
    detail = client.get(f"{BASE}/aid/batches/{batch_id}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "OPEN"
    # Stale drafts cannot be published after their application window expires.
    with get_sessionmaker()() as db:
        row = db.get(AidBatch, int(batch_id))
        row.status = "DRAFT"
        row.apply_end = datetime.utcnow() - timedelta(days=1)
        db.commit()
    assert client.post(url, headers=admin, json={"version": draft["version"] + 1}).status_code == 409
    # Cross-tenant lookup and publish do not reveal or change the batch.
    other = {**student, "tenantId": str(TID + 1), "currentRoleCode": "SCHOOL_ADMIN", "userType": "SCHOOL_ADMIN"}
    from app.core.exceptions import AppException
    import pytest
    _set_ctx(other)
    from app.core.context import set_tenant
    set_tenant({"tenantId": str(TID + 1)})
    try:
        with pytest.raises(AppException, match="不存在"):
            aid.get_batch(batch_id, other)
        with pytest.raises(AppException, match="不存在"):
            aid.publish_batch(batch_id, other, draft["version"] + 1)
    finally:
        _clear_ctx()

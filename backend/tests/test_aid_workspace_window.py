"""New-application windows must agree across staff intake and both student clients."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.services import affairs_aid_service as aid
from test_affairs_aid import BASE, TID, _apply, _hdr, _open_batch, _seed


def test_four_client_progress_never_confuses_review_publicity_with_completion():
    for status in aid.AID_NODES:
        data = aid.presentation(status)
        assert status not in data["statusLabel"]
        assert "认定已完成" not in data["progressHint"]
    assert "公示结束前尚未完成" in aid.presentation("SCHOOL_REVIEW")["progressHint"]
    assert "复核完成前" in aid.presentation("PUBLICITY", pending_objection=True)["progressHint"]
    assert "单独评审" in aid.presentation("APPROVED")["progressHint"]
    assert aid.presentation("UNKNOWN_INTERNAL_STATUS")["statusLabel"] == "状态待确认"


def test_window_boundaries_and_timezone():
    now = datetime(2026, 9, 5, 8)
    batch = SimpleNamespace(status="OPEN", apply_start=now, apply_end=now)
    aid.require_application_window(batch, now=now)
    for instant in (now - timedelta(microseconds=1), now + timedelta(microseconds=1)):
        with pytest.raises(AppException):
            aid.require_application_window(batch, now=instant)
    assert aid._parse_dt("2026-09-05T16:00:00+08:00") == now
    assert aid._parse_dt("2026-09-05T08:00:00Z") == now
    assert aid._parse_dt("2026-09-05T16:00") == now
    assert aid._parse_dt("invalid") is None


def test_staff_and_student_reject_closed_windows_without_creating_records(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch, AidFamilyEconomy
    from app.services import affairs_student_atomic_service as atomic
    from app.student_portal.services import affairs_service as portal
    from test_affairs_four_end_hardening import _set_ctx, _clear_ctx

    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    batch_id = _open_batch(client, hdr)
    student = {"userId": "u-A001", "studentNo": "A001", "realName": "甲一",
               "userType": "STUDENT", "currentRoleCode": "STUDENT", "tenantId": str(TID)}
    body = {"batchId": str(batch_id), "applyLevel": "GENERAL", "memberCount": 3,
            "statement": "隔离测试家庭经济困难情况说明，申请认定", "confirm": True}
    for offset, expected in ((1, "尚未开始"), (-2, "已结束")):
        with get_sessionmaker()() as db:
            batch = db.get(AidBatch, int(batch_id))
            batch.apply_start = datetime.utcnow() + timedelta(days=offset)
            batch.apply_end = batch.apply_start + timedelta(days=1)
            db.commit()
        result = _apply(client, hdr, batch_id, ids["sa"])
        assert result.status_code == 409, result.text
        assert expected in result.json()["message"]
        _set_ctx(student)
        try:
            available = portal.aid_batches_open(student)
            assert not any(x["batchId"] == str(batch_id) for x in available["items"])
            with pytest.raises(AppException, match=expected):
                atomic.aid_apply(student, body)
        finally:
            _clear_ctx()
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(AidApply).where(AidApply.batch_id == int(batch_id))) == 0
        assert db.scalar(select(func.count()).select_from(AidFamilyEconomy).where(AidFamilyEconomy.student_id == ids["sa"])) == 0
        batch = db.get(AidBatch, int(batch_id))
        batch.apply_start, batch.apply_end = datetime.utcnow() - timedelta(days=1), datetime.utcnow() + timedelta(days=1)
        db.commit()
    # Same window becomes available, and actual staff intake builds the workflow.
    accepted = _apply(client, hdr, batch_id, ids["sa"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "CLASS_REVIEW"


def test_terminal_or_deleted_application_cannot_be_recreated(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    batch_id = _open_batch(client, hdr)
    original = _apply(client, hdr, batch_id, ids["sa"]).json()["data"]
    for status, deleted in (("REJECTED", False), ("APPROVED", False), ("ARCHIVED", True)):
        with get_sessionmaker()() as db:
            row = db.get(AidApply, int(original["applyId"]))
            row.status, row.is_deleted = status, deleted
            db.commit()
        repeated = _apply(client, hdr, batch_id, ids["sa"])
        assert repeated.status_code == 409, repeated.text
        assert "原申请" in repeated.json()["message"]
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(AidApply).where(AidApply.batch_id == int(batch_id))) == 1


def test_batch_accepts_explicit_timezone_and_rejects_reversed_window(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    body = {"batchName": "窗口时区验收批次", "schoolYear": "2026-2027", "publish": True,
            "applyStart": "2026-09-05T08:00:00+08:00", "applyEnd": "2026-09-05T18:00:00+08:00"}
    result = client.post(f"{BASE}/aid/batches", headers=hdr, json=body)
    assert result.status_code == 200, result.text
    parsed = result.json()["data"]
    assert parsed["applyStart"].startswith("2026-09-05T00:00:00")
    body["applyEnd"] = "2026-09-05T07:00:00+08:00"
    assert client.post(f"{BASE}/aid/batches", headers=hdr, json=body).status_code == 400

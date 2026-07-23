"""P3 回归：审计列表、互查路由、多批次档案挑选。"""
from __future__ import annotations

from types import SimpleNamespace


def test_graduation_audit_logs_list(client, auth_headers, db_mode):
    r = client.get("/api/v1/graduation/audit-logs", headers=auth_headers, params={"page": 1, "pageSize": 10}).json()
    assert r["code"] == 0
    data = r["data"]
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_mobile_peer_tasks_requires_student(client, auth_headers, db_mode):
    r = client.get("/api/v1/mobile/graduation/peer-tasks", headers=auth_headers).json()
    # 管理端 token 不是学生身份，应拒绝
    assert r["code"] in (403001, 401001)


def test_pick_latest_non_archived_gd_prefers_active_over_newer_archived():
    """无 DB：多批次时优先最近未归档档，而非仅看 id 最大。"""
    from app.services.mobile_student_service import _pick_latest_non_archived_gd

    older_active = SimpleNamespace(id=10, stage="GUIDING")
    newer_archived = SimpleNamespace(id=20, stage="ARCHIVED")
    picked = _pick_latest_non_archived_gd([older_active, newer_archived])
    assert picked is older_active

    latest_active = SimpleNamespace(id=30, stage="FINAL_CHECK")
    picked2 = _pick_latest_non_archived_gd([older_active, newer_archived, latest_active])
    assert picked2 is latest_active

    only_archived = [
        SimpleNamespace(id=1, stage="ARCHIVED"),
        SimpleNamespace(id=5, stage="ARCHIVED"),
    ]
    assert _pick_latest_non_archived_gd(only_archived).id == 5
    assert _pick_latest_non_archived_gd([]) is None

"""PR190 P2-04：审批日期/“今日”统计必须按租户本地自然日，而不是 UTC 00:00。

以 Asia/Shanghai (+08:00) 的 2026-08-22 为例，本地自然日对应数据库 UTC-naive：
[2026-08-21 16:00:00, 2026-08-22 16:00:00)。
真实 MySQL 故意在边界两侧各放记录，锁死 submitDate / actedFrom+actedTo / summary。

本测试使用独立 tenant_id，避免全量回归共享 MySQL 中其它审批用例的“今日”记录污染
summary/list 总数。token 是非 db-* 的测试身份，不会绕过任何生产租户身份校验逻辑。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TID = 1000000000000000190
DAY = "2026-08-22"
START = datetime(2026, 8, 21, 16, 0, 0)
END = datetime(2026, 8, 22, 16, 0, 0)


def _headers():
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u_96001",
        "loginName": "timezone_school_admin",
        "realName": "时区测试管理员",
        "userType": "ADMIN",
        "tid": "tz-test",
        "tenantId": str(TID),
        "activeContextId": "ctx_school_admin",
        "currentRoleCode": "SCHOOL_ADMIN",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_task(db, *, source_id: int, status: str, created_at: datetime, acted_at: datetime | None = None):
    from app.models import WorkflowInstance, WorkflowTask

    inst = WorkflowInstance(
        tenant_id=TID,
        workflow_code="TZ_BOUNDARY_WF",
        source_module="test",
        source_biz_type="COMPANY_CHANGE",
        source_biz_id=source_id,
        applicant_id=97000 + source_id,
        title=f"时区边界任务 {source_id}",
        status="RUNNING" if status == "PENDING" else "APPROVED",
        current_node="NODE_TZ",
    )
    db.add(inst)
    db.flush()
    task = WorkflowTask(
        tenant_id=TID,
        instance_id=inst.id,
        node_code="NODE_TZ",
        assignee_id=96001,
        status=status,
        acted_at=acted_at,
    )
    db.add(task)
    db.flush()
    task.created_at = created_at
    return task


def _seed(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        # PENDING：本地 8/21 23:59、8/22 00:00、8/22 23:59、8/23 00:00
        _seed_task(db, source_id=1, status="PENDING", created_at=datetime(2026, 8, 21, 15, 59, 59))
        _seed_task(db, source_id=2, status="PENDING", created_at=START)
        _seed_task(db, source_id=3, status="PENDING", created_at=datetime(2026, 8, 22, 15, 59, 59))
        _seed_task(db, source_id=4, status="PENDING", created_at=END)

        # APPROVED：acted_at 使用同样四个边界位置；created_at 统一放更早，不干扰筛选。
        old = datetime(2026, 8, 20, 0, 0, 0)
        _seed_task(db, source_id=11, status="APPROVED", created_at=old,
                   acted_at=datetime(2026, 8, 21, 15, 59, 59))
        _seed_task(db, source_id=12, status="APPROVED", created_at=old, acted_at=START)
        _seed_task(db, source_id=13, status="APPROVED", created_at=old,
                   acted_at=datetime(2026, 8, 22, 15, 59, 59))
        _seed_task(db, source_id=14, status="APPROVED", created_at=old, acted_at=END)
        db.commit()
    finally:
        db.close()


def test_local_day_helper_maps_shanghai_midnight_to_utc_16(monkeypatch):
    from app.core import timeutil

    monkeypatch.setattr(timeutil, "tenant_tz", lambda: ZoneInfo("Asia/Shanghai"))
    start, end = timeutil.local_day_bounds_utc(DAY)
    assert start == START
    assert end == END


def test_submit_and_acted_date_filters_use_local_calendar_day(client, db_mode, monkeypatch):
    from app.core import timeutil

    monkeypatch.setattr(timeutil, "tenant_tz", lambda: ZoneInfo("Asia/Shanghai"))
    _seed(db_mode)
    headers = _headers()

    pending = client.get(
        "/api/v1/approvals/tasks",
        headers=headers,
        params={"submitDate": DAY, "page": 1, "pageSize": 50},
    )
    assert pending.status_code == 200, pending.text
    pdata = pending.json()["data"]
    assert pdata["total"] == 2, pdata
    assert {x["sourceBizId"] for x in pdata["items"]} == {"2", "3"}

    done = client.get(
        "/api/v1/approvals/tasks/done",
        headers=headers,
        params={"actedFrom": DAY, "actedTo": DAY, "page": 1, "pageSize": 50},
    )
    assert done.status_code == 200, done.text
    ddata = done.json()["data"]
    assert ddata["total"] == 2, ddata
    assert {x["sourceBizId"] for x in ddata["items"]} == {"12", "13"}


def test_summary_today_new_and_done_today_share_same_local_day_bounds(client, db_mode, monkeypatch):
    from app.core import timeutil

    _seed(db_mode)
    # summary 内部按调用时导入该 helper；固定边界使回归测试不依赖 CI 实际运行日期。
    monkeypatch.setattr(timeutil, "local_today_bounds_utc", lambda: (START, END))

    response = client.get("/api/v1/approvals/summary", headers=_headers())
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["todayNew"] == 2, data
    assert data["doneToday"] == 2, data

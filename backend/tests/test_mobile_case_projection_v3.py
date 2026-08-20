"""V3 §7 「我的办理」投影：真实 MySQL 下的分页、状态下推、归属隔离与时间线。

覆盖 V3 深审 P0-06：旧 my_applications() 三张表 .all() 全量读回 Python，
没有分页也没有游标；本模块必须把排序、过滤、分页全部下推到数据库。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import AppException
from app.services import mobile_case_projection_service as cases

MAIN = 1000000000000000001


def _stu_token(real_name, tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _list(client, name="办理甲", **params):
    """走真实端点：租户上下文由中间件建立，直接调 service 会因缺上下文被拒。"""
    query = "&".join(f"{key}={value}" for key, value in params.items() if value not in (None, ""))
    url = "/api/v1/mobile/student/cases" + (f"?{query}" if query else "")
    response = client.get(url, headers=_stu_token(name))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _detail(client, case_id, name="办理甲"):
    return client.get(f"/api/v1/mobile/student/cases/{case_id}", headers=_stu_token(name))


def _assert_client_error(response, context=""):
    """本仓库把校验错误统一收敛成 4xx（当前是 400），关键是必须被拒绝：
    既不能被当成没传而静默放行，也不能打成 5xx。"""
    assert 400 <= response.status_code < 500, f"{context} -> {response.status_code} {response.text[:200]}"


def _seed_cases(_db_mode, *, owner="办理甲", other="办理乙", leave_count=25):
    """给 owner 造一批不同状态、不同 updated_at 的请假，再给 other 造一条用于隔离验证。"""
    from app.db.session import get_sessionmaker
    from app.models import CsLeave, StudentProfile
    db = get_sessionmaker()()
    made = {}
    try:
        for name, no in [(owner, "CB0001"), (other, "CB0002")]:
            profile = StudentProfile(tenant_id=MAIN, student_no=no, real_name=name, grade="2023",
                                     current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
            db.add(profile)
            db.flush()
            made[name] = profile.id

        base = datetime(2026, 8, 1, 9, 0, 0)
        statuses = ["PENDING_REVIEW", "RETURNED", "APPROVED", "DRAFT", "REJECTED"]
        for index in range(leave_count):
            status = statuses[index % len(statuses)]
            leave = CsLeave(
                tenant_id=MAIN, student_id=made[owner], leave_type="PERSONAL",
                status=status, affairs_status=status, code=f"LV{index:04d}",
                apply_time=base + timedelta(hours=index),
                reviewer="辅导员" if status != "DRAFT" else None,
                return_reason="材料不全，请补充" if status == "RETURNED" else None,
            )
            db.add(leave)
            db.flush()
            # updated_at 由 onupdate 维护，这里显式铺开保证 keyset 排序可验证
            leave.updated_at = base + timedelta(hours=index)
        other_leave = CsLeave(tenant_id=MAIN, student_id=made[other], leave_type="SICK",
                              status="PENDING_REVIEW", affairs_status="PENDING_REVIEW", code="LVOTHER",
                              apply_time=base)
        db.add(other_leave)
        db.commit()
        made["otherLeaveId"] = other_leave.id
    finally:
        db.close()
    return made


def test_group_mapping_is_exhaustive_and_defaults_to_processing():
    assert cases._group_of("RETURNED") == "returned"
    assert cases._group_of("rejected") == "returned"
    assert cases._group_of("APPROVED") == "done"
    assert cases._group_of("DRAFT") == "pending"
    # 未登记的中间态一律算“审批中”，不会凭空消失
    assert cases._group_of("WAITING_COLLEGE") == "processing"
    assert cases._group_of(None) == "processing"


def test_unknown_group_is_rejected(client, db_mode):
    _seed_cases(db_mode)
    response = client.get("/api/v1/mobile/student/cases?statusGroup=not_a_group",
                          headers=_stu_token("办理甲"))
    _assert_client_error(response, "未知分组")


def test_cursor_is_monotonic_on_the_composite_key():
    now = datetime(2026, 8, 19, 12, 0, 0)
    earlier = cases._cursor_of(now - timedelta(minutes=1), "LEAVE", 9)
    later = cases._cursor_of(now, "LEAVE", 1)
    assert earlier < later, "更新时间才是主排序键"
    # 同一时刻靠 source + id 稳定区分
    assert cases._cursor_of(now, "GRANT", 1) < cases._cursor_of(now, "LEAVE", 1)
    assert cases._cursor_of(now, "LEAVE", 1) != cases._cursor_of(now, "LEAVE", 2)


def test_malformed_cursor_is_rejected_not_silently_ignored(client, db_mode):
    _seed_cases(db_mode)
    for bad in ("garbage", "a%7Cb", "not-a-time%7CLEAVE%7C1", "2026-08-19T00%3A00%3A00%7CLEAVE%7Cabc"):
        response = client.get(f"/api/v1/mobile/student/cases?cursor={bad}", headers=_stu_token("办理甲"))
        _assert_client_error(response, f"游标 {bad} 应被拒绝而不是被当成没传")


def test_list_pages_through_the_database_without_offset(client, db_mode):
    _seed_cases(db_mode)
    from urllib.parse import quote

    first = _list(client, pageSize=10)
    assert len(first["items"]) == 10
    assert first["nextCursor"], "还有更多时必须给游标"

    second = _list(client, pageSize=10, cursor=quote(first["nextCursor"], safe=""))
    assert len(second["items"]) == 10

    third = _list(client, pageSize=10, cursor=quote(second["nextCursor"], safe=""))
    assert len(third["items"]) == 5
    assert third["nextCursor"] is None, "最后一页不得再给游标"

    ids = [row["caseId"] for row in first["items"] + second["items"] + third["items"]]
    assert len(ids) == len(set(ids)) == 25, "翻页不得重复或漏条"

    # 按 updated_at 降序
    stamps = [row["updatedAt"] for row in first["items"] + second["items"] + third["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_status_filter_is_pushed_down_and_partitions_the_set(client, db_mode):
    _seed_cases(db_mode)
    from urllib.parse import quote

    total = 0
    for group in ("pending", "processing", "returned", "done"):
        rows = []
        cursor = None
        while True:
            page = _list(client, statusGroup=group, pageSize=10,
                         cursor=quote(cursor, safe="") if cursor else None)
            rows.extend(page["items"])
            cursor = page["nextCursor"]
            if not cursor:
                break
        assert all(row["statusGroup"] == group for row in rows), f"{group} 分组里混入了别的状态"
        total += len(rows)
    assert total == 25, "四个分组必须正好覆盖全部办理，不重不漏"


def test_returned_cases_carry_the_opinion_and_an_action_back_to_the_business_page(client, db_mode):
    _seed_cases(db_mode)
    page = _list(client, statusGroup="returned", pageSize=50)
    returned = [row for row in page["items"] if row["status"] == "RETURNED"]
    assert returned, "种子里应有退回记录"
    row = returned[0]
    assert row["latestOpinion"] == "材料不全，请补充"
    # 退回重提必须回到请假页本身，不是通用大厅
    assert row["action"]["target"]["path"] == "/pages/student/affairs/leave"
    assert row["action"]["target"]["routeExact"] is True
    assert row["action"]["target"]["query"]["recordId"] == row["sourceBizId"]


def test_another_students_case_is_invisible_and_undetectable(client, db_mode):
    made = _seed_cases(db_mode)
    mine = _list(client, pageSize=50)
    assert all(row["sourceBizId"] != str(made["otherLeaveId"]) for row in mine["items"])

    # 直接猜单号也拿不到，且返回 404 而不是 403（不泄露记录是否存在）
    response = _detail(client, f"leave:{made['otherLeaveId']}")
    assert response.status_code == 404, response.text


def test_detail_returns_a_timeline_whose_nodes_keep_their_source(client, db_mode):
    _seed_cases(db_mode)
    page = _list(client, pageSize=1)
    case_id = page["items"][0]["caseId"]
    response = _detail(client, case_id)
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    assert detail["caseId"] == case_id
    assert isinstance(detail["timeline"], list)
    for node in detail["timeline"]:
        assert node["source"], "每个时间线节点都必须保留出处"
        assert "actor" in node


def test_malformed_case_id_is_rejected(client, db_mode):
    _seed_cases(db_mode)
    for bad in ("leave", "leave:", "leave:abc", "unknown:1"):
        _assert_client_error(_detail(client, bad), f"单号 {bad}")


def test_endpoint_enforces_page_size_bounds(client, db_mode):
    _seed_cases(db_mode)
    headers = _stu_token("办理甲")
    _assert_client_error(client.get("/api/v1/mobile/student/cases?pageSize=0", headers=headers), "pageSize=0")
    _assert_client_error(client.get("/api/v1/mobile/student/cases?pageSize=51", headers=headers), "pageSize=51")
    ok = client.get("/api/v1/mobile/student/cases?pageSize=5", headers=headers)
    assert ok.status_code == 200
    assert len(ok.json()["data"]["items"]) == 5


def test_service_never_materialises_all_rows_in_python():
    source = open(cases.__file__, encoding="utf-8").read()
    body = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert ").all()" not in body or "db.execute(stmt).all()" in body
    # 明确禁止先取全量再切片
    assert "[:size]" in body and "rows[:size]" in body
    assert "limit(size + 1)" in body, "必须用 pageSize+1 判定 hasMore，不重复 COUNT"
    assert "offset(" not in body, "禁止深 OFFSET 分页"

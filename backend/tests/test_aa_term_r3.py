"""学年学期 续工 R3（/academic-affairs/terms/years、/academic-affairs/terms/switch-log）端点测试：
学年管理（按学年汇总学期） / 学期切换记录（PUBLISH/SET_CURRENT 审计流水推导切换链）。
SQLite 自测专用（由调用方通过 TEST_DATABASE_URL=sqlite:/// 环境变量触发 conftest.db_mode 的 sqlite 分支），
不得作为 MySQL 正式验收证据；正式验收由总控在共享 MySQL 测试库上顺序跑一遍 pytest。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_term(db_mode, year_code, term_no, status):
    """直接写库造不同状态的学年学期行（ARCHIVED/DRAFT 等无法全部经真实状态机快速驱动，测聚合逻辑本身）。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    t = AaTerm(tenant_id=TID, year_code=year_code, term_no=term_no, status=status)
    db.add(t); db.flush()
    tid = t.id
    db.commit()
    db.close()
    return tid


def _term(client, hdr, year="2026-2027", no=1):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year, "termNo": no, "termName": f"{year} 第{no}学期",
        "startDate": "2026-09-01", "endDate": "2027-01-15", "teachingWeeks": 18})


def test_r1_academic_years_grouping(client, db_mode):
    admin = _hdr(client, "school_admin01")
    # 2024-2025：两学期均已归档 → yearStatus=ARCHIVED
    _seed_term(db_mode, "2024-2025", 1, "ARCHIVED")
    _seed_term(db_mode, "2024-2025", 2, "ARCHIVED")
    # 2025-2026：仅草稿一学期 → yearStatus=PLANNING，termCount=1（缺第二学期）
    _seed_term(db_mode, "2025-2026", 1, "DRAFT")
    # 2026-2027：经真实发布链路 → yearStatus=ACTIVE，isCurrentYear=True
    tid = _term(client, admin, "2026-2027", 1).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{tid}/publish", headers=admin)

    res = client.get(f"{BASE}/terms/years", headers=admin)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    by_year = {row["yearCode"]: row for row in items}

    assert by_year["2024-2025"]["yearStatus"] == "ARCHIVED"
    assert by_year["2024-2025"]["termCount"] == 2
    assert by_year["2024-2025"]["isCurrentYear"] is False

    assert by_year["2025-2026"]["yearStatus"] == "PLANNING"
    assert by_year["2025-2026"]["termCount"] == 1

    assert by_year["2026-2027"]["yearStatus"] == "ACTIVE"
    assert by_year["2026-2027"]["isCurrentYear"] is True
    assert by_year["2026-2027"]["terms"][0]["termId"] == str(tid)
    # 学年降序排列（最新学年在前）
    assert [row["yearCode"] for row in items] == ["2026-2027", "2025-2026", "2024-2025"]


def test_r2_switch_log_tracks_publish_and_set_current(client, db_mode):
    admin = _hdr(client, "school_admin01")
    a = _term(client, admin, "2026-2027", 1).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{a}/publish", headers=admin)          # PUBLISH → A（from=None）
    b = _term(client, admin, "2026-2027", 2).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{b}/publish", headers=admin)          # PUBLISH → B（切走 A 的当前标记，from=A）
    client.post(f"{BASE}/terms/{a}/set-current", headers=admin)      # SET_CURRENT → A（from=B）

    res = client.get(f"{BASE}/terms/switch-log", headers=admin)
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["total"] >= 3
    items = body["items"]
    # 最新在前
    assert items[0]["action"] == "SET_CURRENT"
    assert items[0]["toTermId"] == str(a)
    assert items[0]["fromTermId"] == str(b)
    assert items[0]["toTermLabel"] == "2026-2027 第1学期"

    assert items[1]["action"] == "PUBLISH"
    assert items[1]["toTermId"] == str(b)
    assert items[1]["fromTermId"] == str(a)

    assert items[2]["action"] == "PUBLISH"
    assert items[2]["toTermId"] == str(a)
    assert items[2]["fromTermId"] is None
    assert items[2]["operator"]  # 操作人留痕非空


def test_r3_student_forbidden(client, db_mode):
    stu = _stu_token("学甲", "TT2602")
    assert client.get(f"{BASE}/terms/years", headers=stu).status_code == 403
    assert client.get(f"{BASE}/terms/switch-log", headers=stu).status_code == 403

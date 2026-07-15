"""学年学期 Tier1-R2（/academic-affairs/terms/*）端点测试：
当前学期设置(set-current) / 学期周次(weeks) / 教学周配置(teaching-weeks) / 学期状态(freeze/unfreeze) / 学期归档总览(archive-overview)。
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


def _seed_draft_term(db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    t = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="DRAFT",
              start_date=datetime(2026, 9, 1), teaching_weeks=18, exam_week_start=18)
    db.add(t); db.flush()
    tid = t.id
    db.commit()
    db.close()
    return tid


def test_t1_set_current_requires_published(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    admin = _hdr(client, "school_admin01")
    # DRAFT 学期不可直接设为当前 → 409
    assert client.post(f"{BASE}/terms/{term_id}/set-current", headers=admin).status_code == 409
    # 发布后可设为当前（幂等）
    pub = client.post(f"{BASE}/terms/{term_id}/publish", headers=admin).json()
    assert pub["data"]["isCurrent"] is True
    r1 = client.post(f"{BASE}/terms/{term_id}/set-current", headers=admin).json()
    assert r1["code"] == 0 and r1["data"]["isCurrent"] is True
    cur = client.get(f"{BASE}/terms/current", headers=admin).json()["data"]
    assert cur["termId"] == str(term_id)


def test_t2_weeks_grid_computed(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    admin = _hdr(client, "school_admin01")
    weeks = client.get(f"{BASE}/terms/{term_id}/weeks", headers=admin).json()["data"]["items"]
    assert len(weeks) == 18
    assert weeks[0]["weekNo"] == 1 and weeks[0]["startDate"] == "2026-09-01"
    # 第18周=考试周开始周次
    assert weeks[-1]["weekType"] == "EXAM"
    # 校历放假事件覆盖某周 → 该周类型变 HOLIDAY
    client.post(f"{BASE}/terms/{term_id}/calendar", headers=admin,
               json={"eventType": "HOLIDAY", "startDate": "2026-10-01", "endDate": "2026-10-07",
                    "remark": "国庆"})
    weeks2 = client.get(f"{BASE}/terms/{term_id}/weeks", headers=admin).json()["data"]["items"]
    assert any(w["weekType"] == "HOLIDAY" for w in weeks2)


def test_t3_teaching_weeks_config_only_draft(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    admin = _hdr(client, "school_admin01")
    # DRAFT 可改
    r = client.put(f"{BASE}/terms/{term_id}/teaching-weeks", headers=admin,
                  json={"teachingWeeks": 20, "examWeekStart": 19}).json()
    assert r["code"] == 0 and r["data"]["teachingWeeks"] == 20 and r["data"]["examWeekStart"] == 19
    # 考试周超过教学周总数 → 400
    bad = client.put(f"{BASE}/terms/{term_id}/teaching-weeks", headers=admin,
                     json={"examWeekStart": 99})
    assert bad.status_code == 400
    # 发布后结构性调整 → 409
    client.post(f"{BASE}/terms/{term_id}/publish", headers=admin)
    locked = client.put(f"{BASE}/terms/{term_id}/teaching-weeks", headers=admin,
                        json={"teachingWeeks": 22})
    assert locked.status_code == 409


def test_t4_freeze_unfreeze_state_machine(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    admin = _hdr(client, "school_admin01")
    # DRAFT→FROZEN 非法：409
    assert client.post(f"{BASE}/terms/{term_id}/freeze", headers=admin).status_code == 409
    client.post(f"{BASE}/terms/{term_id}/publish", headers=admin)
    # PUBLISHED→FROZEN 合法
    fz = client.post(f"{BASE}/terms/{term_id}/freeze", headers=admin).json()
    assert fz["code"] == 0 and fz["data"]["status"] == "FROZEN"
    # 已冻结不可重复冻结
    assert client.post(f"{BASE}/terms/{term_id}/freeze", headers=admin).status_code == 409
    # 解冻原因过短 → 400
    assert client.post(f"{BASE}/terms/{term_id}/unfreeze", headers=admin,
                       json={"reason": "短"}).status_code == 400
    uf = client.post(f"{BASE}/terms/{term_id}/unfreeze", headers=admin,
                     json={"reason": "误操作冻结需恢复排课"}).json()
    assert uf["code"] == 0 and uf["data"]["status"] == "PUBLISHED"


def test_t5_archive_overview_readonly(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/terms/{term_id}/publish", headers=admin)
    ov = client.get(f"{BASE}/terms/archive-overview", headers=admin).json()["data"]["items"]
    row = next(r for r in ov if r["termId"] == str(term_id))
    assert row["termStatus"] == "PUBLISHED" and row["archiveBatchStatus"] is None
    # 建立归档批次后总览应反映批次状态（不重复实现归档动作，仅验证只读联动）
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(term_id)}).json()["data"]["batchId"]
    ov2 = client.get(f"{BASE}/terms/archive-overview", headers=admin).json()["data"]["items"]
    row2 = next(r for r in ov2 if r["termId"] == str(term_id))
    assert row2["archiveBatchId"] == str(bid) and row2["archiveBatchStatus"] == "DRAFT"


def test_t6_student_forbidden(client, db_mode):
    term_id = _seed_draft_term(db_mode)
    stu = _stu_token("学甲", "TT2601")
    assert client.get(f"{BASE}/terms/{term_id}/weeks", headers=stu).status_code == 403
    assert client.post(f"{BASE}/terms/{term_id}/freeze", headers=stu).status_code == 403
    assert client.get(f"{BASE}/terms/archive-overview", headers=stu).status_code == 403

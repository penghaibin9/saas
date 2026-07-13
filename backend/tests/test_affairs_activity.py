"""13A-D 学生活动波次1 · 端到端（真实 DB 模式）。

覆盖：活动创建→发布→流转→确认生成二课学时(唯一防重复)→进360→台账/成绩单；
撤销确认重算不产生重复学分；非法状态/校验；二课类目建/列。
（enroll/checkin 为学生移动端本人动作，依赖学生令牌解析，另由移动集成测试覆盖；
本文件以 ORM 播入 CHECKED_IN 报名模拟"已报名+已签到"后走确认闭环。）
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_checkin(activity_id, student_id):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivitySignup
    db = get_sessionmaker()()
    db.add(AffairsActivitySignup(tenant_id=TID, activity_id=int(activity_id), student_id=int(student_id),
                                 signup_status="CHECKED_IN"))
    db.commit(); db.close()


def test_activity_full_flow_and_credit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    aid = client.post(f"{BASE}/activities", headers=hdr, json={
        "activityName": "2026迎新晚会", "activityType": "ACTIVITY", "creditType": "SECOND_CLASS",
        "creditValue": 2, "categoryCode": "WENTI", "quota": 50}).json()["data"]["activityId"]
    assert client.post(f"{BASE}/activities/{aid}/publish", headers=hdr,
                       json={"action": "PUBLISH"}).json()["data"]["status"] == "PUBLISHED"
    _seed_checkin(aid, sid)  # 模拟学生已报名+已签到
    for act in ("ENROLL_CLOSE", "START", "FINISH"):
        r = client.post(f"{BASE}/activities/{aid}/transition", headers=hdr, json={"action": act}).json()
        assert r["code"] == 0, (act, r)
    c = client.post(f"{BASE}/activities/{aid}/confirm", headers=hdr).json()
    assert c["code"] == 0 and c["data"]["status"] == "CONFIRMED" and c["data"]["creditsGranted"] == 1
    # 台账 + 成绩单
    led = client.get(f"{BASE}/second-class/ledger", headers=hdr).json()
    assert any(x["studentId"] == str(sid) and x["creditType"] == "SECOND_CLASS" for x in led["data"]["items"])
    rep = client.get(f"{BASE}/second-class/students/{sid}/report", headers=hdr).json()["data"]
    assert rep["items"] and any(t["key"] == "SECOND_CLASS" and t["value"] == 2 for t in rep["byType"])
    # 进360：确认写 StudentStageEvent(to_stage=ACTIVITY_CONFIRMED)
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    from sqlalchemy import select
    db = get_sessionmaker()()
    ev = db.scalars(select(StudentStageEvent).where(
        StudentStageEvent.tenant_id == TID, StudentStageEvent.student_id == sid,
        StudentStageEvent.to_stage == "ACTIVITY_CONFIRMED")).all()
    db.close()
    assert len(ev) >= 1


def test_activity_unconfirm_no_duplicate_credit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    sid = db_mode["student"]
    aid = client.post(f"{BASE}/activities", headers=hdr, json={
        "activityName": "志愿服务日", "activityType": "VOLUNTEER", "creditType": "VOLUNTEER_HOUR",
        "creditValue": 4}).json()["data"]["activityId"]
    client.post(f"{BASE}/activities/{aid}/publish", headers=hdr, json={"action": "PUBLISH"})
    _seed_checkin(aid, sid)
    for act in ("ENROLL_CLOSE", "START", "FINISH"):
        client.post(f"{BASE}/activities/{aid}/transition", headers=hdr, json={"action": act})
    client.post(f"{BASE}/activities/{aid}/confirm", headers=hdr)
    client.post(f"{BASE}/activities/{aid}/unconfirm", headers=hdr, json={"reason": "名单需重算"})
    c2 = client.post(f"{BASE}/activities/{aid}/confirm", headers=hdr).json()
    assert c2["data"]["creditsGranted"] == 1
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivityCredit
    from sqlalchemy import func, select
    db = get_sessionmaker()()
    n = db.scalar(select(func.count()).select_from(AffairsActivityCredit).where(
        AffairsActivityCredit.tenant_id == TID, AffairsActivityCredit.activity_id == int(aid)))
    db.close()
    assert n == 1  # 撤销删除后重算，仍只 1 条（唯一约束+删重建）


def test_activity_validation_and_state(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 空名称：或 HTTP 422，或统一信封业务错码（两种约定均视为拒绝，不得建成）
    r0 = client.post(f"{BASE}/activities", headers=hdr, json={"activityName": ""})
    assert r0.status_code == 422 or r0.json().get("code") not in (0, None)
    aid = client.post(f"{BASE}/activities", headers=hdr,
                      json={"activityName": "草稿活动"}).json()["data"]["activityId"]
    # 非 FINISHED 确认 → 业务错
    assert client.post(f"{BASE}/activities/{aid}/confirm", headers=hdr).json()["code"] != 0
    # 撤销原因过短 → 业务错
    assert client.post(f"{BASE}/activities/{aid}/publish", headers=hdr,
                       json={"action": "CANCEL", "reason": "短"}).json()["code"] != 0


def test_second_class_category(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/second-class/categories", headers=hdr,
                    json={"categoryCode": "SIXIANG", "categoryName": "思想成长", "creditType": "SECOND_CLASS"}).json()
    assert r["code"] == 0
    lst = client.get(f"{BASE}/second-class/categories", headers=hdr).json()
    assert any(c["categoryCode"] == "SIXIANG" for c in lst["data"]["items"])
    # 重复编码 → 业务错
    assert client.post(f"{BASE}/second-class/categories", headers=hdr,
                       json={"categoryCode": "SIXIANG", "categoryName": "重复"}).json()["code"] != 0

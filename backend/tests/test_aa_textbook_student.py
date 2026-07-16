"""教材学生自助端到端（正方 学生端6.13教材明细/6.14教材费用 对标）：
学生查本人教材领用+费用 → 签收本人教材(生成费用应收) → 费用出现；跨学生签收被拦。MySQL-only。
"""
from __future__ import annotations

BASE = "/api/v1/mobile/academic"
MAIN = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_dist(student_no, real_name, book="高等数学教材", price=45, qty=1):
    """建 学生档案 + 教材 + 待签收发放记录，返回 (profile_id, record_id)。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTextbook, AaTextbookDistributionRecord, StudentProfile
    db = get_sessionmaker()()
    p = StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                       current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(p); db.flush()
    tb = AaTextbook(tenant_id=MAIN, name=book, unit_price=price, status="ENABLED")
    db.add(tb); db.flush()
    r = AaTextbookDistributionRecord(tenant_id=MAIN, batch_id=1, student_id=p.id, textbook_id=tb.id,
                                     textbook_name=book, qty=qty, status="PENDING")
    db.add(r); db.flush()
    pid, rid = p.id, r.id
    db.commit(); db.close()
    return pid, rid


def test_textbook_my_sign_and_fee(client, db_mode):
    _pid, rid = _seed_dist("TB0001", "教材甲", price=45, qty=1)
    hdr = _stu_token("教材甲", "TB0001")
    # 签收前：待签收，无费用
    d = client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]
    assert len(d["distributions"]) == 1 and d["distributions"][0]["status"] == "PENDING"
    assert d["fees"]["items"] == [] and d["fees"]["totalDue"] == 0
    # 学生签收本人教材
    ok = client.post(f"{BASE}/textbook/{rid}/sign", headers=hdr).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "RECEIVED"
    # 签收后：已领取 + 费用应收 45
    d2 = client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]
    assert d2["distributions"][0]["status"] == "RECEIVED"
    assert len(d2["fees"]["items"]) == 1 and d2["fees"]["items"][0]["amount"] == 45.0
    assert d2["fees"]["totalDue"] == 45.0 and d2["fees"]["unpaid"] == 45.0


def test_textbook_cross_student_sign_forbidden(client, db_mode):
    _pid, rid = _seed_dist("TB0002", "教材乙", price=30)
    # 另一学生尝试签收乙的教材
    other = _stu_token("教材丙", "TB0003")
    _seed_dist("TB0003", "教材丙")  # 让丙有档案（否则 _me 报无档案）
    r = client.post(f"{BASE}/textbook/{rid}/sign", headers=other).json()
    assert r["code"] != 0  # 只能签收本人教材

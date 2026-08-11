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
    """建正式学期→征订价格快照→发放批次→学生待签收记录，返回 (profile_id, record_id)。

    学生签收现行生产合同必须沿完整征订/发放事实链取不可变价格快照，测试不再用孤立
    distribution_record + 当前教材目录价格冒充正式应收依据。
    """
    from app.db.session import get_sessionmaker
    from app.models import (
        AaTerm,
        AaTextbook,
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
        StudentProfile,
    )
    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == MAIN,
        AaTerm.year_code == "2098-2099",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        term = AaTerm(tenant_id=MAIN, year_code="2098-2099", term_no=1,
                      status="PUBLISHED", is_current=False)
        db.add(term); db.flush()
    p = StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                       current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(p); db.flush()
    tb = AaTextbook(tenant_id=MAIN, name=book, unit_price=price, status="ENABLED")
    db.add(tb); db.flush()
    order = AaTextbookOrderBatch(tenant_id=MAIN, batch_name=f"{student_no}-教材征订",
                                 term_id=term.id, status="ARRIVED")
    db.add(order); db.flush()
    db.add(AaTextbookOrderItem(
        tenant_id=MAIN, order_batch_id=order.id, textbook_id=tb.id, textbook_name=book,
        order_qty=qty, arrived_qty=qty, unit_price_snapshot=price,
    ))
    dist = AaTextbookDistributionBatch(
        tenant_id=MAIN, order_batch_id=order.id, status="DISTRIBUTING")
    db.add(dist); db.flush()
    r = AaTextbookDistributionRecord(tenant_id=MAIN, batch_id=dist.id, student_id=p.id,
                                     textbook_id=tb.id, textbook_name=book, qty=qty, status="PENDING")
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
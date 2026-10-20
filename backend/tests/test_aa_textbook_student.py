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
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "STUDENT_MINI"})}


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
    tb = AaTextbook(tenant_id=MAIN, name=book, isbn="9787300000000", unit_price=price, status="ENABLED")
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
    assert d["distributions"][0]["isbn"] == "9787300000000"
    assert d["fees"]["items"] == [] and d["fees"]["totalDue"] == 0
    # 学生签收本人教材
    ok = client.post(f"{BASE}/textbook/{rid}/sign", headers=hdr).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "RECEIVED"
    # 签收后：已领取 + 费用应收 45
    d2 = client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]
    assert d2["distributions"][0]["status"] == "RECEIVED"
    assert len(d2["fees"]["items"]) == 1 and d2["fees"]["items"][0]["amount"] == 45.0
    assert d2["fees"]["totalDue"] == 45.0 and d2["fees"]["unpaid"] == 45.0
    # Replaying a receipt never creates a second charge.
    again = client.post(f"{BASE}/textbook/{rid}/sign", headers=hdr).json()
    assert again["code"] == 0
    assert client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]["fees"]["totalDue"] == 45.0
    # 正式退领保留原费用历史，但已减免金额不能继续计入学生应缴/欠费。
    from test_aa_textbook import _hdr
    admin = _hdr(client, "school_admin01")
    returned = client.post(f"/api/v1/academic-affairs/textbooks/distribution-records/{rid}/return",
        headers=admin, json={"reason": "核对实际领用范围后办理教材退领"})
    assert returned.status_code == 200, returned.text
    after_return = client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]
    assert after_return["distributions"][0]["status"] == "RETURNED"
    assert after_return["fees"]["items"][0]["amount"] == 45.0
    assert after_return["fees"]["items"][0]["status"] == "WAIVED"
    assert after_return["fees"]["totalDue"] == after_return["fees"]["unpaid"] == 0
    assert after_return["fees"]["waivedAmount"] == 45.0
    assert client.post(f"{BASE}/textbook/{rid}/sign", headers=hdr).status_code == 409
    # A retired catalog entry must not hide the historical distribution.
    from app.db.session import get_sessionmaker
    from app.models import AaTextbook, AaTextbookDistributionRecord
    with get_sessionmaker()() as db:
        record = db.get(AaTextbookDistributionRecord, rid)
        db.get(AaTextbook, record.textbook_id).is_deleted = True
        db.commit()
    retained = client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]["distributions"]
    assert len(retained) == 1 and retained[0]["isbn"] is None
    # Deleted distribution records must disappear from both student surfaces.
    with get_sessionmaker()() as db:
        db.get(AaTextbookDistributionRecord, rid).is_deleted = True
        db.commit()
    assert client.get(f"{BASE}/textbook/my", headers=hdr).json()["data"]["distributions"] == []


def test_textbook_cross_student_sign_forbidden(client, db_mode):
    _pid, rid = _seed_dist("TB0002", "教材乙", price=30)
    # 另一学生尝试签收乙的教材
    other = _stu_token("教材丙", "TB0003")
    _seed_dist("TB0003", "教材丙")  # 让丙有档案（否则 _me 报无档案）
    r = client.post(f"{BASE}/textbook/{rid}/sign", headers=other).json()
    assert r["code"] != 0  # 只能签收本人教材


def test_textbook_mobile_pages_are_bounded_and_keep_full_fee_totals(client, db_mode):
    """移动端教材明细/费用必须数据库分页，且猜测别人的 recordId 不能读取。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AaTextbook,
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
    )

    profile_id, first_record_id = _seed_dist("TBPAGE-A", "教材分页甲", book="分页教材 00", price=1)
    with get_sessionmaker()() as db:
        first_record = db.get(AaTextbookDistributionRecord, first_record_id)
        first_record.status = "RECEIVED"
        distribution_batch = db.get(AaTextbookDistributionBatch, first_record.batch_id)
        order_batch = db.get(AaTextbookOrderBatch, distribution_batch.order_batch_id)
        # A distribution batch points to one order batch; isolated test fixtures add
        # realistic catalogue/order/receipt rows without changing a manual sandbox flow.
        db.add(AaTextbookFeeLedger(
            tenant_id=MAIN,
            distribution_record_id=first_record.id,
            student_id=profile_id,
            textbook_name=first_record.textbook_name,
            amount=1,
            paid_amount=0,
            status="UNPAID",
        ))
        for number in range(2, 24):
            textbook = AaTextbook(
                tenant_id=MAIN,
                name=f"分页教材 {number:02d}",
                isbn=f"9787300{number:06d}",
                unit_price=number,
                status="ENABLED",
            )
            db.add(textbook); db.flush()
            db.add(AaTextbookOrderItem(
                tenant_id=MAIN,
                order_batch_id=order_batch.id,
                textbook_id=textbook.id,
                textbook_name=textbook.name,
                order_qty=1,
                arrived_qty=1,
                unit_price_snapshot=number,
            ))
            record = AaTextbookDistributionRecord(
                tenant_id=MAIN,
                batch_id=first_record.batch_id,
                student_id=profile_id,
                textbook_id=textbook.id,
                textbook_name=textbook.name,
                qty=1,
                status="RECEIVED",
            )
            db.add(record); db.flush()
            db.add(AaTextbookFeeLedger(
                tenant_id=MAIN,
                distribution_record_id=record.id,
                student_id=profile_id,
                textbook_name=record.textbook_name,
                amount=number,
                paid_amount=0,
                status="UNPAID",
            ))
        db.commit()

    header = _stu_token("教材分页甲", "TBPAGE-A")
    first_page = client.get(f"{BASE}/textbook/my", headers=header, params={
        "distributionPage": 1, "distributionPageSize": 20, "feePage": 1, "feePageSize": 20,
    })
    assert first_page.status_code == 200, first_page.text
    first = first_page.json()["data"]
    assert len(first["distributions"]) == 20
    assert first["distributionPagination"] == {"total": 23, "page": 1, "pageSize": 20, "hasMore": True}
    assert len(first["fees"]["items"]) == 20
    assert first["fees"]["total"] == 23 and first["fees"]["hasMore"] is True
    assert first["fees"]["totalDue"] == sum(range(1, 24)) and first["fees"]["unpaid"] == sum(range(1, 24))

    second_page = client.get(f"{BASE}/textbook/my", headers=header, params={
        "distributionPage": 2, "distributionPageSize": 20, "feePage": 2, "feePageSize": 20,
    })
    assert second_page.status_code == 200, second_page.text
    second = second_page.json()["data"]
    assert len(second["distributions"]) == len(second["fees"]["items"]) == 3
    assert second["distributionPagination"]["hasMore"] is False
    assert second["fees"]["total"] == 23 and second["fees"]["hasMore"] is False
    assert {row["recordId"] for row in first["distributions"]}.isdisjoint(
        {row["recordId"] for row in second["distributions"]}
    )

    _other_profile_id, _other_record_id = _seed_dist("TBPAGE-B", "教材分页乙")
    other = client.get(f"{BASE}/textbook/my", headers=_stu_token("教材分页乙", "TBPAGE-B"), params={
        "distributionRecordId": str(first_record_id),
    })
    assert other.status_code == 200, other.text
    assert other.json()["data"]["distributions"] == []
    assert other.json()["data"]["distributionPagination"]["total"] == 0

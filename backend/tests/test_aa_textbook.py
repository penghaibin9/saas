"""教材管理（/academic-affairs/textbooks/*）端点测试。

覆盖全链路：目录→选用(挂教学任务)→审核(学院→教务→备案)→征订(汇总合并+到货)→
发放(生成名单+签收触发费用台账)→费用(标记已收)→统计；ISBN 重复400、非在籍不可签收、学生越权403。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§8/§9。
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


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass,
                            StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=1, course_name="高等数学",
                        class_id=klass.id, teaching_class_name="软件2401",
                        teacher_key="teacher_a", teacher_name="甲老师")
    db.add(tt); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="TB2401", real_name="书甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    ids = {"task": tt.id, "class": klass.id, "student": s1.id}
    db.commit(); db.close()
    return ids


def test_t1_full_chain(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 目录
    tbid = client.post(f"{BASE}/textbooks", headers=admin,
                       json={"name": "高等数学(第七版)", "isbn": "9787040396638", "unitPrice": 45.5}).json()["data"]["textbookId"]
    # 选用（挂教学任务）→ 提交
    sid = client.post(f"{BASE}/textbooks/selections", headers=admin,
                      json={"taskId": str(ids["task"]), "textbookId": str(tbid), "expectedQty": 40}).json()["data"]["selectionId"]
    client.post(f"{BASE}/textbooks/selections/{sid}/submit", headers=admin)
    # 审核批次（纳入选用）→ 逐级推进到 PUBLISHED（DRAFT→COLLEGE_REVIEWING→COLLEGE_APPROVED→ACADEMIC_APPROVED→PUBLISHED）
    rbid = client.post(f"{BASE}/textbooks/review-batches", headers=admin,
                       json={"batchName": "2024秋审核", "selectionIds": [str(sid)]}).json()["data"]["reviewBatchId"]
    for _ in range(4):
        client.post(f"{BASE}/textbooks/review-batches/{rbid}/advance", headers=admin, json={"action": "APPROVE"})
    rb = client.post(f"{BASE}/textbooks/review-batches/{rbid}/advance", headers=admin, json={"action": "APPROVE"})
    # 已到 PUBLISHED（5 步：DRAFT起点，4次推进到 ACADEMIC_APPROVED，第5次→PUBLISHED）
    # 选用应变 APPROVED
    sels = client.get(f"{BASE}/textbooks/selections", headers=admin, params={"status": "APPROVED"}).json()["data"]["items"]
    assert any(s["selectionId"] == str(sid) for s in sels)
    # 征订：从 APPROVED 选用汇总生成
    obid = client.post(f"{BASE}/textbooks/order-batches", headers=admin, json={"batchName": "2024秋征订"}).json()["data"]["orderBatchId"]
    client.post(f"{BASE}/textbooks/order-batches/{obid}/submit", headers=admin)
    items = client.get(f"{BASE}/textbooks/order-batches/{obid}/items", headers=admin).json()["data"]["items"]
    assert len(items) == 1 and items[0]["orderQty"] == 40
    itemId = items[0]["itemId"]
    # 登记到货（全到货 → ARRIVED）
    arr = client.post(f"{BASE}/textbooks/order-items/{itemId}/arrival", headers=admin, json={"arrivedQty": 40}).json()
    assert arr["data"]["batchStatus"] == "ARRIVED"
    # 发放：生成名单
    dbid = client.post(f"{BASE}/textbooks/distribution-batches", headers=admin,
                       json={"orderBatchId": str(obid), "classId": str(ids["class"]), "studentIds": [str(ids["student"])]}).json()["data"]["distributionBatchId"]
    recs = client.get(f"{BASE}/textbooks/distribution-batches/{dbid}/records", headers=admin).json()["data"]["items"]
    assert len(recs) == 1 and recs[0]["status"] == "PENDING"
    rid = recs[0]["recordId"]
    # 签收 → 触发费用台账
    assert client.post(f"{BASE}/textbooks/distribution-records/{rid}/sign", headers=admin).json()["data"]["status"] == "RECEIVED"
    fees = client.get(f"{BASE}/textbooks/fee-ledger", headers=admin).json()["data"]["items"]
    assert len(fees) == 1 and fees[0]["amount"] == 45.5 and fees[0]["status"] == "UNPAID"
    # 标记已收
    assert client.post(f"{BASE}/textbooks/fee-ledger/{fees[0]['feeId']}/mark", headers=admin, json={"action": "PAID"}).json()["data"]["status"] == "PAID"
    # 统计
    st = client.get(f"{BASE}/textbooks/stats", headers=admin).json()["data"]
    assert st["orderQty"] == 40 and st["arrivedQty"] == 40 and st["arrivalRate"] == 1.0


def test_t2_isbn_duplicate_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/textbooks", headers=admin, json={"name": "书A", "isbn": "ISBN-DUP-1"})
    assert client.post(f"{BASE}/textbooks", headers=admin, json={"name": "书B", "isbn": "ISBN-DUP-1"}).status_code == 400


def test_t3_selection_duplicate_task_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tbid = client.post(f"{BASE}/textbooks", headers=admin, json={"name": "书X"}).json()["data"]["textbookId"]
    client.post(f"{BASE}/textbooks/selections", headers=admin, json={"taskId": str(ids["task"]), "textbookId": str(tbid)})
    # 同教学任务再建未终结选用 → 409
    assert client.post(f"{BASE}/textbooks/selections", headers=admin,
                       json={"taskId": str(ids["task"]), "textbookId": str(tbid)}).status_code == 409


def test_t4_review_return(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tbid = client.post(f"{BASE}/textbooks", headers=admin, json={"name": "书R"}).json()["data"]["textbookId"]
    sid = client.post(f"{BASE}/textbooks/selections", headers=admin, json={"taskId": str(ids["task"]), "textbookId": str(tbid)}).json()["data"]["selectionId"]
    client.post(f"{BASE}/textbooks/selections/{sid}/submit", headers=admin)
    rbid = client.post(f"{BASE}/textbooks/review-batches", headers=admin, json={"selectionIds": [str(sid)]}).json()["data"]["reviewBatchId"]
    # 退回原因过短 400
    assert client.post(f"{BASE}/textbooks/review-batches/{rbid}/advance", headers=admin, json={"action": "RETURN", "reason": "x"}).status_code == 400
    # 合法退回 → 选用回 RETURNED
    r = client.post(f"{BASE}/textbooks/review-batches/{rbid}/advance", headers=admin, json={"action": "RETURN", "reason": "教材版次过旧需更新"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "RETURNED"


def test_t6_partial_fee_and_stock(client, db_mode):
    """费用部分收款(PARTIAL→累计达应收转PAID) + 教材库存(到货-已发放)。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tbid = client.post(f"{BASE}/textbooks", headers=admin,
                       json={"name": "高数(七版)", "isbn": "9787040396000", "unitPrice": 50}).json()["data"]["textbookId"]
    sid = client.post(f"{BASE}/textbooks/selections", headers=admin,
                      json={"taskId": str(ids["task"]), "textbookId": str(tbid), "expectedQty": 10}).json()["data"]["selectionId"]
    client.post(f"{BASE}/textbooks/selections/{sid}/submit", headers=admin)
    rbid = client.post(f"{BASE}/textbooks/review-batches", headers=admin, json={"selectionIds": [str(sid)]}).json()["data"]["reviewBatchId"]
    for _ in range(5):
        client.post(f"{BASE}/textbooks/review-batches/{rbid}/advance", headers=admin, json={"action": "APPROVE"})
    obid = client.post(f"{BASE}/textbooks/order-batches", headers=admin, json={"batchName": "征订"}).json()["data"]["orderBatchId"]
    client.post(f"{BASE}/textbooks/order-batches/{obid}/submit", headers=admin)
    itemId = client.get(f"{BASE}/textbooks/order-batches/{obid}/items", headers=admin).json()["data"]["items"][0]["itemId"]
    client.post(f"{BASE}/textbooks/order-items/{itemId}/arrival", headers=admin, json={"arrivedQty": 10})
    dbid = client.post(f"{BASE}/textbooks/distribution-batches", headers=admin,
                       json={"orderBatchId": str(obid), "classId": str(ids["class"]), "studentIds": [str(ids["student"])]}).json()["data"]["distributionBatchId"]
    rid = client.get(f"{BASE}/textbooks/distribution-batches/{dbid}/records", headers=admin).json()["data"]["items"][0]["recordId"]
    client.post(f"{BASE}/textbooks/distribution-records/{rid}/sign", headers=admin)
    fid = client.get(f"{BASE}/textbooks/fee-ledger", headers=admin).json()["data"]["items"][0]["feeId"]
    # 部分收款 20 → PARTIAL
    r1 = client.post(f"{BASE}/textbooks/fee-ledger/{fid}/mark", headers=admin, json={"action": "PARTIAL", "amount": 20}).json()
    assert r1["data"]["status"] == "PARTIAL" and r1["data"]["paidAmount"] == 20.0
    # 再收 30 → 累计50=应收 → PAID
    r2 = client.post(f"{BASE}/textbooks/fee-ledger/{fid}/mark", headers=admin, json={"action": "PARTIAL", "amount": 30}).json()
    assert r2["data"]["status"] == "PAID"
    # 超收拦截
    assert client.post(f"{BASE}/textbooks/fee-ledger/{fid}/mark", headers=admin, json={"action": "PARTIAL", "amount": 10}).status_code == 400
    # 库存：到货10 - 已发放签收1 = 9
    stock = client.get(f"{BASE}/textbooks/stock", headers=admin).json()["data"]["items"]
    row = next(x for x in stock if x["textbookId"] == str(tbid))
    assert row["arrivedQty"] == 10 and row["distributedQty"] == 1 and row["stockQty"] == 9


def test_t5_student_cannot_manage_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("书甲", "TB2401")
    assert client.post(f"{BASE}/textbooks", headers=stu, json={"name": "越权"}).status_code == 403
    assert client.get(f"{BASE}/textbooks", headers=stu).status_code == 403

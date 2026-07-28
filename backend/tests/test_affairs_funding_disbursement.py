"""13A-C 奖助发放台账端到端（真实 DB）。

覆盖：按批次为 GRANTED 申请生成发放台账(幂等)→标记已发放/失败→发放概览；
重复发放冲突、失败原因过短、已发放不可置失败。金额脱敏由后端裁定。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_granted(sid, n=2):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject, StudentProfile
    db = get_sessionmaker()()
    p = FundingProject(tenant_id=TID, project_name="国家助学金", project_type="GRANT",
                       amount=3300, quota=10, status="ENABLED")
    db.add(p); db.flush()
    b = FundingBatch(tenant_id=TID, project_id=p.id, project_type="GRANT", year_code="2025-2026",
                     quota=10, status="OPEN")
    db.add(b); db.flush()
    base_student = db.get(StudentProfile, int(sid))
    assert base_student is not None
    student_ids = [int(sid)]
    for i in range(1, n):
        other = StudentProfile(
            tenant_id=TID, student_no=f"DISB{sid}-{i}", real_name=f"发放测试学生{i}",
            class_id=base_student.class_id, college_id=base_student.college_id,
            current_stage=base_student.current_stage or "ON_CAMPUS",
            student_status="NORMAL", status="ACTIVE", is_deleted=False, version=0,
        )
        db.add(other); db.flush(); student_ids.append(int(other.id))
    for student_id in student_ids:
        db.add(FundingApplication(tenant_id=TID, batch_id=b.id, student_id=student_id,
                                  apply_source="SELF", project_type="GRANT", amount=3300,
                                  status="GRANTED", is_deleted=False, version=0))
    db.commit()
    bid = b.id
    db.close()
    return bid


def test_disbursement_full_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    bid = _seed_granted(db_mode["student"], n=2)
    # 生成发放台账
    g = client.post(f"{BASE}/funding/batches/{bid}/disbursements/generate", headers=hdr).json()
    assert g["code"] == 0 and g["data"]["generated"] == 2
    # 幂等：再生成 0 条
    g2 = client.post(f"{BASE}/funding/batches/{bid}/disbursements/generate", headers=hdr).json()
    assert g2["data"]["generated"] == 0
    # 台账列表（PENDING 2 条）
    lst = client.get(f"{BASE}/funding/disbursements", headers=hdr, params={"batchId": bid}).json()
    items = lst["data"]["items"]
    assert len(items) == 2 and all(x["bankStatus"] == "PENDING" for x in items)
    d1, d2 = items[0]["disbursementId"], items[1]["disbursementId"]
    # 标记已发放
    iss = client.post(f"{BASE}/funding/disbursements/{d1}/issue", headers=hdr,
                      json={"disburseNo": "FB2026-001", "bankLast4": "6411"}).json()
    assert iss["code"] == 0 and iss["data"]["bankStatus"] == "ISSUED"
    assert iss["data"]["bankLast4"] == "6411"  # 仅后4位
    # 重复发放 → 冲突
    assert client.post(f"{BASE}/funding/disbursements/{d1}/issue", headers=hdr, json={}).json()["code"] != 0
    # 已发放不可置失败
    assert client.post(f"{BASE}/funding/disbursements/{d1}/fail", headers=hdr,
                       json={"reason": "银行退回卡号有误"}).json()["code"] != 0
    # 另一条置失败（原因≥5）
    assert client.post(f"{BASE}/funding/disbursements/{d2}/fail", headers=hdr,
                       json={"reason": "短"}).json()["code"] != 0
    f2 = client.post(f"{BASE}/funding/disbursements/{d2}/fail", headers=hdr,
                     json={"reason": "银行账号信息缺失待补"}).json()
    assert f2["code"] == 0 and f2["data"]["bankStatus"] == "FAILED"
    # 发放概览
    st = client.get(f"{BASE}/funding/disbursements/stats", headers=hdr).json()["data"]
    assert st["total"] == 2 and any(x["key"] == "ISSUED" for x in st["byStatus"])

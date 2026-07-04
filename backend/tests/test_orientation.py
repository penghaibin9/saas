"""数字迎新域测试：台账 CRUD + 绿色通道/材料/宿舍/异常各闭环 + 审计 + 看板。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (GreenChannelApplication, OrientationException, OrientationMaterial,
                            OrientationStudent)
    db = get_sessionmaker()()
    try:
        s = OrientationStudent(tenant_id=MAIN_TID, name="新生甲", admission_no="LQ2026999001",
                               class_name="软件2601班", phone_encrypted="13800009999",
                               id_card_encrypted="330102200801019999", stage="ADMITTED",
                               report_status="PREPARED", payment_status="UNPAID",
                               material_status="UPLOADED", dorm_status="ASSIGNED", risk_level="HIGH",
                               building="梧桐苑1号楼", room="1-301-1", counselor="李辅导",
                               steps_json={"ACTIVATE": "DONE", "PAYMENT": "BLOCKED"},
                               blocked_step="PAYMENT", blocked_reason="未缴费", payable_amount=8600,
                               paid_amount=0)
        db.add(s)
        db.flush()
        gc = GreenChannelApplication(tenant_id=MAIN_TID, ori_student_id=s.id, apply_type="生源地助学贷款",
                                     apply_amount=8600, submit_time=datetime.utcnow(), status="REVIEWING")
        mat = OrientationMaterial(tenant_id=MAIN_TID, ori_student_id=s.id, material_type="AID_PROOF",
                                  file_name="困难认定表.pdf", submit_time=datetime.utcnow(), status="UPLOADED")
        exc = OrientationException(tenant_id=MAIN_TID, ori_student_id=s.id, exception_type="PAYMENT",
                                   description="缴费异常", risk_level="MEDIUM", status="OPEN", handler="李辅导")
        db.add_all([gc, mat, exc])
        db.commit()
        return {"student": s.id, "gc": gc.id, "mat": mat.id, "exc": exc.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/orientation/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["reportStatusLabel"] == "预报到完成"
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["greenChannels"]) == 1 and len(det["data"]["materials"]) == 1
    assert det["data"]["student"]["steps"]["PAYMENT"] == "BLOCKED"
    assert len(det["data"]["steps"]) == 7
    assert det["data"]["steps"][0] == {"key": "ACTIVATE", "label": "账号激活"}
    assert det["data"]["steps"][3]["key"] == "PAYMENT"


def test_create_and_void_student(client, auth_headers, db_mode):
    _seed(db_mode)
    c = client.post("/api/v1/orientation/students", headers=auth_headers,
                    json={"name": "新生乙", "admissionNo": "LQ2026999002"}).json()
    assert c["code"] == 0
    sid = c["data"]["id"]
    dup = client.post("/api/v1/orientation/students", headers=auth_headers,
                      json={"name": "x", "admissionNo": "LQ2026999002"}).json()
    assert dup["code"] == 409001
    bad = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                     json={"reason": "录取信息重复，作废该记录"}).json()
    assert ok["code"] == 0


def test_green_channel_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/reject", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/approve", headers=auth_headers,
                     json={"remark": "材料齐全予以通过"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    # 通过后学生缴费状态转绿色通道，并解除 PAYMENT 卡点
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["paymentStatus"] == "GREEN_CHANNEL"
    assert det["data"]["student"]["blockedStep"] == ""
    assert det["data"]["student"]["steps"]["PAYMENT"] == "DONE"
    dup = client.post(f"/api/v1/orientation/green-channels/{ids['gc']}/approve", headers=auth_headers,
                      json={}).json()
    assert dup["code"] == 409001


def test_material_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/orientation/materials/{ids['mat']}/return", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/materials/{ids['mat']}/approve", headers=auth_headers,
                     json={}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"


def test_dorm_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ex = client.post(f"/api/v1/orientation/dorms/{ids['student']}/exception", headers=auth_headers,
                     json={"note": "床位与系统记录不一致"}).json()
    assert ex["code"] == 0
    dorms = client.get("/api/v1/orientation/dorms?dormStatus=EXCEPTION", headers=auth_headers).json()
    assert dorms["data"]["total"] == 1


def test_exception_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    fu = client.post(f"/api/v1/orientation/exceptions/{ids['exc']}/followup", headers=auth_headers,
                     json={"content": "已电话联系家长", "way": "PHONE"}).json()
    assert fu["code"] == 0
    esc = client.post(f"/api/v1/orientation/exceptions/{ids['exc']}/escalate", headers=auth_headers,
                      json={"reason": "多次联系无果，升级处理"}).json()
    assert esc["code"] == 0 and esc["data"]["status"] == "ESCALATED"
    det = client.get(f"/api/v1/orientation/exceptions/{ids['exc']}", headers=auth_headers).json()
    assert det["data"]["exception"]["riskLevel"] == "HIGH" and len(det["data"]["exception"]["followUps"]) == 1


def test_dashboard_and_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    dash = client.get("/api/v1/orientation/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(k["key"] == "total" for k in dash["data"]["kpis"])
    assert any(k["key"] == "prepared" for k in dash["data"]["kpis"])
    assert len(dash["data"]["stepFunnel"]) == 7
    # 触发一条审计后可查
    client.post(f"/api/v1/orientation/materials/{ids['mat']}/approve", headers=auth_headers, json={})
    audit = client.get("/api/v1/orientation/audit-logs?bizType=MATERIAL", headers=auth_headers).json()
    assert audit["code"] == 0 and audit["data"]["total"] >= 1


def test_update_student(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ok = client.put(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers,
                    json={"reportStatus": "CHECKED_IN", "counselor": "王辅导"}).json()
    assert ok["code"] == 0
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["reportStatus"] == "CHECKED_IN"
    assert det["data"]["student"]["counselor"] == "王辅导"


def test_progress_blocked_and_resolve(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.put(f"/api/v1/orientation/progress/{ids['student']}/blocked", headers=auth_headers,
                     json={"blockedStep": "MATERIAL", "blockedReason": "短"}).json()
    assert bad["code"] == 422001
    ok = client.put(f"/api/v1/orientation/progress/{ids['student']}/blocked", headers=auth_headers,
                    json={"blockedStep": "MATERIAL", "blockedReason": "材料缺失需补交"}).json()
    assert ok["code"] == 0
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["blockedStep"] == "MATERIAL"
    assert det["data"]["student"]["steps"]["MATERIAL"] == "BLOCKED"
    resolved = client.post(f"/api/v1/orientation/progress/{ids['student']}/resolve", headers=auth_headers,
                           json={"note": "已人工处理"}).json()
    assert resolved["code"] == 0
    det2 = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det2["data"]["student"]["blockedStep"] == ""
    assert det2["data"]["student"]["steps"]["MATERIAL"] == "DONE"


def test_update_dorm(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ok = client.put(f"/api/v1/orientation/dorms/{ids['student']}", headers=auth_headers,
                    json={"building": "梧桐苑 2 号楼", "room": "2-105-1", "dormStatus": "ASSIGNED"}).json()
    assert ok["code"] == 0
    dorms = client.get("/api/v1/orientation/dorms", headers=auth_headers).json()
    row = dorms["data"]["items"][0]
    assert row["building"] == "梧桐苑 2 号楼"
    assert row["room"] == "2-105-1"
    assert row["dormStatus"] == "ASSIGNED"


def test_requires_login(client):
    assert client.get("/api/v1/orientation/dashboard").json()["code"] == 401001

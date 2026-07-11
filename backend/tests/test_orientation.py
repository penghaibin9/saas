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
                    json={"name": "新生乙", "admissionNo": "LQ2026999002", "classId": "NCL01"}).json()
    assert c["code"] == 0
    sid = c["data"]["id"]
    det = client.get(f"/api/v1/orientation/students/{sid}", headers=auth_headers).json()
    assert det["data"]["student"]["className"] == "软件2601班"
    dup = client.post("/api/v1/orientation/students", headers=auth_headers,
                      json={"name": "x", "admissionNo": "LQ2026999002"}).json()
    assert dup["code"] == 409001
    bad = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/orientation/students/{sid}/void", headers=auth_headers,
                     json={"reason": "录取信息重复，作废该记录"}).json()
    assert ok["code"] == 0


def test_student_batch_remind_and_assign(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    remind = client.post("/api/v1/orientation/students/batch-remind", headers=auth_headers,
                         json={"ids": [str(ids["student"])], "message": "请尽快完成报到"}).json()
    assert remind["code"] == 0 and remind["data"]["count"] == 1
    assign = client.post("/api/v1/orientation/students/batch-assign-counselor", headers=auth_headers,
                         json={"ids": [str(ids["student"])], "counselor": "王辅导"}).json()
    assert assign["code"] == 0 and assign["data"]["count"] == 1
    det = client.get(f"/api/v1/orientation/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["student"]["counselor"] == "王辅导"


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


def test_batch_closed_loop(client, auth_headers, db_mode):
    # 新建（草稿）
    c = client.post("/api/v1/orientation/batches", headers=auth_headers,
                    json={"batchName": "2026 级新生迎新", "batchNo": "ORI-2026",
                          "year": "2026", "startDate": "2026-09-01", "reportEndDate": "2026-09-15",
                          "plannedCount": 3200, "remark": "秋季迎新"}).json()
    assert c["code"] == 0
    bid = c["data"]["id"]
    # 编号唯一
    dup = client.post("/api/v1/orientation/batches", headers=auth_headers,
                      json={"batchName": "重复", "batchNo": "ORI-2026"}).json()
    assert dup["code"] != 0
    # 列表 + 脱敏无关，状态为草稿
    lst = client.get("/api/v1/orientation/batches", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    row = lst["data"]["items"][0]
    assert row["statusLabel"] == "草稿" and row["plannedCount"] == 3200
    # 非法流转：草稿不能直接结束
    bad = client.post(f"/api/v1/orientation/batches/{bid}/close", headers=auth_headers).json()
    assert bad["code"] != 0
    # 启用 草稿→进行中
    act = client.post(f"/api/v1/orientation/batches/{bid}/activate", headers=auth_headers).json()
    assert act["code"] == 0 and act["data"]["status"] == "ACTIVE"
    # 重复启用被拒
    assert client.post(f"/api/v1/orientation/batches/{bid}/activate", headers=auth_headers).json()["code"] != 0
    # 编辑
    upd = client.put(f"/api/v1/orientation/batches/{bid}", headers=auth_headers,
                     json={"plannedCount": 3300}).json()
    assert upd["code"] == 0
    assert client.get(f"/api/v1/orientation/batches/{bid}", headers=auth_headers).json()["data"]["plannedCount"] == 3300
    # 结束 进行中→已结束
    cl = client.post(f"/api/v1/orientation/batches/{bid}/close", headers=auth_headers).json()
    assert cl["code"] == 0 and cl["data"]["status"] == "CLOSED"
    # 已结束不可编辑
    assert client.put(f"/api/v1/orientation/batches/{bid}", headers=auth_headers,
                      json={"remark": "x"}).json()["code"] != 0
    # 审计留痕（BATCH 类型）
    logs = client.get("/api/v1/orientation/audit-logs?bizType=BATCH", headers=auth_headers).json()
    assert logs["code"] == 0 and logs["data"]["total"] >= 3


def test_verify_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    sid = ids["student"]
    # 不通过但原因太短 → 拒绝
    bad = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                      json={"passed": False, "reason": "x"}).json()
    assert bad["code"] != 0
    # 通过 → stage=PRE_STUDENT_VERIFIED，环节 INFO=DONE
    ok = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                     json={"passed": True}).json()
    assert ok["code"] == 0 and ok["data"]["stage"] == "PRE_STUDENT_VERIFIED"
    det = client.get(f"/api/v1/orientation/students/{sid}", headers=auth_headers).json()
    assert det["data"]["student"]["steps"]["INFO"] == "DONE"
    # 不通过（含原因） → 记录成功
    fail = client.post(f"/api/v1/orientation/students/{sid}/verify", headers=auth_headers,
                       json={"passed": False, "reason": "身份证与录取信息不一致"}).json()
    assert fail["code"] == 0
    # 审计留痕（核验动作 ≥ 2 条）
    logs = client.get("/api/v1/orientation/audit-logs?keyword=核验", headers=auth_headers).json()
    assert logs["code"] == 0 and logs["data"]["total"] >= 2


def test_checkin_point_crud(client, auth_headers, db_mode):
    c = client.post("/api/v1/orientation/checkin-points", headers=auth_headers,
                    json={"name": "东门报到点", "location": "东大门", "capacity": 300, "inCharge": "王老师"}).json()
    assert c["code"] == 0
    pid = c["data"]["id"]
    lst = client.get("/api/v1/orientation/checkin-points", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1 and lst["data"]["items"][0]["statusLabel"] == "启用"
    t = client.post(f"/api/v1/orientation/checkin-points/{pid}/toggle", headers=auth_headers).json()
    assert t["code"] == 0 and t["data"]["status"] == "DISABLED"
    u = client.put(f"/api/v1/orientation/checkin-points/{pid}", headers=auth_headers, json={"capacity": 500}).json()
    assert u["code"] == 0
    d = client.post(f"/api/v1/orientation/checkin-points/{pid}/delete", headers=auth_headers).json()
    assert d["code"] == 0
    assert client.get("/api/v1/orientation/checkin-points", headers=auth_headers).json()["data"]["total"] == 0


def test_flow_config(client, auth_headers, db_mode):
    lst = client.get("/api/v1/orientation/flow-config", headers=auth_headers).json()
    assert lst["code"] == 0 and len(lst["data"]) == 7  # 首次自动 seed 7 环节
    fid = lst["data"][3]["id"]
    upd = client.put(f"/api/v1/orientation/flow-config/{fid}", headers=auth_headers, json={"enabled": False}).json()
    assert upd["code"] == 0 and upd["data"]["enabled"] is False
    again = client.get("/api/v1/orientation/flow-config", headers=auth_headers).json()
    assert again["code"] == 0 and len(again["data"]) == 7  # 不重复 seed


def test_notice_send(client, auth_headers, db_mode):
    a = client.post("/api/v1/orientation/notices", headers=auth_headers,
                    json={"title": "报到须知", "channel": "INAPP"}).json()
    assert a["code"] == 0
    s1 = client.post(f"/api/v1/orientation/notices/{a['data']['id']}/send", headers=auth_headers).json()
    assert s1["code"] == 0 and s1["data"]["status"] == "SENT"
    b = client.post("/api/v1/orientation/notices", headers=auth_headers,
                    json={"title": "缴费提醒", "channel": "SMS"}).json()
    s2 = client.post(f"/api/v1/orientation/notices/{b['data']['id']}/send", headers=auth_headers).json()
    assert s2["code"] == 0 and s2["data"]["status"] == "DISABLED" and s2["data"]["failReason"]


def test_archive_run(client, auth_headers, db_mode):
    _seed(db_mode)
    c = client.post("/api/v1/orientation/archives", headers=auth_headers,
                    json={"archiveName": "2026 迎新归档", "scope": "全校"}).json()
    assert c["code"] == 0
    aid = c["data"]["id"]
    r = client.post(f"/api/v1/orientation/archives/{aid}/run", headers=auth_headers).json()
    assert r["code"] == 0 and r["data"]["status"] == "DONE" and r["data"]["itemCount"] >= 1
    assert client.post(f"/api/v1/orientation/archives/{aid}/run", headers=auth_headers).json()["code"] != 0


def test_student_xlsx_import_export(client, auth_headers, db_mode):
    import base64
    import io
    from openpyxl import Workbook

    tpl = client.get("/api/v1/orientation/students/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"
    adm = "LQ2026XLS0001"
    wb = Workbook()
    ws = wb.active
    ws.append(["录取编号", "姓名", "身份证号", "录取专业", "联系电话", "班级"])
    ws.append([adm, "导入测试生", "330102200801011234", "软件技术", "13800009999", "软件2601"])
    buf = io.BytesIO()
    wb.save(buf)
    up = client.post("/api/v1/orientation/students/import/xlsx", headers=auth_headers,
                     files={"file": ("s.xlsx", buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert up["code"] == 0 and up["data"]["validRows"] == 1
    ok = client.post("/api/v1/orientation/students/import/confirm", headers=auth_headers,
                     json={"rows": up["data"]["rows"]}).json()
    assert ok["code"] == 0 and ok["data"]["created"] == 1
    ex = client.post("/api/v1/orientation/students/export", headers=auth_headers,
                     json={"purpose": "新生台账导出测试备案", "keyword": adm}).json()
    assert ex["code"] == 0 and ex["data"]["filename"].endswith(".xlsx")
    assert base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"

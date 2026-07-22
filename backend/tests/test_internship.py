"""岗位实习域测试：列表/详情/看板 + 打卡异常处理闭环 + 周报批阅闭环 + 批次状态机闭环。"""
from __future__ import annotations

from datetime import datetime

import pytest

MAIN_TID = 1000000000000000001


def _seed(db_mode):
    """在 db_mode 库里为主租户学生插入实习记录 + 异常 + 周报 + 风险。返回 id 集。"""
    from app.db.session import get_sessionmaker
    from app.models import (AttendanceException, InternshipBatch, InternshipRecord,
                            RiskRecord, WeeklyReport)
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(tenant_id=MAIN_TID, batch_name="测试批次", batch_no="T-1",
                                start_date=datetime(2026, 3, 2), end_date=datetime(2026, 8, 28),
                                status="RUNNING")
        db.add(batch)
        db.flush()
        rec = InternshipRecord(tenant_id=MAIN_TID, student_id=db_mode["student"], batch_id=batch.id,
                               enterprise_name="测试企业", position_name="开发实习生",
                               advisor_name="刘强", status="ONBOARD", risk_level="HIGH",
                               intern_start_date=datetime(2026, 3, 2), intern_end_date=datetime(2026, 8, 28))
        db.add(rec)
        db.flush()
        exc = AttendanceException(tenant_id=MAIN_TID, internship_id=rec.id,
                                  exception_type="OUT_OF_RANGE", exception_date=datetime.utcnow(),
                                  distance_km=1.2, streak_days=3, status="PENDING_HANDLE")
        rep = WeeklyReport(tenant_id=MAIN_TID, internship_id=rec.id, week_number=3,
                           work_content="本周工作内容示例", word_count=1200, report_version=2,
                           submitted_at=datetime.utcnow(), status="PENDING_REVIEW")
        risk = RiskRecord(tenant_id=MAIN_TID, internship_id=rec.id, risk_code="INT-R07",
                          risk_title="连续打卡异常", risk_level="HIGH", source_module="system",
                          status="PROCESSING")
        db.add_all([exc, rep, risk])
        db.commit()
        return {"record": rec.id, "exception": exc.id, "report": rep.id}
    finally:
        db.close()


def test_dashboard(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    body = client.get("/api/v1/internship/dashboard", headers=auth_headers).json()
    assert body["code"] == 0
    labels = {s["label"]: s["value"] for s in body["data"]["stats"]}
    assert labels["在岗学生"] == "1"


def test_students_list_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/internship/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["statusLabel"] == "在岗中"
    det = client.get(f"/api/v1/internship/students/{ids['record']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["checkins"]) == 1 and len(det["data"]["reports"]) == 1


def test_students_filter_risk(client, auth_headers, db_mode):
    _seed(db_mode)
    hit = client.get("/api/v1/internship/students?riskLevel=HIGH", headers=auth_headers).json()
    assert hit["data"]["total"] == 1
    miss = client.get("/api/v1/internship/students?riskLevel=LOW", headers=auth_headers).json()
    assert miss["data"]["total"] == 0


def test_handle_exception_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    # 短意见拒绝
    bad = client.post(f"/api/v1/internship/exceptions/{ids['exception']}/handle",
                      headers=auth_headers, json={"action": "REASONABLE", "comment": "ok"}).json()
    assert bad["code"] == 422001
    # 转风险闭环
    ok = client.post(f"/api/v1/internship/exceptions/{ids['exception']}/handle",
                     headers=auth_headers, json={"action": "TO_RISK", "comment": "已核实并转风险跟进"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "COMPLETED"
    # 重复处理冲突
    again = client.post(f"/api/v1/internship/exceptions/{ids['exception']}/handle",
                        headers=auth_headers, json={"action": "REASONABLE", "comment": "重复处理意见"}).json()
    assert again["code"] == 409001
    # 转风险后应多出一条风险单
    risks = client.get("/api/v1/internship/risks", headers=auth_headers).json()
    assert risks["code"] == 0 and risks["data"]["total"] >= 2


def test_review_report_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    # 退回需原因≥5字
    bad = client.post(f"/api/v1/internship/reports/{ids['report']}/review",
                      headers=auth_headers, json={"action": "RETURN", "comment": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/internship/reports/{ids['report']}/review",
                     headers=auth_headers, json={"action": "APPROVE", "comment": ""}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    dup = client.post(f"/api/v1/internship/reports/{ids['report']}/review",
                      headers=auth_headers, json={"action": "APPROVE", "comment": ""}).json()
    assert dup["code"] == 409001


def test_exceptions_and_reports_list(client, auth_headers, db_mode):
    _seed(db_mode)
    exc = client.get("/api/v1/internship/exceptions?status=PENDING_HANDLE", headers=auth_headers).json()
    assert exc["code"] == 0 and exc["data"]["total"] == 1
    rep = client.get("/api/v1/internship/reports?status=PENDING_REVIEW", headers=auth_headers).json()
    assert rep["code"] == 0 and rep["data"]["total"] == 1


def test_batch_rejects_evaluation_weights_not_summing_to_one(client, auth_headers, db_mode):
    """评价三项权重之和必须为 1.0（IX-E2E-001）。"""
    bad = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": "权重错误批次", "batchNo": "INT-BAD-W",
        "startDate": "2026-03-02", "endDate": "2026-08-28",
        "rules": {"evaluation": {"enterpriseWeight": 0.5, "teacherWeight": 0.5, "selfWeight": 0.5}},
    }).json()
    assert bad["code"] != 0
    ok = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": "权重正确批次", "batchNo": "INT-OK-W",
        "startDate": "2026-03-02", "endDate": "2026-08-28",
        "rules": {"evaluation": {"enterpriseWeight": 0.4, "teacherWeight": 0.4, "selfWeight": 0.2}},
    }).json()
    assert ok["code"] == 0


def test_batch_closed_loop(client, auth_headers, db_mode):
    # 新建（草稿），服务端应自动补默认阶段/规则
    c = client.post("/api/v1/internship/batches", headers=auth_headers,
                    json={"batchName": "2026 春季岗位实习", "batchNo": "INT-2026S",
                          "academicYear": "2025-2026", "term": "第二学期",
                          "startDate": "2026-03-02", "endDate": "2026-08-28",
                          "plannedCount": 120, "remark": "春季批次"}).json()
    assert c["code"] == 0
    bid = c["data"]["id"]
    det0 = client.get(f"/api/v1/internship/batches/{bid}", headers=auth_headers).json()
    assert det0["code"] == 0 and len(det0["data"]["stages"]) == 3
    assert det0["data"]["rules"]["checkin"]["geofenceRadiusM"] == 500
    dup = client.post("/api/v1/internship/batches", headers=auth_headers,
                      json={"batchName": "重复批次", "batchNo": "INT-2026S"}).json()
    assert dup["code"] != 0
    lst = client.get("/api/v1/internship/batches", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    row = lst["data"]["items"][0]
    assert row["statusLabel"] == "草稿" and row["plannedCount"] == 120 and row["actualCount"] == 0
    assert client.post(f"/api/v1/internship/batches/{bid}/close", headers=auth_headers).json()["code"] != 0
    assert client.post(f"/api/v1/internship/batches/{bid}/archive", headers=auth_headers).json()["code"] != 0
    # 草稿态改规则（局部合并）
    upd0 = client.put(f"/api/v1/internship/batches/{bid}", headers=auth_headers,
                      json={"rules": {"checkin": {"geofenceRadiusM": 800}}}).json()
    assert upd0["code"] == 0
    det_r = client.get(f"/api/v1/internship/batches/{bid}", headers=auth_headers).json()["data"]
    assert det_r["rules"]["checkin"]["geofenceRadiusM"] == 800
    assert det_r["rules"]["weeklyReport"]["minWordCount"] == 800
    act = client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()
    assert act["code"] == 0 and act["data"]["status"] == "RUNNING"
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()["code"] != 0
    assert client.post(f"/api/v1/internship/batches/{bid}/void", headers=auth_headers,
                       json={"reason": "误建批次需要作废"}).json()["code"] != 0
    # 启用后不可改规则，可改计划人数
    assert client.put(f"/api/v1/internship/batches/{bid}", headers=auth_headers,
                      json={"rules": {"checkin": {"geofenceRadiusM": 900}}}).json()["code"] != 0
    upd = client.put(f"/api/v1/internship/batches/{bid}", headers=auth_headers,
                     json={"plannedCount": 150}).json()
    assert upd["code"] == 0
    det1 = client.get(f"/api/v1/internship/batches/{bid}", headers=auth_headers).json()["data"]
    assert det1["plannedCount"] == 150
    assert det1["rules"]["checkin"]["geofenceRadiusM"] == 800
    cl = client.post(f"/api/v1/internship/batches/{bid}/close", headers=auth_headers).json()
    assert cl["code"] == 0 and cl["data"]["status"] == "CLOSED"
    assert client.put(f"/api/v1/internship/batches/{bid}", headers=auth_headers,
                      json={"remark": "x"}).json()["code"] != 0
    ar = client.post(f"/api/v1/internship/batches/{bid}/archive", headers=auth_headers).json()
    assert ar["code"] == 0 and ar["data"]["status"] == "ARCHIVED"
    assert client.post(f"/api/v1/internship/batches/{bid}/archive", headers=auth_headers).json()["code"] != 0
    det2 = client.get(f"/api/v1/internship/batches/{bid}", headers=auth_headers).json()["data"]
    assert len(det2["auditTrail"]) >= 4
    import base64
    exp = client.post("/api/v1/internship/batches/export", headers=auth_headers).json()
    assert exp["code"] == 0 and exp["data"]["rowCount"] >= 1
    assert exp["data"]["filename"].endswith(".xlsx")
    assert base64.b64decode(exp["data"]["contentBase64"])[:2] == b"PK"


def test_batch_void_only_draft(client, auth_headers, db_mode):
    c = client.post("/api/v1/internship/batches", headers=auth_headers,
                    json={"batchName": "待作废批次", "batchNo": "INT-VOID-1"}).json()
    bid = c["data"]["id"]
    bad = client.post(f"/api/v1/internship/batches/{bid}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/internship/batches/{bid}/void", headers=auth_headers,
                     json={"reason": "批次信息录入有误，作废重建"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "VOIDED"
    assert client.put(f"/api/v1/internship/batches/{bid}", headers=auth_headers,
                      json={"remark": "x"}).json()["code"] != 0


def test_requires_login(client):
    assert client.get("/api/v1/internship/dashboard").json()["code"] == 401001

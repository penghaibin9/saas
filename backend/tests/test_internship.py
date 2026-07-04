"""岗位实习域测试：列表/详情/看板 + 打卡异常处理闭环 + 周报批阅闭环 + 规则校验。"""
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


def test_requires_login(client):
    assert client.get("/api/v1/internship/dashboard").json()["code"] == 401001

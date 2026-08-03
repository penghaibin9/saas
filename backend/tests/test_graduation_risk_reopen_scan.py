"""第5批：风险案重开生命周期 + 扫描聚合（无学生级 N+1）。"""
from __future__ import annotations

from conftest import make_org_class

import uuid

from sqlalchemy import event, select

from app.db.session import get_sessionmaker
from app.models import GraduationRiskCase, GraduationStudent

RISK = "/api/v1/graduation/gd-risks"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"
BATCH = "/api/v1/graduation/batches"


def _uniq(prefix="B5"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(graduation_client, h):
    return graduation_client.post(BATCH, headers=h, json={
        "batchName": _uniq("批"), "batchNo": _uniq("BN"),
        "gradeYear": "2026届", "plannedCount": 50,
    }).json()["data"]["id"]


def _gd_student(graduation_client, h, bid, stage="TOPIC_SELECTING"):
    sid = graduation_client.post(STU, headers=h, json={
        "studentNo": _uniq("S"), "realName": _uniq("生"), "classId": make_org_class(),
    }).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        s.stage = stage
        s.topic_id = None
        db.commit()
    finally:
        db.close()
    return gid


def test_scan_creates_and_reopens_same_uk_row(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    gid = _gd_student(graduation_client, h, bid, stage="TOPIC_SELECTING")

    r1 = graduation_client.post(f"{RISK}/scan", headers=h, params={"batchId": bid})
    assert r1.json()["code"] == 0, r1.json()
    assert r1.json()["data"]["newCasesCreated"] >= 1

    db = get_sessionmaker()()
    try:
        cases = db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(gid),
            GraduationRiskCase.risk_code == "GD-R01",
            GraduationRiskCase.is_deleted.is_(False),
        )).all()
        assert len(cases) == 1
        case = cases[0]
        case_id = case.id
        case.status = "CLOSED"
        case.close_reason = "已临时处理完毕测试"
        case.closed_at = case.detected_at
        db.commit()
    finally:
        db.close()

    r2 = graduation_client.post(f"{RISK}/scan", headers=h, params={"batchId": bid})
    assert r2.json()["code"] == 0, r2.json()
    assert r2.json()["data"]["reopenedCases"] >= 1

    db = get_sessionmaker()()
    try:
        cases = db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(gid),
            GraduationRiskCase.risk_code == "GD-R01",
            GraduationRiskCase.is_deleted.is_(False),
        )).all()
        assert len(cases) == 1
        assert cases[0].id == case_id
        assert cases[0].status == "OPEN"
        assert int(cases[0].reopen_count or 0) >= 1
        assert cases[0].last_reopened_at is not None
    finally:
        db.close()

    last = graduation_client.get(f"{RISK}/last-scan", headers=h, params={"batchId": bid})
    assert last.json()["code"] == 0
    assert last.json()["data"]["lastScanAt"]


def test_scan_uses_batch_queries_not_per_student_n_plus_one(graduation_client, auth_headers, db_mode):
    """十余名学生扫描时，附属表应聚合查询，而非每生一遍。"""
    h = auth_headers
    bid = _batch(graduation_client, h)
    for _ in range(12):
        _gd_student(graduation_client, h, bid, stage="TOPIC_SELECTING")

    db = get_sessionmaker()()
    bind = db.get_bind()
    db.close()

    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(str(statement))

    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    try:
        r = graduation_client.post(f"{RISK}/scan", headers=h, params={"batchId": bid})
        assert r.json()["code"] == 0, r.json()
        data = r.json()["data"]
        assert data["scannedStudents"] >= 12
        assert data.get("elapsedMs") is not None
        taskbook_selects = [
            s for s in statements
            if "t_gd_taskbook" in s.lower() and s.lstrip().upper().startswith("SELECT")
        ]
        assert len(taskbook_selects) <= 3, f"taskbook queries too many: {len(taskbook_selects)}"
        guidance_selects = [
            s for s in statements
            if "t_gd_guidance" in s.lower() and s.lstrip().upper().startswith("SELECT")
        ]
        assert len(guidance_selects) <= 3, f"guidance queries too many: {len(guidance_selects)}"
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)

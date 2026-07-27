"""毕业设计 · 第2批：风险扫描 / 批量归档批次范围、预检查与审计。

覆盖：扫描限定批次与数据范围；批量生成/备案须 batchId；preview 与执行数量一致；
材料不齐/风险未关闭正确跳过；审计含批次与影响数量；非法/缺失 batchId 拒绝。
"""
from __future__ import annotations

from conftest import make_org_class

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

GD_STU = "/api/v1/graduation/gd-students"
GD_BATCH = "/api/v1/graduation/batches"
GD_RISK = "/api/v1/graduation/gd-risks"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
STU = "/api/v1/students"
MAIN = 1000000000000000001


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(client, h):
    r = client.post(GD_BATCH, headers=h, json={
        "batchName": _uniq("批次"), "batchNo": _uniq("GD-B2"),
        "gradeYear": "2026届", "plannedCount": 50,
    }).json()
    assert r["code"] == 0, r
    return r["data"]["id"], r["data"]["batchName"]


def _student(client, h, name=None):
    sno = _uniq("S")
    r = client.post(STU, headers=h, json={
        "studentNo": sno, "realName": name or f"学生{sno[-4:]}",
        "classId": make_org_class(),
    }).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _record(client, h, sid, batch_id, college_id=None):
    r = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": batch_id}).json()
    assert r["code"] == 0, r
    gid = r["data"]["id"]
    if college_id is not None:
        from app.db.session import get_sessionmaker
        from app.models import GraduationStudent
        db = get_sessionmaker()()
        try:
            stu = db.get(GraduationStudent, int(gid))
            stu.college_id = str(college_id)
            # 未选题 → 扫描可命中 GD-R01
            stu.stage = "TOPIC_SELECTING"
            stu.topic_id = None
            db.commit()
            db.refresh(stu)
            assert str(stu.college_id) == str(college_id)
            assert str(stu.batch_id) == str(batch_id)
        finally:
            db.close()
    return gid


def _college_headers(college_id="10"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-college-{college_id}", "realName": "学院管理员甲",
        "userType": "TEACHER", "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "GD_COLLEGE_ADMIN",
        "collegeId": str(college_id), "collegeIds": [str(college_id)],
    })}


def test_scan_requires_batch_id(client, auth_headers, db_mode):
    r = client.post(f"{GD_RISK}/scan", headers=auth_headers).json()
    assert r["code"] != 0
    bad = client.post(f"{GD_RISK}/scan", headers=auth_headers, params={"batchId": "abc"})
    assert bad.status_code != 500
    assert bad.status_code == 422 or bad.json().get("code") == 422001


def test_scan_2026_does_not_create_2025_risks(client, auth_headers, db_mode):
    h = auth_headers
    b2026, name2026 = _batch(client, h)
    b2025, _ = _batch(client, h)
    g26 = _record(client, h, _student(client, h, "扫描2026生"), b2026, college_id=None)
    g25 = _record(client, h, _student(client, h, "扫描2025生"), b2025, college_id=None)

    # 确保两人都是未选题
    from app.db.session import get_sessionmaker
    from app.models import GraduationRiskCase, GraduationStudent
    db = get_sessionmaker()()
    try:
        for gid in (g26, g25):
            s = db.get(GraduationStudent, int(gid))
            s.stage = "TOPIC_SELECTING"
            s.topic_id = None
        db.commit()
    finally:
        db.close()

    scan = client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": b2026}).json()
    assert scan["code"] == 0, scan
    assert scan["data"]["batchId"] == str(b2026)
    assert scan["data"]["batchName"] == name2026
    assert scan["data"]["scannedStudents"] >= 1
    assert scan["data"]["newCasesCreated"] >= 1
    assert "scopeSummary" in scan["data"] and scan["data"]["operator"]

    db = get_sessionmaker()()
    try:
        r26 = db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(g26),
            GraduationRiskCase.risk_code == "GD-R01",
            GraduationRiskCase.is_deleted.is_(False))).all()
        r25 = db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(g25),
            GraduationRiskCase.risk_code == "GD-R01",
            GraduationRiskCase.is_deleted.is_(False))).all()
        assert len(r26) >= 1
        assert len(r25) == 0
    finally:
        db.close()


def test_college_admin_scan_does_not_create_other_college_risks(client, auth_headers, db_mode):
    h = auth_headers
    bid, _ = _batch(client, h)
    g_in = _record(client, h, _student(client, h, "本院生"), bid, college_id=10)
    g_out = _record(client, h, _student(client, h, "外院生"), bid, college_id=99)

    from app.db.session import get_sessionmaker
    from app.models import GraduationRiskCase, GraduationStudent
    db = get_sessionmaker()()
    try:
        for gid in (g_in, g_out):
            s = db.get(GraduationStudent, int(gid))
            s.stage = "TOPIC_SELECTING"
            s.topic_id = None
        db.commit()
    finally:
        db.close()

    ch = _college_headers("10")
    scan = client.post(f"{GD_RISK}/scan", headers=ch, params={"batchId": bid}).json()
    assert scan["code"] == 0, scan
    assert scan["data"]["scannedStudents"] == 1, scan["data"]
    assert scan["data"]["skippedStudents"] >= 1, scan["data"]
    assert "10" in (scan["data"].get("scopeSummary") or ""), scan["data"]

    db = get_sessionmaker()()
    try:
        assert db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(g_in),
            GraduationRiskCase.risk_code == "GD-R01")).first() is not None
        assert db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.gd_student_id == int(g_out),
            GraduationRiskCase.risk_code == "GD-R01")).first() is None
    finally:
        db.close()


def test_batch_ops_require_batch_id(client, auth_headers, db_mode):
    h = auth_headers
    for path in (
        f"{GD_ARCHIVE}/batch-generate",
        f"{GD_ARCHIVE}/batch-file",
        f"{GD_ARCHIVE}/batch-generate/preview",
        f"{GD_ARCHIVE}/batch-file/preview",
    ):
        r = client.post(path, headers=h).json()
        assert r["code"] != 0, path


def test_batch_generate_only_current_batch_and_preview_matches(client, auth_headers, db_mode):
    h = auth_headers
    b1, name1 = _batch(client, h)
    b2, _ = _batch(client, h)
    g1 = _record(client, h, _student(client, h, "归档甲"), b1)
    g2 = _record(client, h, _student(client, h, "归档乙"), b2)

    prev = client.post(f"{GD_ARCHIVE}/batch-generate/preview", headers=h,
                       params={"batchId": b1}).json()
    assert prev["code"] == 0, prev
    assert prev["data"]["batchId"] == str(b1)
    assert prev["data"]["batchName"] == name1
    assert prev["data"]["candidateCount"] == 1
    # 新建学生材料不齐 → executable 0，skipped 含 missing_materials
    assert prev["data"]["executableCount"] == 0
    assert prev["data"]["skippedCount"] == 1
    reasons = {x["reason"]: x["count"] for x in prev["data"]["skipReasons"]}
    assert reasons.get("missing_materials", 0) >= 1

    gen = client.post(f"{GD_ARCHIVE}/batch-generate", headers=h, params={"batchId": b1}).json()
    assert gen["code"] == 0, gen
    assert gen["data"]["batchId"] == str(b1)
    assert gen["data"]["skipped"] == prev["data"]["skippedCount"]
    assert gen["data"]["submitted"] == prev["data"]["executableCount"]

    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord
    db = get_sessionmaker()()
    try:
        a1 = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.gd_student_id == int(g1),
            GraduationArchiveRecord.is_deleted.is_(False))).first()
        a2 = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.gd_student_id == int(g2),
            GraduationArchiveRecord.is_deleted.is_(False))).first()
        assert a1 is not None
        assert a1.status == "PENDING_SUBMIT"
        assert a2 is None  # 未处理其他批次
    finally:
        db.close()


def test_batch_file_preview_matches_and_skips_open_risk(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationRiskCase, GraduationStudent

    h = auth_headers
    bid, bname = _batch(client, h)
    gid = _record(client, h, _student(client, h, "备案风险生"), bid)

    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        a = GraduationArchiveRecord(
            tenant_id=stu.tenant_id, gd_student_id=stu.id, status="SUBMITTED",
            missing_items=[], checklist_json=[],
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(a)
        db.add(GraduationRiskCase(
            tenant_id=stu.tenant_id, risk_code="GD-R01", risk_name="未选题",
            gd_student_id=stu.id, level="MEDIUM", status="OPEN",
            detected_at=datetime.now(timezone.utc),
        ))
        db.commit()
    finally:
        db.close()

    prev = client.post(f"{GD_ARCHIVE}/batch-file/preview", headers=h,
                       params={"batchId": bid}).json()
    assert prev["code"] == 0, prev
    assert prev["data"]["batchName"] == bname
    assert prev["data"]["candidateCount"] == 1
    assert prev["data"]["executableCount"] == 0
    reasons = {x["reason"]: x["count"] for x in prev["data"]["skipReasons"]}
    assert reasons.get("open_risks", 0) >= 1

    filed = client.post(f"{GD_ARCHIVE}/batch-file", headers=h,
                        params={"batchId": bid}, json={}).json()
    assert filed["code"] == 0
    assert filed["data"]["filed"] == prev["data"]["executableCount"]
    assert filed["data"]["skipped"] == prev["data"]["skippedCount"]
    assert filed["data"]["batchId"] == str(bid)

    db = get_sessionmaker()()
    try:
        a = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.gd_student_id == int(gid))).first()
        assert a.status == "SUBMITTED"  # 因开放风险未备案
    finally:
        db.close()


def test_scan_audit_contains_batch_and_counts(client, auth_headers, db_mode):
    h = auth_headers
    bid, bname = _batch(client, h)
    _record(client, h, _student(client, h, "审计扫描生"), bid)
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    db = get_sessionmaker()()
    try:
        # 取该批次唯一学生改未选题
        rows = db.scalars(select(GraduationStudent).where(
            GraduationStudent.batch_id == int(bid))).all()
        for s in rows:
            s.stage = "TOPIC_SELECTING"
            s.topic_id = None
        db.commit()
    finally:
        db.close()

    scan = client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid}).json()
    assert scan["code"] == 0
    assert scan["data"]["batchId"] == str(bid)
    assert scan["data"]["batchName"] == bname
    assert "scannedStudents" in scan["data"]
    assert "newCasesCreated" in scan["data"]
    assert "existingCases" in scan["data"]
    assert "skippedStudents" in scan["data"]
    assert scan["data"]["operator"]
    assert scan["data"]["scopeSummary"]

    audit = client.get("/api/v1/graduation/audit-logs", headers=h,
                       params={"bizType": "RISK", "pageSize": 20}).json()
    assert audit["code"] == 0
    hit = next((x for x in audit["data"]["items"]
                if x.get("action") == "扫描毕设风险" and str(bid) in (x.get("detail") or "")), None)
    assert hit is not None
    assert bname in (hit.get("detail") or "")

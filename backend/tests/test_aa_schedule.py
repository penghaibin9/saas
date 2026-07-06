"""13B-P4 课表 · 端到端（三重冲突检测 + 单双周 + 三视图 + 发布）。

S1 教师冲突409；S2 班级冲突409；S3 教室冲突409；S4 单双周不冲突；S5 导入带冲突清单；
S6 发布通知；S7 三视图；S8 作废重发。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="SC001", real_name="课表甲", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"class": a.id, "student": s.id}
    db.commit()
    db.close()
    return ids


def _batch(client, hdr):
    return client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": "1"}).json()["data"]["batchId"]


def _item(client, hdr, bid, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "T1", "teacherName": "王老师", "classId": "100", "className": "软件2601",
            "classroom": "A101", "courseName": "高数", **kw}
    return client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)


def test_s1_teacher_conflict(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    assert _item(client, hdr, bid).status_code == 200
    # 同教师同时段，换班换教室 → 教师冲突
    r = _item(client, hdr, bid, classId="200", classroom="B202")
    assert r.status_code == 409 and "TEACHER" in r.json()["message"]


def test_s2_class_conflict(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _item(client, hdr, bid)
    r = _item(client, hdr, bid, teacherKey="T2", teacherName="李老师", classroom="B202")
    assert r.status_code == 409 and "CLASS" in r.json()["message"]


def test_s3_classroom_conflict(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _item(client, hdr, bid)
    r = _item(client, hdr, bid, teacherKey="T2", teacherName="李老师", classId="200", className="X")
    assert r.status_code == 409 and "CLASSROOM" in r.json()["message"]


def test_s4_parity_no_conflict(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    # 单周排 T1，双周同时段同教师排 → 不冲突（单双周错开）
    assert _item(client, hdr, bid, weekParity="ODD").status_code == 200
    assert _item(client, hdr, bid, weekParity="EVEN").status_code == 200
    # 但单周再排同教师 → 冲突
    assert _item(client, hdr, bid, weekParity="ODD").status_code == 409


def test_s5_import_reports_conflicts(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    r = client.post(f"{BASE}/schedule-batches/{bid}/import", headers=hdr, json={"items": [
        {"weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "100", "classroom": "A101"},
        {"weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "200", "classroom": "B202"},  # 教师冲突
    ]}).json()
    assert r["data"]["imported"] == 1 and len(r["data"]["conflicts"]) == 1


def test_s6_publish_notifies(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _item(client, hdr, bid)
    r = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr).json()
    assert r["data"]["status"] == "PUBLISHED" and r["data"]["notified"] >= 1


def test_s7_three_views(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _item(client, hdr, bid, classId=str(ids["class"]))
    cv = client.get(f"{BASE}/schedule-batches/{bid}/class-view?classId={ids['class']}", headers=hdr).json()
    tv = client.get(f"{BASE}/schedule-batches/{bid}/teacher-view?teacherKey=T1", headers=hdr).json()
    sv = client.get(f"{BASE}/schedule-batches/{bid}/student-view?studentId={ids['student']}", headers=hdr).json()
    assert len(cv["data"]["items"]) == 1 and len(tv["data"]["items"]) == 1
    assert len(sv["data"]["items"]) == 1  # 学生按行政班推导出本班课表


def test_s8_void_reissue(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _batch(client, hdr)
    _item(client, hdr, bid)
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    r = client.post(f"{BASE}/schedule-batches/{bid}/void-reissue", headers=hdr,
                    json={"reason": "临时调整教学安排"}).json()
    assert r["data"]["status"] == "ARCHIVED"

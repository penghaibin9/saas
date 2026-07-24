"""班级辅导员真实责任关系：MySQL db_mode 下的主责、交接、空缺、范围与乐观锁。"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope, User
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="责任关系学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="责任关系专业", status="ACTIVE")
    db.add(major); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="责任2601", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=major.id, class_name="责任2602", status="ACTIVE")
    db.add_all([a, b]); db.flush()
    db.add_all([
        StudentProfile(tenant_id=TID, student_no="CA001", real_name="学生甲", class_id=a.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE"),
        StudentProfile(tenant_id=TID, student_no="CA002", real_name="学生乙", class_id=a.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE"),
        StudentProfile(tenant_id=TID, student_no="CB001", real_name="学生丙", class_id=b.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE"),
    ])
    users = []
    for login, name in (("ca_counselor_1", "辅导员一"), ("ca_counselor_2", "辅导员二"),
                        ("ca_counselor_3", "辅导员三")):
        u = User(tenant_id=TID, login_name=login, real_name=name, password_hash="x",
                 user_type="TEACHER", status="ACTIVE")
        db.add(u); users.append(u)
    db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="责任2601",
                               status="ACTIVE"))
    db.commit()
    result = {"a": a.id, "b": b.id, "u1": users[0].id, "u2": users[1].id, "u3": users[2].id}
    db.close()
    return result


def _assign(client, hdr, class_id, user_id, duty="PRIMARY", **extra):
    return client.post(f"{BASE}/counselor-assignments", headers=hdr, json={
        "classId": class_id, "userId": user_id, "dutyType": duty, **extra})


def test_primary_unique_and_workload_ledger(client, db_mode):
    ids, hdr = _seed(db_mode), _hdr(client, "school_admin01")
    first = _assign(client, hdr, ids["a"], ids["u1"]).json()["data"]
    assert first["dutyType"] == "PRIMARY" and first["counselorName"] == "辅导员一"
    _assign(client, hdr, ids["a"], ids["u2"], "CO").raise_for_status()
    second = _assign(client, hdr, ids["a"], ids["u3"]).json()["data"]
    rows = client.get(f"{BASE}/counselor-assignments?classId={ids['a']}", headers=hdr).json()["data"]["items"]
    assert len([x for x in rows if x["status"] == "ACTIVE" and x["dutyType"] == "PRIMARY"]) == 1
    assert next(x for x in rows if x["id"] == first["id"])["status"] == "ENDED"
    ledger = client.get(f"{BASE}/counselor-ledger", headers=hdr).json()["data"]["items"]
    u3 = next(x for x in ledger if x["userId"] == str(ids["u3"]))
    assert u3["classCount"] == 1 and u3["studentCount"] == 2 and u3["primaryCount"] == 1
    assert second["userId"] == str(ids["u3"])


def test_handover_ends_old_primary_and_preserves_history(client, db_mode):
    ids, hdr = _seed(db_mode), _hdr(client, "school_admin01")
    original = _assign(client, hdr, ids["a"], ids["u1"]).json()["data"]
    moved = client.post(f"{BASE}/classes/{ids['a']}/counselor-handover", headers=hdr, json={
        "fromUserId": ids["u1"], "toUserId": ids["u2"], "reason": "调岗交接", "version": original["version"]}).json()["data"]
    assert moved["dutyType"] == "PRIMARY" and moved["handoverFromUserId"] == str(ids["u1"])
    rows = client.get(f"{BASE}/counselor-assignments?classId={ids['a']}", headers=hdr).json()["data"]["items"]
    old = next(x for x in rows if x["id"] == original["id"])
    assert old["status"] == "ENDED" and old["reason"] == "调岗交接"


def test_temp_requires_end_and_vacancy_after_primary_end(client, db_mode):
    ids, hdr = _seed(db_mode), _hdr(client, "school_admin01")
    assert _assign(client, hdr, ids["a"], ids["u1"], "TEMP").status_code == 400
    primary = _assign(client, hdr, ids["a"], ids["u1"]).json()["data"]
    ended = client.post(f"{BASE}/counselor-assignments/{primary['id']}/end", headers=hdr,
                        json={"reason": "离职", "version": primary["version"]})
    assert ended.status_code == 200
    vacant = client.get(f"{BASE}/counselor-vacancies", headers=hdr).json()["data"]["items"]
    assert str(ids["a"]) in {x["classId"] for x in vacant}


def test_counselor_cannot_change_out_of_scope_class_and_stale_version_conflicts(client, db_mode):
    ids, admin = _seed(db_mode), _hdr(client, "school_admin01")
    denied = _assign(client, _hdr(client, "counselor01"), ids["b"], ids["u1"])
    assert denied.status_code == 403 and denied.json()["bizCode"] == "NO_DATA_SCOPE"
    created = _assign(client, admin, ids["a"], ids["u1"]).json()["data"]
    stale = client.post(f"{BASE}/counselor-assignments/{created['id']}/end", headers=admin,
                        json={"reason": "并发旧版本", "version": created["version"] + 1})
    assert stale.status_code == 409 and stale.json()["bizCode"] == "APPROVAL_VERSION_CONFLICT"

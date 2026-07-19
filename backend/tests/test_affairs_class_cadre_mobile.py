"""学工中心 · 移动端班干部任命/免去（新聚合 affairs_class_students 首次覆盖 + 全流程复测）。
全部经 HTTP client 走真库(db_mode)。PC 端既有 test_affairs_dashboard.py 已覆盖
list_cadres/add_cadre 本身的越权拦截；本文件专门覆盖移动端新增的"班级学生名单"聚合函数
（此前完全没有测试触碰过），以及整条 mobile 链路（我的班级→该班学生→任命→列表→免去）。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_classes(db_mode):
    """2 班 + 5 生（A 班 3 人/B 班 2 人）+ 辅导员范围限定 A 班。返回 {A, B, a_students}。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2201", grade="2022", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2202", grade="2022", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    a_students = []
    for i in range(3):
        s = StudentProfile(tenant_id=TID, student_no=f"MA{i:03d}", real_name=f"甲生{i}",
                           class_id=a.id, current_stage="ORIENTATION",
                           student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        a_students.append(s.id)
    for i in range(2):
        db.add(StudentProfile(tenant_id=TID, student_no=f"MB{i:03d}", real_name=f"乙生{i}",
                              class_id=b.id, current_stage="ORIENTATION",
                              student_status="NORMAL", status="ACTIVE"))
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2201",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "a_students": a_students}
    db.close()
    return ids


def test_my_classes_scope(client, db_mode):
    """辅导员的「我的班级」只返回 A 班，不含无授权的 B 班。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    r = client.get(f"{MOB}/teacher/affairs/classes", headers=hdr).json()
    assert r["code"] == 0
    class_ids = {c["classId"] for c in r["data"]["list"]}
    assert str(ids["A"]) in class_ids
    assert str(ids["B"]) not in class_ids


def test_class_students_scope_matches_cadre_appoint_scope(client, db_mode):
    """核心：班级学生名单聚合函数（此前无测试覆盖）与 add_cadre 内部范围校验完全同口径——
    A 班学生名单可查（3人），越权查 B 班学生名单应 403，且 403 场景与 PC 端
    test_counselor_cross_class_403 验证的 add_cadre 越权拦截一致（不会出现"选得到、任命却403"）。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    ok = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/students", headers=hdr).json()
    assert ok["code"] == 0
    assert len(ok["data"]["list"]) == 3
    assert {s["studentId"] for s in ok["data"]["list"]} == {str(sid) for sid in ids["a_students"]}

    forbidden = client.get(f"{MOB}/teacher/affairs/classes/{ids['B']}/students", headers=hdr)
    assert forbidden.status_code == 403
    assert forbidden.json()["bizCode"] == "NO_DATA_SCOPE"


def test_appoint_list_remove_full_flow_via_mobile(client, db_mode):
    """移动端完整链路：选班级→选学生→任命→列表可见(含姓名学号补全)→免去。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    sid = ids["a_students"][0]

    appoint = client.post(f"{MOB}/teacher/affairs/classes/{ids['A']}/cadres", headers=hdr,
                          json={"studentId": str(sid), "position": "MONITOR", "termCode": "2026-1"})
    assert appoint.status_code == 200 and appoint.json()["code"] == 0
    cadre_id = appoint.json()["data"]["cadreId"]

    lst = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/cadres", headers=hdr).json()
    assert len(lst["data"]["list"]) == 1
    row = lst["data"]["list"][0]
    assert row["position"] == "MONITOR"
    assert row["studentName"] == "甲生0"  # mobile 层补全的姓名（PC _cadre_row 本身不含）
    assert row["studentNo"] == "MA000"

    # 同班同职务重复任命 → 409（复用 PC add_cadre 的重复校验）
    dup = client.post(f"{MOB}/teacher/affairs/classes/{ids['A']}/cadres", headers=hdr,
                      json={"studentId": str(sid), "position": "MONITOR"})
    assert dup.status_code == 409

    remove = client.post(f"{MOB}/teacher/affairs/classes/cadres/{cadre_id}/remove", headers=hdr,
                         json={"reason": "换届改选"})
    assert remove.status_code == 200 and remove.json()["data"]["status"] == "REMOVED"
    lst2 = client.get(f"{MOB}/teacher/affairs/classes/{ids['A']}/cadres", headers=hdr).json()
    assert len(lst2["data"]["list"]) == 0  # list_cadres 只返回在任(未软删)记录


def test_cross_class_appoint_403_via_mobile(client, db_mode):
    """越权：辅导员(范围=A班)对 B 班学生任命班干部 → 403（复用 add_cadre 内部 _class_in_scope_or_403）。"""
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    r = client.post(f"{MOB}/teacher/affairs/classes/{ids['B']}/cadres", headers=hdr,
                    json={"studentId": "1", "position": "STUDY"})
    assert r.status_code == 403

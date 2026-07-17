"""波5 课堂考勤（移动端首创）端到端：新建场次(按行政班圈定名单)→标记→提交→范围收敛。"""
from __future__ import annotations

BASE = "/api/v1/mobile/teacher/academic/attendance"
MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _teacher_token(real_name="王老师", tenant_id=MAIN, tid="demo", role="ACADEMIC_TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "MP"})}


def _seed_class(n_students=3, tenant_id=MAIN):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    try:
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="考勤测2601",
                        grade="2026", status="ACTIVE")
        db.add(c); db.flush()
        cid = c.id
        for i in range(n_students):
            db.add(StudentProfile(tenant_id=tenant_id, student_no=f"AT{i:04d}",
                                  real_name=f"考勤生{i}", class_id=cid,
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        return cid
    finally:
        db.close()


def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):
    """新建考勤场次现要求调用者对该行政班确有教学任务归属（P0 越权修复），测试需先建好教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    try:
        db.add(AaTeachingTask(tenant_id=tenant_id, batch_id=1, course_id=1, class_id=class_id,
                              teacher_key=teacher_key, status="PENDING_ASSIGN"))
        db.commit()
    finally:
        db.close()


def test_attendance_full_flow(client, db_mode):
    cid = _seed_class(n_students=3)
    _seed_teaching_task(cid, "周老师")
    hdr = _teacher_token("周老师")
    r = client.post(f"{BASE}/sessions", headers=hdr,
                    json={"classId": cid, "courseName": "高等数学", "sessionDate": "2026-07-15"}).json()
    assert r["code"] == 0
    sess = r["data"]
    assert sess["totalCount"] == 3 and sess["presentCount"] == 3 and sess["status"] == "DRAFT"
    sid = sess["sessionId"]

    detail = client.get(f"{BASE}/sessions/{sid}", headers=hdr).json()["data"]
    assert len(detail["items"]) == 3
    stu0 = detail["items"][0]
    assert stu0["status"] == "PRESENT"

    marked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                         json={"studentId": stu0["studentId"], "status": "ABSENT"}).json()["data"]
    assert marked["absentCount"] == 1 and marked["presentCount"] == 2

    submitted = client.post(f"{BASE}/sessions/{sid}/submit", headers=hdr).json()["data"]
    assert submitted["status"] == "SUBMITTED"

    # 提交后不可再改
    blocked = client.post(f"{BASE}/sessions/{sid}/mark", headers=hdr,
                          json={"studentId": stu0["studentId"], "status": "PRESENT"}).json()
    assert blocked["code"] != 0

    # 列表里能看到本人这条场次
    lst = client.get(f"{BASE}/sessions", headers=hdr).json()["data"]
    assert lst["total"] >= 1
    assert any(s["sessionId"] == sid for s in lst["items"])


def test_attendance_other_teacher_cannot_view_or_mark(client, db_mode):
    """teacher_key 归属收敛：非本人创建的场次，另一教师应被拦截。"""
    cid = _seed_class(n_students=2)
    _seed_teaching_task(cid, "张老师")
    owner_hdr = _teacher_token("张老师")
    r = client.post(f"{BASE}/sessions", headers=owner_hdr,
                    json={"classId": cid, "courseName": "英语", "sessionDate": "2026-07-15"}).json()
    sid = r["data"]["sessionId"]

    other_hdr = _teacher_token("李老师")
    blocked = client.get(f"{BASE}/sessions/{sid}", headers=other_hdr).json()
    assert blocked["code"] != 0

    # 另一教师自己的场次列表里也不应该出现这条
    other_list = client.get(f"{BASE}/sessions", headers=other_hdr).json()["data"]
    assert not any(s["sessionId"] == sid for s in other_list["items"])


def test_attendance_empty_class_not_found(client, db_mode):
    """行政班无学生名单：明确报错，不 500、不建空场次。"""
    hdr = _teacher_token("赵老师")
    r = client.post(f"{BASE}/sessions", headers=hdr,
                    json={"classId": 999999999, "courseName": "无人班", "sessionDate": "2026-07-15"}).json()
    assert r["code"] != 0


def test_attendance_requires_login(client):
    assert client.get(f"{BASE}/sessions").json()["code"] == 401001


def _hdr_admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_attendance_pc_stats_and_type(client, db_mode):
    """PC 跨堂次统计(正方4.19)+点名类别：教师建2场次点名提交，教务处按学生汇总旷课并可按类别过滤。"""
    cid = _seed_class(n_students=3)
    hdr = _teacher_token("孙老师")
    PC = "/api/v1/academic-affairs/attendance"
    # 场次1：常规类别（不传=常规），1 人旷课
    s1 = client.post(f"{BASE}/sessions", headers=hdr, json={
        "classId": cid, "courseName": "语文", "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()["data"]
    absent_sid = client.get(f"{BASE}/sessions/{s1['sessionId']}", headers=hdr).json()["data"]["items"][0]["studentId"]
    client.post(f"{BASE}/sessions/{s1['sessionId']}/mark", headers=hdr,
                json={"studentId": absent_sid, "status": "ABSENT"})
    client.post(f"{BASE}/sessions/{s1['sessionId']}/submit", headers=hdr)
    # 场次2：实训类别，同一人再旷课
    s2 = client.post(f"{BASE}/sessions", headers=hdr, json={
        "classId": cid, "courseName": "语文", "termCode": "2026-1", "sessionDate": "2026-07-15",
        "sessionType": "实训"}).json()["data"]
    assert s2["sessionType"] == "实训"
    client.post(f"{BASE}/sessions/{s2['sessionId']}/mark", headers=hdr,
                json={"studentId": absent_sid, "status": "ABSENT"})
    client.post(f"{BASE}/sessions/{s2['sessionId']}/submit", headers=hdr)

    admin = _hdr_admin(client)
    stats = client.get(f"{PC}/stats", headers=admin, params={"classId": cid}).json()["data"]
    assert stats["sessionCount"] == 2
    top = stats["students"][0]  # 按旷课次数降序
    assert top["studentId"] == absent_sid and top["absent"] == 2 and top["sessions"] == 2
    # 点名类别过滤：只看实训 → 该生旷课 1、场次 1
    only = client.get(f"{PC}/stats", headers=admin, params={"classId": cid, "sessionType": "实训"}).json()["data"]
    assert only["sessionCount"] == 1 and only["students"][0]["absent"] == 1
    # PC 场次列表可查
    lst = client.get(f"{PC}/sessions", headers=admin, params={"classId": cid}).json()["data"]
    assert lst["total"] == 2

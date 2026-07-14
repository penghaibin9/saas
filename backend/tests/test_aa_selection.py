"""选课管理（/academic-affairs/selection/*）端点测试（SM-09 冻结状态机）。

覆盖：批次全生命周期(建/发布/开选/学生选/退/截止/锁定/归档)、发布无课程400、非OPEN选课409、
容量满409、SUSPENDED学生403、重复选课409、学生越权管理批次403、锁定后人工调整原因400/成功、
低人数取消开课+补选指引。口径核对施工包 §7/§9/§10。MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    c1 = AaCourse(tenant_id=TID, course_code="SEL001", course_name="职业素养选修", credit=2, status="ENABLED")
    c2 = AaCourse(tenant_id=TID, course_code="SEL002", course_name="人工智能导论", credit=3, status="ENABLED")
    db.add_all([c1, c2]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="SEL2401", real_name="选甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="SEL2402", real_name="选乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s3 = StudentProfile(tenant_id=TID, student_no="SEL2403", real_name="休丙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="SUSPENDED", status="ACTIVE")
    db.add_all([s1, s2, s3]); db.flush()
    ids = {"course1": c1.id, "course2": c2.id, "s1": s1.id, "s2": s2.id, "s3": s3.id}
    db.commit(); db.close()
    return ids


def _make_open_batch(client, admin, course_id, capacity=5, name="2024秋选修"):
    """建批次→加课程→发布→开选，返回 (batchId, selectionCourseId)。"""
    bid = client.post(f"{BASE}/selection/batches", headers=admin,
                      json={"batchName": name}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(course_id), "capacity": capacity, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    return bid, scid


def test_s1_full_lifecycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=5)
    stu = _stu_token("选甲", "SEL2401")
    # 学生可选课程有余量
    r = client.get(f"{BASE}/selection/student/courses", headers=stu).json()
    assert r["code"] == 0 and any(str(c["selectionCourseId"]) == str(scid)
                                  for grp in r["data"]["items"] for c in grp["courses"])
    # 选课成功
    r = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                    json={"selectionCourseId": str(scid)}).json()
    assert r["code"] == 0 and r["data"]["status"] == "SELECTED"
    # 我的选课
    my = client.get(f"{BASE}/selection/student/my", headers=stu).json()
    assert any(rec["selectionCourseId"] == str(scid) for rec in my["data"]["items"])
    # selectedCount 已+1
    cs = client.get(f"{BASE}/selection/batches/{bid}/courses", headers=admin).json()["data"]["items"]
    assert cs[0]["selectedCount"] == 1
    # 退课
    assert client.post(f"{BASE}/selection/student/drop", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["data"]["status"] == "DROPPED"
    # 截止→锁定→归档
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).json()["data"]["status"] == "CLOSED"
    assert client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin).json()["data"]["status"] == "LOCKED"
    assert client.post(f"{BASE}/selection/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_s2_publish_without_course_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin,
                      json={"batchName": "空批次"}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 400


def test_s3_enroll_when_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "未开选"}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)  # PUBLISHED，未 open
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s4_capacity_full_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=1)
    # 选甲占满
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选甲", "SEL2401"),
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    # 选乙容量满 409
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选乙", "SEL2402"),
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s5_suspended_student_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("休丙", "SEL2403"),
                       json={"selectionCourseId": str(scid)}).status_code == 403


def test_s6_duplicate_enroll_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s7_student_cannot_manage_batch_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/batches", headers=stu, json={"batchName": "越权"}).status_code == 403
    assert client.get(f"{BASE}/selection/batches", headers=stu).status_code == 403


def test_s8_lock_non_closed_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _make_open_batch(client, admin, ids["course1"])  # OPEN
    assert client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin).status_code == 409


def test_s9_adjust_after_lock(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"])
    stu = _stu_token("选甲", "SEL2401")
    rid = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                      json={"selectionCourseId": str(scid)}).json()["data"]["recordId"]
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    # 原因过短 400
    assert client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                       json={"reason": "x"}).status_code == 400
    # 合法原因成功，记录转 DROPPED
    r = client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                    json={"reason": "学生转专业需退课处理"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "DROPPED"


def test_s10_low_enroll_cancel_and_reselect(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # minCapacity=2，无人选 → 低人数
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "低人数批次"}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(ids["course1"]), "capacity": 30, "minCapacity": 2}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    # 统计显示低人数
    st = client.get(f"{BASE}/selection/batches/{bid}/stats", headers=admin).json()["data"]
    assert st["lowEnrollCount"] == 1
    # 人工取消开课
    assert client.post(f"{BASE}/selection/courses/{scid}/cancel", headers=admin).json()["data"]["status"] == "COURSE_CANCELLED"
    # 补选指引含被取消课程
    guide = client.get(f"{BASE}/selection/batches/{bid}/reselect-guide", headers=admin).json()["data"]
    assert len(guide["cancelledCourses"]) == 1

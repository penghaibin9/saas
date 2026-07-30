"""移动学生端·新增自助接口(成绩认定/等级考试报名/专业分流志愿)端到端测试。

验证:学生 token 经 /mobile/academic/* 委托到域 service 真能跑通(不是只 200);
空数据不 500;提交真落库;跨教务处管理端可见。MySQL-only(db_mode 夹具)。
"""
from __future__ import annotations

BASE = "/api/v1/mobile/academic"
ADMIN_BASE = "/api/v1/academic-affairs"
MAIN = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_student(student_no, real_name, grade="2026", major_id=None, class_id=None):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                          grade=grade, major_id=major_id, class_id=class_id,
                          current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()


def _seed_target_course(client, admin):
    response = client.post(f"{ADMIN_BASE}/courses", headers=admin, json={
        "courseCode": "RG101", "courseName": "高等数学",
        "category": "MAJOR_CORE", "nature": "REQUIRED", "credit": 4,
        "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM",
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]["courseId"]


# ── 成绩认定 ──

def test_recognition_my_empty_not_500(client, db_mode):
    _seed_student("RG0001", "认定测生")
    r = client.get(f"{BASE}/recognition/my", headers=_stu_token("认定测生", "RG0001")).json()
    assert r["code"] == 0 and r["data"]["items"] == []


def test_recognition_submit_and_visible_to_admin(client, db_mode):
    _seed_student("RG0002", "认定乙")
    hdr = _stu_token("认定乙", "RG0002")
    admin = _admin(client)
    target_course_id = _seed_target_course(client, admin)
    # 低分拦截（即使目标课程合法，低分仍必须被业务规则拒绝）
    bad = client.post(f"{BASE}/recognition/submit", headers=hdr,
                      json={"sourceCourseName": "高数A", "sourceScore": 50,
                            "targetCourseId": str(target_course_id),
                            "targetCourseName": "高等数学"})
    assert bad.status_code == 400, bad.text
    # 正常提交
    ok = client.post(f"{BASE}/recognition/submit", headers=hdr,
                     json={"sourceCourseName": "高数A", "sourceScore": 82, "sourceCredit": 4,
                           "sourceOrigin": "原电子专业",
                           "targetCourseId": str(target_course_id),
                           "targetCourseName": "高等数学", "reason": "转专业替代"})
    assert ok.status_code == 200, ok.text
    my = client.get(f"{BASE}/recognition/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED"
    # 教务处管理端可见同一条
    admin_list = client.get(f"{ADMIN_BASE}/grade-recognitions", headers=_admin(client)).json()["data"]
    assert any(x["studentNo"] == "RG0002" for x in admin_list["items"])


# ── 等级考试报名 ──

def test_level_exam_my_empty_and_register_flow(client, db_mode):
    _seed_student("LV0001", "考级测生")
    admin = _admin(client)
    hdr = _stu_token("考级测生", "LV0001")
    # 空
    r0 = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert r0["openExams"] == [] and r0["myRegs"] == []
    # 教务处建考试并开放
    eid = client.post(f"{ADMIN_BASE}/level-exams", headers=admin,
                      json={"examName": "四级(移动)", "category": "CET", "level": "四级",
                            "fee": 30, "passLine": 425}).json()["data"]["examId"]
    client.post(f"{ADMIN_BASE}/level-exams/{eid}/transition?action=OPEN", headers=admin)
    # 学生看到并报名
    d = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert len(d["openExams"]) == 1
    reg = client.post(f"{BASE}/level-exam/{eid}/register", headers=hdr)
    assert reg.status_code == 200, reg.text
    d2 = client.get(f"{BASE}/level-exam/my", headers=hdr).json()["data"]
    assert len(d2["myRegs"]) == 1 and d2["myRegs"][0]["status"] == "REGISTERED"
    # 取消
    assert client.post(f"{BASE}/level-exam/{eid}/cancel", headers=hdr).status_code == 200


# ── 专业分流志愿 ──

def _seed_split(client):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass
    db = get_sessionmaker()()
    col = College(tenant_id=MAIN, college_name="信息学院", status="ACTIVE"); db.add(col); db.flush()
    src = Major(tenant_id=MAIN, college_id=col.id, major_name="电子大类", status="ACTIVE")
    ma = Major(tenant_id=MAIN, college_id=col.id, major_name="软件技术", status="ACTIVE")
    mb = Major(tenant_id=MAIN, college_id=col.id, major_name="网络技术", status="ACTIVE")
    db.add_all([src, ma, mb]); db.flush()
    kls = SchoolClass(tenant_id=MAIN, major_id=src.id, class_name="电信26", grade="2026", status="ACTIVE")
    db.add(kls); db.flush()
    ids = {"src": src.id, "ma": ma.id, "mb": mb.id, "class": kls.id}
    db.commit(); db.close()
    return ids


def test_major_split_view_and_submit(client, db_mode):
    ids = _seed_split(client)
    _seed_student("MS0001", "分流测生", grade="2026", major_id=ids["src"], class_id=ids["class"])
    admin = _admin(client)
    hdr = _stu_token("分流测生", "MS0001")
    # 教务处建分流批次+专业+开放
    bid = client.post(f"{ADMIN_BASE}/major-split/batches", headers=admin,
                      json={"batchName": "2026电子分流", "grade": "2026",
                            "sourceMajorId": str(ids["src"]), "maxChoices": 2}).json()["data"]["batchId"]
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/options", headers=admin,
                json={"majorId": str(ids["ma"]), "capacity": 30})
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/options", headers=admin,
                json={"majorId": str(ids["mb"]), "capacity": 30})
    client.post(f"{ADMIN_BASE}/major-split/batches/{bid}/open", headers=admin)
    # 学生看到开放批次（含可选专业）
    d = client.get(f"{BASE}/major-split/my", headers=hdr).json()["data"]
    assert len(d["openBatches"]) == 1
    assert len(d["openBatches"][0]["options"]) == 2
    # 提交志愿
    r = client.post(f"{BASE}/major-split/submit", headers=hdr,
                    json={"batchId": bid, "choices": [str(ids["ma"]), str(ids["mb"])]})
    assert r.status_code == 200, r.text
    d2 = client.get(f"{BASE}/major-split/my", headers=hdr).json()["data"]
    assert len(d2["myVolunteers"]) == 1
    assert [str(x) for x in d2["myVolunteers"][0]["choices"]] == [str(ids["ma"]), str(ids["mb"])]

"""13B-P3 课程库 · 端到端（两级审核 + 版本化 + 学时校验）。

C1 建课→两级审→ENABLED；C2 学时构成校验400；C3 已启用改动强制新版本；C4 重复代码409；C5 退回。

Tier1 R2（新增课程/课程分类/课程性质/学分学时/课程负责人/课程停用）续工新增：
C6 课程负责人须为本校在职教师；C7 课程编号格式校验；C8 适用专业与全校通用互斥；
C9 停用/启用 + 被在途培养方案引用限停 + 引用查询端点；C10 课程负责人检索选择器。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _course(client, hdr, code="CS101", **extra):
    body = {"courseCode": code, "courseName": "数据结构", "courseNameEn": "Data Structure",
            "category": "MAJOR_CORE", "nature": "REQUIRED", "credit": 4,
            "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16, "examMode": "EXAM",
            "isCore": True, **extra}
    return client.post(f"{BASE}/courses", headers=hdr, json=body)


def _seed_teacher(db_mode, login="t_course_owner01", name="王老师"):
    from app.db.session import get_sessionmaker
    from app.models import User
    db = get_sessionmaker()()
    u = User(tenant_id=TID, login_name=login, real_name=name, password_hash="x",
             user_type="TEACHER", status="ACTIVE")
    db.add(u); db.flush()
    uid = u.id
    db.commit(); db.close()
    return uid


def _seed_major(db_mode, name="软件技术"):
    from app.db.session import get_sessionmaker
    from app.models import College, Major
    db = get_sessionmaker()()
    c = College(tenant_id=TID, college_name="信息学院-课程库测试", status="ACTIVE")
    db.add(c); db.flush()
    m = Major(tenant_id=TID, college_id=c.id, major_name=name, status="ACTIVE")
    db.add(m); db.flush()
    mid = m.id
    db.commit(); db.close()
    return mid


def test_c1_two_level_review_to_enabled(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr).json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    r1 = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r1["data"]["status"] == "ACADEMIC_REVIEW"  # 学院审过→教务审
    r2 = client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "ENABLED"  # 教务审过→启用
    assert r2["data"]["categoryLabel"] == "专业核心" and r2["data"]["natureLabel"] == "必修"


def test_c2_hours_composition_422(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 理论48+实践16=64，但总学时写 80 → 不一致 422
    assert _course(client, hdr, code="CS102", hoursTotal=80).status_code == 400


def test_c3_enabled_edit_forces_new_version(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr, code="CS103").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # ENABLED
    # 改已启用课程 → 生成 v2 草稿
    r = client.put(f"{BASE}/courses/{cid}", headers=hdr, json={
        "courseCode": "CS103", "courseName": "数据结构(修订)", "category": "MAJOR_CORE",
        "nature": "REQUIRED", "credit": 5, "hoursTotal": 64, "hoursTheory": 48,
        "hoursPractice": 16, "examMode": "EXAM"}).json()
    assert r["data"]["version"] == 2 and r["data"]["status"] == "DRAFT"


def test_c4_duplicate_code_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _course(client, hdr, code="CS104")
    assert _course(client, hdr, code="CS104").status_code == 409


def test_c5_reject_returns(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr, code="CS105").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    r = client.post(f"{BASE}/courses/{cid}/review", headers=hdr,
                    json={"action": "RETURN", "reason": "学时构成需调整"}).json()
    assert r["data"]["status"] == "RETURNED"


def test_c6_owner_teacher_must_be_active_teacher(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 不存在的负责人 → 400
    assert _course(client, hdr, code="CS106", ownerTeacherId="999999").status_code == 400
    # 真实在职教师 → 建课成功且回显
    tid = _seed_teacher(db_mode)
    r = _course(client, hdr, code="CS107", ownerTeacherId=str(tid)).json()
    assert r["data"]["ownerTeacherId"] == str(tid)


def test_c7_course_code_format_400(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    assert _course(client, hdr, code="cs108").status_code == 400  # 小写不合法
    assert _course(client, hdr, code="CS1").status_code == 400    # 数字位数不足(<3位)
    assert _course(client, hdr, code="CS108").status_code == 200  # 合法格式


def test_c8_applicable_majors_mutual_exclusive_with_all_major(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    mid = _seed_major(db_mode)
    r = _course(client, hdr, code="CS109", isAllMajor=True, applicableMajors=[str(mid)])
    assert r.status_code == 400
    # 单选适用专业（不勾全校通用）→ 正常建课并回显
    r2 = _course(client, hdr, code="CS110", isAllMajor=False, applicableMajors=[str(mid)]).json()
    assert r2["data"]["applicableMajors"] == [str(mid)]


def test_c9_disable_blocked_by_live_program_reference_then_allowed(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _course(client, hdr, code="CS111").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})  # ENABLED
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "课程停用校验方案", "majorId": "1", "gradeYear": "2026",
        "totalCredits": 4}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "数据结构", "openTermNo": 1, "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # PUBLISHED
    # 被在途/生效方案引用 → 停用 400 拦截
    assert client.post(f"{BASE}/courses/{cid}/disable", headers=hdr).status_code == 400
    # 引用查询端点：能看到该方案
    refs = client.get(f"{BASE}/courses/{cid}/references", headers=hdr).json()
    assert any(it["programId"] == str(pid) for it in refs["data"]["items"])
    # 未被引用的课程：停用/启用正常闭环
    cid2 = _course(client, hdr, code="CS112").json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid2}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid2}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid2}/review", headers=hdr, json={"action": "APPROVE"})
    d = client.post(f"{BASE}/courses/{cid2}/disable", headers=hdr).json()
    assert d["data"]["status"] == "DISABLED"
    e = client.post(f"{BASE}/courses/{cid2}/enable", headers=hdr).json()
    assert e["data"]["status"] == "ENABLED"
    # 非法状态转移（重复启用已启用课程）→ 409
    assert client.post(f"{BASE}/courses/{cid2}/enable", headers=hdr).status_code == 409


def test_c10_teacher_search_selector(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    tid = _seed_teacher(db_mode, login="t_search01", name="张三")
    r = client.get(f"{BASE}/courses/teachers/search", headers=hdr, params={"keyword": "张三"}).json()
    assert any(it["value"] == str(tid) for it in r["data"]["items"])


def test_c11_student_forbidden_on_new_endpoints(client, db_mode):
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/courses/1/enable", headers=hdr).status_code == 403
    assert client.get(f"{BASE}/courses/teachers/search", headers=hdr).status_code == 403

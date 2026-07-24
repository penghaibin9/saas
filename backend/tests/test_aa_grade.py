"""13B-P5/R1 成绩录入(平时+期末按比例) + 审核发布更正 + 读侧视图 · 端到端。

G1 录入合成→提交→学院审→教务发布→投影t_acad_grade→成绩单；G2 占比≠100→422；
G3 未录全禁提交409；G4 挂科清单；G5 成绩分析；G6 N+1；G7 未审核直接发布409；
G8 成绩异常清单(缺考标记入清单/正常成绩不入)；G9 成绩异常清单按类型过滤+学生令牌403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, n=2):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(tenant_id=TID, student_no=f"G{i:03d}", real_name=f"成绩{i}", class_id=a.id,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    db.close()
    return sids


def _task(client, hdr, usual=30, final=70):
    return client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "高等数学", "termCode": "2026-2027-1", "credit": 4,
        "usualRatio": usual, "finalRatio": final,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]


def _submit_and_approve(client, hdr, tid):
    """走完提交→学院审通过→（回到 ACADEMIC_REVIEW，供调用方自行发布）。
    school_admin01(SCHOOL_ADMIN) 同时在 _REVIEW_ROLES 白名单内，可代行教务处/学院两级动作。"""
    s = client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    assert s.status_code == 200, s.text
    r = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ACADEMIC_REVIEW"


def test_g1_compose_publish_project(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                    json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 90}).json()
    assert r["data"]["totalScore"] == 87 and r["data"]["passStatus"] == "PASSED"  # 80*.3+90*.7
    _submit_and_approve(client, hdr, tid)
    p = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr).json()
    assert p["data"]["projected"] == 1
    # 投影到 t_acad_grade → 成绩单可读
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "高等数学" and g["score"] == 87 and g["source"] == "PUBLISH" for g in tr["items"])


def test_g2_ratio_not_100_422(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    assert client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "X", "usualRatio": 40, "finalRatio": 70,
        "adminSupplementReason": "测试管理员补录成绩任务"}).status_code == 400


def test_g3_incomplete_submit_409(client, db_mode):
    sids = _seed(db_mode, 2)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    # 第2人只录平时分未录期末分 → total_score 仍为 None → 未录全
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={"studentId": str(sids[1]), "usualScore": 70})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 409


def test_g4_fail_list(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 40, "finalScore": 50})  # 47 FAIL
    _submit_and_approve(client, hdr, tid)
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    fl = client.get(f"{BASE}/grade-views/fail-list", headers=hdr).json()["data"]["items"]
    assert any(x["courseName"] == "高等数学" for x in fl)


def test_g5_analysis(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 90, "finalScore": 95})
    _submit_and_approve(client, hdr, tid)
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    a = client.get(f"{BASE}/grade-views/analysis", headers=hdr).json()["data"]
    assert a["total"] == 1 and a["passRate"] == 1.0


def test_g8_analysis_enhanced_and_group(client, db_mode):
    """正方对标：总体新增优秀率/平均分/最高最低；dimension=course/class 出分组统计表。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 90, "finalScore": 90})  # 合成 90，优秀
    _submit_and_approve(client, hdr, tid)
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    a = client.get(f"{BASE}/grade-views/analysis", headers=hdr).json()["data"]
    assert a["excellentRate"] == 1.0 and a["avgScore"] == 90.0
    assert a["maxScore"] == 90 and a["minScore"] == 90
    byc = client.get(f"{BASE}/grade-views/analysis", headers=hdr, params={"dimension": "course"}).json()["data"]
    assert byc["dimension"] == "course"
    assert any(r["name"] == "高等数学" and r["total"] == 1 for r in byc["rows"])
    byk = client.get(f"{BASE}/grade-views/analysis", headers=hdr, params={"dimension": "class"}).json()["data"]
    assert byk["dimension"] == "class" and len(byk["rows"]) >= 1


def test_g9_analysis_export_xlsx(client, db_mode):
    """成绩分析统计表导出 xlsx：用途<5 字被拒；合规请求返回真实 xlsx 二进制。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                json={"studentId": str(sids[0]), "usualScore": 88, "finalScore": 88})
    _submit_and_approve(client, hdr, tid)
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    bad = client.post(f"{BASE}/grade-views/analysis/export", headers=hdr,
                      json={"dimension": "course", "purpose": "x"})
    assert bad.status_code in (400, 422)
    ok = client.post(f"{BASE}/grade-views/analysis/export", headers=hdr,
                     json={"dimension": "course", "purpose": "学期成绩分析统计导出"})
    assert ok.status_code == 200
    assert "spreadsheetml" in ok.headers.get("content-type", "")
    assert ok.content[:2] == b"PK"


def test_g10_midterm_three_component(client, db_mode):
    """成绩分项扩展(正方对标)：平时30+期中30+期末40 三分项按比例合成总评；期中未录则未录全。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "钳工实训", "termCode": "2026-1", "credit": 3,
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "midtermScore": 90, "finalScore": 100}).json()
    assert r["data"]["totalScore"] == 91  # 80*.3 + 90*.3 + 100*.4 = 24+27+40
    assert r["data"]["passStatus"] == "PASSED"
    r2 = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "midtermScore": None, "finalScore": 100}).json()  # 显式清空期中→未录全
    assert r2["data"]["totalScore"] is None
    assert r2["data"]["midtermScore"] is None


def test_g11_midterm_ratio_sum_must_100(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    assert client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "X", "usualRatio": 30, "midtermRatio": 30, "finalRatio": 30,
        "adminSupplementReason": "测试管理员补录成绩任务"}).status_code == 400
    assert client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "Y", "usualRatio": 40, "midtermRatio": 20, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"}).status_code == 200


def test_g6_fail_list_no_n_plus_one(client, db_mode):
    """挂科清单读侧：命中 t_acad_student 次数与挂科行数无关（JOIN 批量，非逐行 db.get）。"""
    from sqlalchemy import event
    from app.db.session import get_engine
    sids = _seed(db_mode, 6)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    for sid in sids:
        client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
                    json={"studentId": str(sid), "usualScore": 30, "finalScore": 30})  # 30 FAIL
    _submit_and_approve(client, hdr, tid)
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    hits = []
    engine = get_engine()

    def _rec(conn, cursor, statement, parameters, context, executemany):
        if "t_acad_student" in statement:
            hits.append(statement)

    event.listen(engine, "before_cursor_execute", _rec)
    try:
        fl = client.get(f"{BASE}/grade-views/fail-list?pageSize=50", headers=hdr).json()["data"]
    finally:
        event.remove(engine, "before_cursor_execute", _rec)
    assert fl["total"] >= 6 and len(hits) <= 2, f"疑似 N+1：命中 t_acad_student {len(hits)} 次"


def test_g7_publish_without_review_409(client, db_mode):
    """R1 回归红线：未经学院审+教务终审，直接发布必须 409（不得绕过状态机）。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    assert client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr).status_code == 409


def test_g8_exception_list(client, db_mode):
    """成绩异常清单（成绩管理·三级模块续工）：缺考标记学生入清单，正常录分学生不入清单。"""
    sids = _seed(db_mode, 2)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "exceptionFlag": "ABSENT"})
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[1]), "usualScore": 80, "finalScore": 90})
    el = client.get(f"{BASE}/grade-views/exception-list", headers=hdr).json()["data"]
    assert el["total"] == 1
    row = el["items"][0]
    assert row["studentId"] == str(sids[0])
    assert row["exceptionFlag"] == "ABSENT"
    assert row["courseName"] == "高等数学"


def test_g9_exception_list_filter_flag_and_student_403(client, db_mode):
    """成绩异常清单：exceptionFlag 过滤仅返回命中类型；学生令牌 403（require_staff，与同组读视图一致）。"""
    sids = _seed(db_mode, 2)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "exceptionFlag": "DEFERRED"})
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[1]), "exceptionFlag": "EXEMPT"})
    only_deferred = client.get(f"{BASE}/grade-views/exception-list?exceptionFlag=DEFERRED",
                               headers=hdr).json()["data"]
    assert only_deferred["total"] == 1
    assert only_deferred["items"][0]["exceptionFlag"] == "DEFERRED"
    stu_hdr = _hdr(client, "student01")
    assert client.get(f"{BASE}/grade-views/exception-list", headers=stu_hdr).status_code == 403


def test_g10_cross_tenant_teaching_task_rejected(client, db_mode):
    """租户隔离收口：新建成绩任务引用他租户 teachingTaskId 须拒绝（此前 db.get 不校验
    tenant_id，会把他租户 teacher_key 带进本租户新任务）。"""
    _seed(db_mode, 1)
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    other = AaTeachingTask(tenant_id=TID + 1, batch_id=1, course_id=1, course_name="他租户课",
                           teacher_key="other_teacher", status="READY")
    db.add(other); db.commit()
    other_tt_id = other.id
    db.close()
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "高数", "termCode": "2026-2027-1", "credit": 4,
        "usualRatio": 30, "finalRatio": 70, "teachingTaskId": str(other_tt_id)})
    assert r.status_code == 404 and r.json()["bizCode"] == "DATA_NOT_FOUND"

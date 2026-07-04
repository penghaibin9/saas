"""学业过程域测试：台账/成绩/补考/重修 CRUD + 预警全闭环（含 academicStatus 联动）+ 审计。"""
from __future__ import annotations

MAIN_TID = 1000000000000000001


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicMakeup, AcademicStudent, AcademicWarning
    db = get_sessionmaker()()
    try:
        s = AcademicStudent(tenant_id=MAIN_TID, name="学业甲", student_no="2023999001", class_id="CL01",
                            class_name="软件2301班", counselor="李敏", gpa=2.1, avg_score=61,
                            failed_count=3, obtained_credits=40, required_credits=120,
                            warning_level="HIGH", warning_count=1, academic_status="WARNING")
        db.add(s)
        db.flush()
        g = AcademicGrade(tenant_id=MAIN_TID, acad_student_id=s.id, course_name="高等数学", term="2025-2026-2",
                          nature="REQUIRED", credit_value=5, score=52, pass_status="FAILED", exam_type="FINAL")
        mk = AcademicMakeup(tenant_id=MAIN_TID, acad_student_id=s.id, course_name="高等数学", term="2025-2026-2",
                            origin_score=52, status="PENDING_EXAM")
        w = AcademicWarning(tenant_id=MAIN_TID, code="AW-T-1", acad_student_id=s.id, warn_type="MULTI_FAIL",
                            level="HIGH", reason="多门挂科触发预警", status="PENDING_HANDLE")
        db.add_all([g, mk, w])
        db.commit()
        return {"student": s.id, "grade": g.id, "makeup": mk.id, "warning": w.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/academic/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["academicStatusLabel"] == "预警中"
    det = client.get(f"/api/v1/academic/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["grades"]) == 1 and len(det["data"]["warnings"]) == 1
    assert det["data"]["credit"]["gap"] == 80


def test_grade_update_requires_reason(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.put(f"/api/v1/academic/grades/{ids['grade']}", headers=auth_headers,
                     json={"score": 75, "reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.put(f"/api/v1/academic/grades/{ids['grade']}", headers=auth_headers,
                    json={"score": 75, "reason": "登分误差已核对更正"}).json()
    assert ok["code"] == 0
    # 成绩改为75后 passStatus 应为 PASSED
    det = client.get(f"/api/v1/academic/students/{ids['student']}", headers=auth_headers).json()
    assert det["data"]["grades"][0]["passStatus"] == "PASSED"


def test_makeup_status(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ok = client.put(f"/api/v1/academic/makeups/{ids['makeup']}/status", headers=auth_headers,
                    json={"status": "PASSED"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "PASSED"


def test_warning_full_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    wid = ids["warning"]
    # 干预内容<5字被拒
    bad = client.post(f"/api/v1/academic/warnings/{wid}/interventions", headers=auth_headers,
                      json={"content": "谈", "way": "TALK"}).json()
    assert bad["code"] == 422001
    fu = client.post(f"/api/v1/academic/warnings/{wid}/interventions", headers=auth_headers,
                     json={"content": "已面谈并制定学习计划", "way": "TALK"}).json()
    assert fu["code"] == 0
    # 干预后预警转 PROCESSING
    det = client.get(f"/api/v1/academic/warnings/{wid}", headers=auth_headers).json()
    assert det["data"]["warning"]["status"] == "PROCESSING" and len(det["data"]["interventions"]) == 1
    # 关闭需说明≥5字
    badc = client.post(f"/api/v1/academic/warnings/{wid}/close", headers=auth_headers,
                       json={"result": "ok"}).json()
    assert badc["code"] == 422001
    ok = client.post(f"/api/v1/academic/warnings/{wid}/close", headers=auth_headers,
                     json={"result": "学生已补考通过，预警解除"}).json()
    assert ok["code"] == 0
    # 关闭后学生 academicStatus 回退 NORMAL（无其它活跃预警）
    stu = client.get(f"/api/v1/academic/students/{ids['student']}", headers=auth_headers).json()
    assert stu["data"]["student"]["academicStatus"] == "NORMAL"
    assert stu["data"]["student"]["warningLevel"] == "NONE"


def test_warning_escalate_and_create(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    esc = client.post(f"/api/v1/academic/warnings/{ids['warning']}/escalate", headers=auth_headers,
                      json={"reason": "多次干预无效，升级学院专班"}).json()
    assert esc["code"] == 0
    stu = client.get(f"/api/v1/academic/students/{ids['student']}", headers=auth_headers).json()
    assert stu["data"]["student"]["academicStatus"] == "HELPING"
    # 新建预警
    nw = client.post("/api/v1/academic/warnings", headers=auth_headers,
                     json={"studentId": str(ids["student"]), "type": "CREDIT_GAP",
                           "reason": "学分缺口过大触发预警"}).json()
    assert nw["code"] == 0 and nw["data"]["code"].startswith("AW-")


def test_warning_assign_and_level(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    asg = client.post("/api/v1/academic/warnings/assign", headers=auth_headers,
                      json={"ids": [str(ids["warning"])], "ownerName": "李敏（辅导员）"}).json()
    assert asg["code"] == 0 and asg["data"]["count"] == 1
    lv = client.put(f"/api/v1/academic/warnings/{ids['warning']}/level", headers=auth_headers,
                    json={"level": "MEDIUM", "reason": "情况好转下调等级"}).json()
    assert lv["code"] == 0


def test_credits_and_dashboard_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    cr = client.get("/api/v1/academic/credits", headers=auth_headers).json()
    assert cr["code"] == 0 and cr["data"]["total"] == 1 and cr["data"]["items"][0]["gap"] == 80
    dash = client.get("/api/v1/academic/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(k["key"] == "students" for k in dash["data"]["kpis"])
    client.post(f"/api/v1/academic/warnings/{ids['warning']}/escalate", headers=auth_headers,
                json={"reason": "升级测试审计写入"})
    au = client.get("/api/v1/academic/audit-logs?bizType=WARNING", headers=auth_headers).json()
    assert au["code"] == 0 and au["data"]["total"] >= 1


def test_requires_login(client):
    assert client.get("/api/v1/academic/dashboard").json()["code"] == 401001

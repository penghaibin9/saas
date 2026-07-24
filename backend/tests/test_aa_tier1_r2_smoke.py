"""教务中心 Tier1-R2 · 补充烟雾测试（学籍管理 / 课表管理 / 成绩管理 / 教学评价）。

这4个模块本轮续工时只做过一次性 SQLite 诊断脚本自测（未提交为 pytest），总控合并复核时
发现缺口后补写本文件：覆盖每个模块最核心的新增端点各一条真实链路，确认在真实数据库层面
可跑通（非详尽穷举，穷尽用例见各模块原始施工卡）。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_class(db_mode, class_name="软件2601"):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    c = SchoolClass(tenant_id=TID, major_id=1, class_name=class_name, grade="2026", status="ACTIVE")
    db.add(c); db.flush()
    cid = c.id
    db.commit()
    db.close()
    return cid


def _seed_student(db_mode, student_no="R001", class_id=None):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no=student_no, real_name=f"学籍{student_no}", class_id=class_id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE",
                       id_card_encrypted=f"ENC-{student_no}")
    db.add(s); db.flush()
    sid = s.id
    db.commit()
    db.close()
    return sid


def _seed_term(db_mode, status="PUBLISHED"):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    t = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status=status)
    db.add(t); db.flush()
    tid = t.id
    db.commit()
    db.close()
    return tid


# ═══════════ 学籍管理：学籍详情 / 敏感字段查看 / 状态汇总 ═══════════

def test_roster_detail_reveal_and_status_summary(client, db_mode):
    cid = _seed_class(db_mode)
    sid = _seed_student(db_mode, "R001", cid)
    hdr = _hdr(client, "school_admin01")
    detail = client.get(f"{BASE}/roster/{sid}", headers=hdr)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["studentNo"] == "R001"
    assert detail.json()["data"]["studentStatus"] == "REGISTERED"
    reveal = client.post(f"{BASE}/roster/{sid}/reveal", headers=hdr, json={"reason": "核对身份信息"})
    assert reveal.status_code == 200, reveal.text
    assert reveal.json()["data"]["idCard"] == "ENC-R001"
    summary = client.get(f"{BASE}/roster/status-summary", headers=hdr)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["total"] >= 1
    assert any(row["status"] == "REGISTERED" for row in data["byStatus"])


def test_roster_detail_student_forbidden_403(client, db_mode):
    sid = _seed_student(db_mode, "R001")
    from app.core.security import create_access_token
    stu_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-R001", "realName": "学籍R001", "studentNo": "R001", "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": "MP"})}
    assert client.get(f"{BASE}/roster/{sid}", headers=stu_hdr).status_code == 403


# ═══════════ 成绩管理：成绩批量导入确认（内部先跑同一套 dry-run 校验再落库）═══════════

def test_grade_import_confirm_writes_records(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _seed_student(db_mode, "IMPORT01")
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "线性代数", "termCode": "2026-2027-1", "credit": 3,
        "usualRatio": 30, "finalRatio": 70,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    rows = [{"studentNo": "IMPORT01", "usualScore": 80, "finalScore": 80}]
    confirm = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={"rows": rows})
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["created"] == 1
    records = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr)
    assert records.status_code == 200, records.text
    items = records.json()["data"]["items"]
    assert len(items) == 1 and items[0]["studentNo"] == "IMPORT01" and items[0]["totalScore"] == 80


def test_grade_import_confirm_unmatched_student_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    tid = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "线性代数", "termCode": "2026-2027-1", "credit": 3,
        "usualRatio": 30, "finalRatio": 70,
        "adminSupplementReason": "测试管理员补录成绩任务"}).json()["data"]["gradeTaskId"]
    rows = [{"studentNo": "NOBODY", "usualScore": 80, "finalScore": 75}]
    confirm = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={"rows": rows})
    assert confirm.status_code == 409, confirm.text


# ═══════════ 课表管理：班级/教师课表只读视图 + 发布记录 ═══════════

def test_schedule_readonly_views_and_publish_records(client, db_mode):
    tid = _seed_term(db_mode)
    cid = _seed_class(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/schedule-batches", headers=hdr,
                      json={"termId": str(tid), "batchName": "2026秋课表"}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json={
        "courseName": "大学英语", "classId": str(cid), "className": "软件2601",
        "teacherKey": "T001", "teacherName": "王老师", "weekday": 1, "slotNo": 1,
        "startWeek": 1, "endWeek": 18})
    assert item.status_code == 200, item.text
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    pub = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    assert pub.status_code == 200, pub.text
    cls = client.get(f"{BASE}/schedule/class/{cid}", headers=hdr)
    assert cls.status_code == 200, cls.text
    assert len(cls.json()["data"]["items"]) == 1
    teacher = client.get(f"{BASE}/schedule/teacher/T001", headers=hdr)
    assert teacher.status_code == 200, teacher.text
    assert teacher.json()["data"]["weeklyHours"] == 1
    records = client.get(f"{BASE}/schedule/publish-records", headers=hdr)
    assert records.status_code == 200, records.text
    assert records.json()["data"]["total"] >= 1


# ═══════════ 教学评价：教师自评应评任务生成 + 我的任务（结构性只读校验，evaluatorKey 匹配见既有 _derive_keys 用例）═══════════

def test_evaluation_self_role_tasks_generate_and_list(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    term_id = _seed_term(db_mode)
    db = get_sessionmaker()()
    b = AaTeachingTaskBatch(tenant_id=TID, term_id=term_id, batch_name="2026秋教学任务", status="APPROVED")
    db.add(b); db.flush()
    t = AaTeachingTask(tenant_id=TID, batch_id=b.id, course_id=1, course_name="数据结构",
                       teacher_key="T002", teacher_name="李老师", status="READY")
    db.add(t); db.flush()
    task_id = t.id
    db.commit()
    db.close()

    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=hdr,
                      json={"batchName": "2026秋评教"}).json()["data"]["batchId"]
    gen = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=hdr, json={
        "evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(task_id)}]})
    assert gen.status_code == 200, gen.text
    assert gen.json()["data"]["taskCount"] == 1
    mine = client.get(f"{BASE}/evaluation/my-role-tasks", headers=hdr,
                      params={"evaluatorType": "SELF", "batchId": bid})
    assert mine.status_code == 200, mine.text


# ═══════════ 课表管理续工第三轮：学生课表 / 教学班课表 / 课表调整记录 ═══════════

def test_student_schedule_view_and_out_of_scope_403(client, db_mode):
    """学生课表：教务处按学生查询到本班课表；未配置数据范围的学院教务查询同一学生 → 403002。"""
    tid = _seed_term(db_mode)
    cid = _seed_class(db_mode, "软件2602")
    sid = _seed_student(db_mode, "STU301", cid)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/schedule-batches", headers=hdr,
                      json={"termId": str(tid), "batchName": "2026秋课表-学生"}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json={
        "courseName": "高等数学", "classId": str(cid), "className": "软件2602",
        "teacherKey": "T101", "teacherName": "赵老师", "weekday": 2, "slotNo": 1,
        "startWeek": 1, "endWeek": 18})
    assert item.status_code == 200, item.text
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    pub = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    assert pub.status_code == 200, pub.text

    stu = client.get(f"{BASE}/schedule/student/{sid}", headers=hdr)
    assert stu.status_code == 200, stu.text
    data = stu.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["courseName"] == "高等数学"
    assert data["studentNo"] == "STU301"

    from app.core.security import create_access_token
    college_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-college-noscope", "realName": "无范围学院教务", "userType": "STAFF",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx_college_noscope",
        "currentRoleCode": "COLLEGE_ADMIN", "clientType": "PC"})}
    forbidden = client.get(f"{BASE}/schedule/student/{sid}", headers=college_hdr)
    assert forbidden.status_code == 403, forbidden.text


def test_teaching_class_schedule_view_and_not_found_404(client, db_mode):
    """教学班课表：按教学班代码（派生自教学任务）查其排课项；不存在的代码 → 404。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    tid = _seed_term(db_mode)
    cid = _seed_class(db_mode, "软件2603")
    hdr = _hdr(client, "school_admin01")
    code = "TC-TEST-0001"
    db = get_sessionmaker()()
    b = AaTeachingTaskBatch(tenant_id=TID, term_id=tid, batch_name="2026秋教学任务-教学班", status="APPROVED")
    db.add(b); db.flush()
    t = AaTeachingTask(tenant_id=TID, batch_id=b.id, course_id=1, course_name="大学物理",
                       class_id=cid, teacher_key="T102", teacher_name="钱老师",
                       teaching_class_code=code, teaching_class_name="大学物理(软件2603)", status="READY")
    db.add(t); db.flush()
    task_id = t.id
    db.commit()
    db.close()

    bid = client.post(f"{BASE}/schedule-batches", headers=hdr,
                      json={"termId": str(tid), "batchName": "2026秋课表-教学班"}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json={
        "taskId": str(task_id), "classId": str(cid), "className": "软件2603",
        "teacherKey": "T102", "teacherName": "钱老师", "weekday": 3, "slotNo": 2,
        "startWeek": 1, "endWeek": 18})
    assert item.status_code == 200, item.text
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    pub = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    assert pub.status_code == 200, pub.text

    tc = client.get(f"{BASE}/schedule/teaching-class/{code}", headers=hdr)
    assert tc.status_code == 200, tc.text
    data = tc.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["courseName"] == "大学物理"
    assert data["teachingClassName"] == "大学物理(软件2603)"

    missing = client.get(f"{BASE}/schedule/teaching-class/TC-NOPE-0000", headers=hdr)
    assert missing.status_code == 404, missing.text


def test_schedule_adjustments_log_and_invalid_biz_type_400(client, db_mode):
    """课表调整记录：手工排课后可在日志中查到 ADD_ITEM 留痕；非法 bizType 白名单外值 → 400。"""
    tid = _seed_term(db_mode)
    cid = _seed_class(db_mode, "软件2604")
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/schedule-batches", headers=hdr,
                      json={"termId": str(tid), "batchName": "2026秋课表-调整记录"}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json={
        "courseName": "大学英语", "classId": str(cid), "className": "软件2604",
        "teacherKey": "T103", "teacherName": "孙老师", "weekday": 4, "slotNo": 1,
        "startWeek": 1, "endWeek": 18})
    assert item.status_code == 200, item.text

    logs = client.get(f"{BASE}/schedule/adjustments", headers=hdr, params={"bizType": "AA_SCHEDULE"})
    assert logs.status_code == 200, logs.text
    data = logs.json()["data"]
    assert data["total"] >= 1
    assert any(r["action"] == "ADD_ITEM" for r in data["items"])

    bad = client.get(f"{BASE}/schedule/adjustments", headers=hdr, params={"bizType": "AA_SCHEDULE_CHANGE"})
    assert bad.status_code == 400, bad.text

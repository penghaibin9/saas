"""13B-P3 培养方案发布 + 教学任务全链 · 端到端。

TT1 全链：建课ENABLED→方案→提交(学分校验)→两审→发布→绑年级→生成任务→分配教师→教师确认→批次提交APPROVED；
TT2 生成幂等；TT3 学分不达标禁提交方案；TT4 批次含未分配任务禁提交。

Tier1 R1（续工）新增：
TT5 两级确认链 college-confirm→review APPROVE，教师已确认任务同步置 READY，统计口径联动；
TT6 教务终审 RETURN→批次退回学院重新核对→再次 college-confirm 成功；
TT7 合班（2 任务合一）→拆班（还原为 2 条独立任务）；
TT8 合班校验：不足 2 条 400、跨课程 400、重复合并 409；
TT9 跨批次任务列表 mergeable 过滤 + 教师本人任务确认（含越权 403 NO_DATA_SCOPE）。
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
    from app.models import SchoolClass
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    ids = {"class": a.id}
    db.commit()
    db.close()
    return ids


def _enabled_course(client, hdr, code="TT101", credit=4):
    cid = client.post(f"{BASE}/courses", headers=hdr, json={
        "courseCode": code, "courseName": "程序设计", "category": "MAJOR_CORE", "nature": "REQUIRED",
        "credit": credit, "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,
        "examMode": "EXAM"}).json()["data"]["courseId"]
    client.post(f"{BASE}/courses/{cid}/submit", headers=hdr)
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/courses/{cid}/review", headers=hdr, json={"action": "APPROVE"})
    return cid


def _published_bound_program(client, hdr, course_id, class_id, total=4):
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "软件技术2026方案", "majorId": "1", "gradeYear": "2026",
        "totalCredits": total}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(course_id), "courseName": "程序设计", "openTermNo": 1,
        "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # PUBLISHED
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={
        "gradeYear": "2026", "classId": str(class_id)})  # ENABLED + ACTIVE binding
    return pid


def _term(client, hdr):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2026-2027", "termNo": 1}).json()["data"]["termId"]


def _seed_two_classes(db_mode):
    """Tier1 R1 合班测试用：同专业 2 个行政班，供同课程生成 2 条教学任务后合班。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2602", grade="2026", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    ids = {"class1": a.id, "class2": b.id}
    db.commit()
    db.close()
    return ids


def test_tt1_full_chain(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    g = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g["data"]["tasksGenerated"] == 1
    bid = g["data"]["batchId"]
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    task_id = tasks[0]["taskId"]
    assert tasks[0]["weeklyHours"]  # 周学时已算(64/18)
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
                json={"teacherName": "王老师", "expectedStudents": 40})
    r = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=hdr,
                    json={"action": "CONFIRM"}).json()
    assert r["data"]["status"] == "TEACHER_CONFIRMED"
    b = client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=hdr).json()
    assert b["data"]["status"] == "APPROVED"


def test_tt2_generate_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr)
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    g1 = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g1["data"]["tasksGenerated"] == 1
    g2 = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g2["data"]["tasksGenerated"] == 0  # 幂等，不重复生成


def test_tt3_program_credit_shortfall_blocks_submit(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT301")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "学分不足方案", "majorId": "1", "totalCredits": 120}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "程序设计", "credit": 4})  # 仅4学分 << 120
    assert client.post(f"{BASE}/programs/{pid}/submit", headers=hdr).status_code == 400


def test_tt4_batch_submit_with_unassigned_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT401")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    # 未分配任何教师就提交 → 409
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/submit", headers=hdr).status_code == 409


def test_tt5_two_level_confirm_approve_ready(client, db_mode):
    """学院核对确认 college-confirm → 教务终审 review APPROVE：教师已确认任务同步置 READY，统计联动。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT501")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    task_id = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks",
                         headers=hdr).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
               json={"teacherName": "王老师", "teacherKey": "academic01", "expectedStudents": 40})
    client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=hdr, json={"action": "CONFIRM"})
    cc = client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=hdr)
    assert cc.status_code == 200 and cc.json()["data"]["status"] == "COLLEGE_CONFIRMED"
    rv = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr, json={"action": "APPROVE"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "APPROVED"
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    assert tasks[0]["status"] == "READY"
    stats = client.get(f"{BASE}/teaching-task-batches/stats", headers=hdr).json()["data"]
    assert stats["taskByStatus"].get("READY") == 1
    assert stats["assignRate"]["numerator"] == 1 and stats["teacherConfirmRate"]["numerator"] == 1


def test_tt6_review_return_then_reconfirm(client, db_mode):
    """教务终审 RETURN → 批次退回学院（原因必填≥5字）→ 再次 college-confirm 成功。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT601")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    task_id = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks",
                         headers=hdr).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr, json={"teacherName": "王老师"})
    # 原因过短 → 400
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=hdr).status_code == 200
    bad = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                      json={"action": "RETURN", "reason": "短"})
    assert bad.status_code == 400
    rv = client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                     json={"action": "RETURN", "reason": "教师工作量超限需重新安排"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "RETURNED"
    # COLLEGE_CONFIRMED 状态下不可再次终审
    assert client.post(f"{BASE}/teaching-task-batches/{bid}/review", headers=hdr,
                       json={"action": "APPROVE"}).status_code == 409
    again = client.post(f"{BASE}/teaching-task-batches/{bid}/college-confirm", headers=hdr)
    assert again.status_code == 200 and again.json()["data"]["status"] == "COLLEGE_CONFIRMED"


def test_tt7_merge_then_split(client, db_mode):
    """合班：2 条同课程任务合一（人数相加）→ 拆班：还原为 2 条独立任务（各自人数不变）。"""
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT701")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "合班测试方案", "majorId": "1", "gradeYear": "2026", "totalCredits": 4}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "程序设计", "openTermNo": 1, "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    # 注：bind_grade 对同(major,gradeYear)会把旧绑定置 SUPERSEDED（既有语义），故用不同 gradeYear
    # 让两个班级的绑定同时 ACTIVE，从而在同一批次生成同课程 2 条任务用于合班测试。
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026", "classId": str(ids["class1"])})
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026B", "classId": str(ids["class2"])})
    tid = _term(client, hdr)
    g = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g["data"]["tasksGenerated"] == 2
    bid = g["data"]["batchId"]
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{t1}/assign", headers=hdr, json={"teacherName": "王老师", "expectedStudents": 20})
    client.post(f"{BASE}/teaching-tasks/{t2}/assign", headers=hdr, json={"teacherName": "王老师", "expectedStudents": 25})
    m = client.post(f"{BASE}/teaching-tasks/merge", headers=hdr, json={"taskIds": [t1, t2], "note": "小班合并授课"})
    assert m.status_code == 200
    survivor = m.json()["data"]
    assert survivor["taskId"] == t1 and survivor["isMerged"] is True and survivor["expectedStudents"] == 45
    after_merge = {r["taskId"]: r for r in
                   client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]}
    assert after_merge[t2]["status"] == "MERGED" and after_merge[t2]["mergedIntoId"] == t1
    s = client.post(f"{BASE}/teaching-tasks/{t1}/split", headers=hdr)
    assert s.status_code == 200
    split_row = s.json()["data"]
    assert split_row["isMerged"] is False and split_row["expectedStudents"] == 20
    after_split = {r["taskId"]: r for r in
                   client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]}
    assert after_split[t2]["status"] == "PENDING_ASSIGN" and after_split[t2]["expectedStudents"] == 25


def test_tt8_merge_validation(client, db_mode):
    """合班校验：不足 2 条→400；跨课程→400；已并入他行的成员再次合并→409。"""
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    c1 = _enabled_course(client, hdr, code="TT801")
    c2 = _enabled_course(client, hdr, code="TT802")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "跨课程校验方案", "majorId": "1", "gradeYear": "2026", "totalCredits": 8}).json()["data"]["programId"]
    for c in (c1, c2):
        client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
            "courseId": str(c), "courseName": "课程", "openTermNo": 1, "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026", "classId": str(ids["class1"])})
    tid = _term(client, hdr)
    g = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    assert g["data"]["tasksGenerated"] == 2  # 同班 2 门课程
    bid = g["data"]["batchId"]
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=hdr, json={"taskIds": [t1]}).status_code == 400
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=hdr,
                       json={"taskIds": [t1, t2]}).status_code == 400  # 跨课程
    # 构造「已并入他行」场景：同课程另生成一个批次做真实合班，再重复合并触发 409
    ids2 = _seed_two_classes(db_mode)
    cid3 = _enabled_course(client, hdr, code="TT803")
    pid2 = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "重复合并校验方案", "majorId": "1", "gradeYear": "2027", "totalCredits": 4}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid2}/courses", headers=hdr, json={
        "courseId": str(cid3), "courseName": "课程", "openTermNo": 1, "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid2}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid2}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid2}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid2}/bind", headers=hdr, json={"gradeYear": "2027", "classId": str(ids2["class1"])})
    client.post(f"{BASE}/programs/{pid2}/bind", headers=hdr, json={"gradeYear": "2027B", "classId": str(ids2["class2"])})
    tid2 = client.post(f"{BASE}/terms", headers=hdr, json={"yearCode": "2027-2028", "termNo": 1}).json()["data"]["termId"]
    g2 = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid2)}).json()
    bid2 = g2["data"]["batchId"]
    # 注：generate_batch 现状按「全部 ENABLED 方案」生成（不按 term 过滤方案适用性，既有行为，非本轮改动
    # 范围）；本批次也会连带生成前一段仍 ENABLED 的 pid 方案任务，这里按 courseId 精确过滤出 cid3 的 2 条。
    t3, t4 = [r["taskId"] for r in
             client.get(f"{BASE}/teaching-task-batches/{bid2}/tasks", headers=hdr).json()["data"]["items"]
             if r["courseId"] == str(cid3)]
    assert client.post(f"{BASE}/teaching-tasks/merge", headers=hdr,
                       json={"taskIds": [t3, t4]}).status_code == 200
    dup = client.post(f"{BASE}/teaching-tasks/merge", headers=hdr, json={"taskIds": [t3, t4]})
    assert dup.status_code == 409


def test_tt9_cross_batch_list_and_teacher_scope(client, db_mode):
    """跨批次列表 mergeable 过滤；教师任务确认按本人 teacherKey 收敛，越权 403 NO_DATA_SCOPE。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT901")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    task_id = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks",
                         headers=hdr).json()["data"]["items"][0]["taskId"]
    mergeable = client.get(f"{BASE}/teaching-tasks", headers=hdr, params={"mergeable": True}).json()["data"]["items"]
    assert any(r["taskId"] == task_id for r in mergeable)
    # 分配给「赵敏」（mock 教师账号 academic01，loginName=academic01）
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
               json={"teacherName": "赵敏", "teacherKey": "academic01"})
    # 无关教师（teacher01）确认他人任务 → 403 NO_DATA_SCOPE
    other_hdr = _hdr(client, "teacher01")
    forbidden = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=other_hdr,
                            json={"action": "CONFIRM"})
    assert forbidden.status_code == 403
    # 本人（academic01）确认 → 200，且「我的任务」列表可见
    self_hdr = _hdr(client, "academic01")
    ok = client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=self_hdr, json={"action": "CONFIRM"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "TEACHER_CONFIRMED"
    mine = client.get(f"{BASE}/teaching-tasks", headers=self_hdr, params={"mine": True}).json()["data"]["items"]
    assert any(r["taskId"] == task_id for r in mine)


def test_tt10_adjust_task_partial_update_and_teacher_reconfirm(client, db_mode):
    """教学任务调整（续工新增）：原因过短 400；仅调学时不影响已确认状态；重复提交无实际变化 400；
    变更教师身份强制退回 ASSIGNED 要求重新确认。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT1001")
    _published_bound_program(client, hdr, cid, ids["class"])
    tid = _term(client, hdr)
    bid = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                      json={"termId": str(tid)}).json()["data"]["batchId"]
    task_id = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks",
                         headers=hdr).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{task_id}/assign", headers=hdr,
               json={"teacherName": "王老师", "teacherKey": "academic01", "expectedStudents": 40})
    client.post(f"{BASE}/teaching-tasks/{task_id}/teacher-act", headers=hdr, json={"action": "CONFIRM"})
    # 原因过短 → 400
    bad = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=hdr,
                      json={"weeklyHours": 5, "reason": "短"})
    assert bad.status_code == 400
    # 仅调学时（不动教师）：教师已确认状态保持不变（不强制重新确认）
    r1 = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=hdr,
                     json={"weeklyHours": 6, "totalHours": 108, "reason": "教学计划课时数校正"})
    assert r1.status_code == 200
    d1 = r1.json()["data"]
    assert d1["weeklyHours"] == 6 and d1["totalHours"] == 108 and d1["status"] == "TEACHER_CONFIRMED"
    # 提交内容与当前值完全相同（无实际变化）→ 400，不产生空审计
    noop = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=hdr,
                       json={"weeklyHours": 6, "reason": "重复提交校验"})
    assert noop.status_code == 400
    # 变更教师身份：强制退回 ASSIGNED 要求新教师重新确认
    r2 = client.post(f"{BASE}/teaching-tasks/{task_id}/adjust", headers=hdr,
                     json={"teacherName": "李老师", "teacherKey": "academic02", "reason": "原教师休产假换人代课"})
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["teacherName"] == "李老师" and d2["status"] == "ASSIGNED"


def test_tt11_adjust_task_conflicts_and_permission(client, db_mode):
    """教学任务调整校验：已合班并入的成员任务不可调整 409；已生成课表项的任务不可调整 409；
    无 academicAffairs 权限角色（学生）403。"""
    ids = _seed_two_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _enabled_course(client, hdr, code="TT1101")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "调整校验方案", "majorId": "1", "gradeYear": "2026", "totalCredits": 4}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseId": str(cid), "courseName": "程序设计", "openTermNo": 1, "module": "专业核心", "credit": 4})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026", "classId": str(ids["class1"])})
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026B", "classId": str(ids["class2"])})
    tid = _term(client, hdr)
    g = client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr, json={"termId": str(tid)}).json()
    bid = g["data"]["batchId"]
    tasks = client.get(f"{BASE}/teaching-task-batches/{bid}/tasks", headers=hdr).json()["data"]["items"]
    t1, t2 = tasks[0]["taskId"], tasks[1]["taskId"]
    client.post(f"{BASE}/teaching-tasks/{t1}/assign", headers=hdr, json={"teacherName": "王老师"})
    client.post(f"{BASE}/teaching-tasks/{t2}/assign", headers=hdr, json={"teacherName": "王老师"})
    client.post(f"{BASE}/teaching-tasks/merge", headers=hdr, json={"taskIds": [t1, t2]})
    # t2 现为 MERGED 成员 → 调整应 409
    merged_adjust = client.post(f"{BASE}/teaching-tasks/{t2}/adjust", headers=hdr,
                                json={"weeklyHours": 4, "reason": "尝试调整已并入成员任务"})
    assert merged_adjust.status_code == 409
    # survivor(t1) 已生成课表项 → 调整应 409（须先在排课模块处理课表项）
    sb = client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": str(tid)}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{sb}/items", headers=hdr, json={
        "taskId": str(t1), "weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
        "teacherKey": "academic01", "teacherName": "王老师", "classId": str(ids["class1"]), "className": "软件2601",
        "classroom": "A101", "courseName": "程序设计"})
    assert item.status_code == 200
    scheduled_adjust = client.post(f"{BASE}/teaching-tasks/{t1}/adjust", headers=hdr,
                                   json={"weeklyHours": 4, "reason": "已排课后尝试调整教学任务"})
    assert scheduled_adjust.status_code == 409
    # 无权限角色（学生，空权限集）→ 403
    stu = _hdr(client, "student01")
    forbidden = client.post(f"{BASE}/teaching-tasks/{t1}/adjust", headers=stu,
                            json={"weeklyHours": 4, "reason": "越权尝试调整教学任务"})
    assert forbidden.status_code == 403

"""13B-R1 成绩审核发布更正 · 状态机/权限/数据范围/更正流程 端到端（真实 DB 模式）。

RF1 学院退回→重提→通过→发布 全链路；RF2 退回原因<5字422；RF3 教师跨范围403；
RF4 ACADEMIC_TEACHER 无教务终审权限(即使有academicAffairs.*通配)403；
RF5 归档后更正409；RF6 更正学院驳回原值不变；RF7 更正两级通过新值生效+source=CHANGE；
RF8 学生令牌全端点403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, n=1):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2602", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(tenant_id=TID, student_no=f"RF{i:03d}", real_name=f"审核{i}", class_id=a.id,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    db.close()
    return sids


def _task(client, hdr, usual=30, final=70):
    return client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": "大学物理", "termCode": "2026-2027-1", "credit": 3,
        "usualRatio": usual, "finalRatio": final}).json()["data"]["gradeTaskId"]


def test_rf1_return_resubmit_approve_publish(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 200
    # 学院退回
    ret = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr,
                      json={"action": "RETURN", "reason": "分数需复核确认"})
    assert ret.status_code == 200 and ret.json()["data"]["status"] == "RETURNED"
    # 退回后可重新录入+重提
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 75, "finalScore": 80})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr).status_code == 200
    appr = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    assert appr.status_code == 200 and appr.json()["data"]["status"] == "ACADEMIC_REVIEW"
    pub = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"


def test_rf2_return_reason_too_short_422(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    r = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "RETURN", "reason": "短"})
    assert r.status_code in (400, 422)


def test_rf3_teacher_cross_course_scope_403(client, db_mode):
    """教师A建的任务，教师B（academic01）无法录入——COURSE 数据范围真实生效。"""
    sids = _seed(db_mode, 1)
    admin_hdr = _hdr(client, "school_admin01")
    tid = _task(client, admin_hdr)  # school_admin01 创建，teacher_key 归属于它，不归属 academic01
    teacher_hdr = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=teacher_hdr,
                    json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    assert r.status_code == 403


def test_rf4_teacher_cannot_publish_even_with_wildcard_403(client, db_mode):
    """ACADEMIC_TEACHER 拥有 academicAffairs.* 权限点通配，但发布是教务处终审专属角色动作，
    端点内角色白名单必须拦截——验证"权限点通配不能代替角色收敛"的设计生效。
    学院审核步骤改用 school_admin01（_REVIEW_ROLES 豁免数据范围）推进状态，避免教师本身
    因 COLLEGE 数据范围未配置而在审核步骤就先被拦下，干扰本测试要验证的目标点。"""
    sids = _seed(db_mode, 1)
    teacher_hdr = _hdr(client, "academic01")
    admin_hdr = _hdr(client, "school_admin01")
    tid = client.post(f"{BASE}/grade-tasks", headers=teacher_hdr, json={
        "courseName": "英语", "termCode": "2026-2027-1", "usualRatio": 30, "finalRatio": 70
    }).json()["data"]["gradeTaskId"]
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=teacher_hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    assert client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=teacher_hdr).status_code == 200
    appr = client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=admin_hdr, json={"action": "APPROVE"})
    assert appr.status_code == 200 and appr.json()["data"]["status"] == "ACADEMIC_REVIEW"
    assert client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=teacher_hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/{tid}/archive", headers=teacher_hdr).status_code == 403


def test_rf5_archived_change_request_409(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/archive", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    db.close()
    r = client.post(f"{BASE}/grade-tasks/{tid}/records/{rec.id}/change-request", headers=hdr,
                    json={"newFinalScore": 85, "reason": "重新核算成绩"})
    assert r.status_code == 409


def test_rf6_change_reject_keeps_original(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})  # 80
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    rid = rec.id
    db.close()
    cr = client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
                     json={"newFinalScore": 60, "reason": "疑似录入错误需核实"})
    assert cr.status_code == 200
    rj = client.post(f"{BASE}/grade-change/{rid}/college-review", headers=hdr,
                     json={"action": "REJECT", "reason": "核实后原分数无误"})
    assert rj.status_code == 200
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    assert any(g["courseName"] == "大学物理" and g["score"] == 80 for g in tr["items"])  # 原值保留


def test_rf7_change_two_level_approve_new_value_applied(client, db_mode):
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 60, "finalScore": 60})  # 60 PASSED(边界)
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaGradeRecord
    db = get_sessionmaker()()
    rec = db.query(AaGradeRecord).filter(AaGradeRecord.task_id == int(tid)).first()
    rid = rec.id
    db.close()
    client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
               json={"newFinalScore": 30, "reason": "复核发现期末分录入错误"})  # 60*.3+30*.7=39 FAIL
    client.post(f"{BASE}/grade-change/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    fin = client.post(f"{BASE}/grade-change/{rid}/academic-review", headers=hdr, json={"action": "APPROVE"})
    assert fin.status_code == 200
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=hdr).json()["data"]
    row = next(g for g in tr["items"] if g["courseName"] == "大学物理")
    assert row["score"] == 39 and row["passStatus"] == "FAILED" and row["source"] == "CHANGE"


def test_rf8_student_forbidden_on_new_endpoints_403(client, db_mode):
    """越权红线：新增的提交/学院审/退回/归档/更正端点，学生令牌一律403。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/grade-tasks/1/submit", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/college-review", headers=hdr, json={"action": "APPROVE"}).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/return", headers=hdr, json={"reason": "占位原因文本"}).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/archive", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/grade-tasks/1/records/1/change-request", headers=hdr,
                       json={"reason": "占位原因文本"}).status_code == 403
    assert client.get(f"{BASE}/grade-tasks/1/roster", headers=hdr).status_code == 403

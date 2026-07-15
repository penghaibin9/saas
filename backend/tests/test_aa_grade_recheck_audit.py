"""教务中心「成绩审核发布更正」07/08 号三级补建：成绩复核 / 成绩操作审计 · 端到端（真实 MySQL）。

不新增状态机、不新增表；两项均在既有 R1 骨架（create_grade_task/enter_score/submit_task/
college_review/publish_grades/change_request/_change_review/change_academic_review 已实现的
_audit() 调用）之上做只读扩展：
  - 07 成绩复核：GET /grade-tasks/{taskId}/records 扩展 recordId/source/更正前值/更正原因/
    更正时间/版本号字段（list_records 纯字段扩展，向后兼容）。
  - 08 成绩操作审计：新增 GET /grade-views/audit（读 t_affairs_audit_trail，biz_type=AA_GRADE_*）。

RA1 成绩明细复核：发布后 source=PUBLISH，更正两级通过后 source=CHANGE 且更正前值/原因/时间留痕；
RA2 审计正常路径：教务处角色可查全量，任务生命周期事件均可按 bizType 过滤查到；
RA3 审计数据范围：任课教师仅能自查本人操作，看不到其他教师的操作记录；
RA4 审计越权：学生令牌 403。
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
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2603", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(tenant_id=TID, student_no=f"RA{i:03d}", real_name=f"复核{i}", class_id=a.id,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
        db.add(s); db.flush(); sids.append(s.id)
    db.commit()
    db.close()
    return sids


def _task(client, hdr, course_name="大学英语", usual=30, final=70):
    return client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "courseName": course_name, "termCode": "2026-2027-1", "credit": 3,
        "usualRatio": usual, "finalRatio": final}).json()["data"]["gradeTaskId"]


def test_ra1_records_show_source_and_change_history(client, db_mode):
    """RA1：复核明细字段随流程推进真实变化——录入阶段 source 未标记 PUBLISH/CHANGE；
    发布后 source=PUBLISH；两级更正通过后 source=CHANGE，且更正前总评/原因/时间/版本号留痕可查。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 70, "finalScore": 80})  # 总评77
    before = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert len(before) == 1
    rec0 = before[0]
    assert rec0["recordId"] and rec0["totalScore"] == 77 and rec0["source"] != "PUBLISH"
    assert rec0["prevTotalScore"] is None and rec0["changeReason"] == "" and rec0["versionNo"] == 1

    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    client.post(f"{BASE}/grade-tasks/{tid}/college-review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=hdr)
    after_publish = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"][0]
    assert after_publish["source"] == "PUBLISH"

    rid = after_publish["recordId"]
    cr = client.post(f"{BASE}/grade-tasks/{tid}/records/{rid}/change-request", headers=hdr,
                     json={"newFinalScore": 90, "reason": "复核发现期末分登记错误"})  # 70*.3+90*.7=84
    assert cr.status_code == 200, cr.text
    client.post(f"{BASE}/grade-change/{rid}/college-review", headers=hdr, json={"action": "APPROVE"})
    fin = client.post(f"{BASE}/grade-change/{rid}/academic-review", headers=hdr, json={"action": "APPROVE"})
    assert fin.status_code == 200, fin.text

    after_change = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"][0]
    assert after_change["recordId"] == rid
    assert after_change["source"] == "CHANGE"
    assert after_change["totalScore"] == 84
    assert after_change["prevTotalScore"] == 77  # 更正前总评留痕
    assert after_change["changeReason"] == "复核发现期末分登记错误"
    assert after_change["changeAt"]
    assert after_change["versionNo"] == 2  # 首次更正后版本号自增


def test_ra2_audit_full_lifecycle_visible_to_academic_admin_with_biztype_filter(client, db_mode):
    """RA2：SCHOOL_ADMIN（_REVIEW_ROLES 白名单，等同教务处终审权限）可查看成绩任务全生命周期审计事件；
    bizType 过滤真实生效——过滤到 AA_GRADE_TASK 时排除同租户下已存在的 AA_GRADE_TRANSCRIPT 行（反之亦然），
    不是「传了参数但服务端没用上」。"""
    sids = _seed(db_mode, 1)
    hdr = _hdr(client, "school_admin01")
    tid = _task(client, hdr, course_name="审计用课程")
    client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr,
               json={"studentId": str(sids[0]), "usualScore": 80, "finalScore": 80})
    client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=hdr)
    exp = client.post(f"{BASE}/students/{sids[0]}/transcript/export", headers=hdr, json={"purpose": "测试审计过滤"})
    assert exp.status_code == 200, exp.text

    r_all = client.get(f"{BASE}/grade-views/audit", headers=hdr, params={"pageSize": 100})
    assert r_all.status_code == 200, r_all.text
    all_items = r_all.json()["data"]["items"]
    task_actions = {it["action"] for it in all_items if it["bizId"] == tid and it["bizType"] == "AA_GRADE_TASK"}
    assert {"CREATE", "ENTER", "SUBMIT"}.issubset(task_actions)
    assert any(it["bizType"] == "AA_GRADE_TRANSCRIPT" and it["action"] == "EXPORT" for it in all_items)
    assert all(it["detail"] == "审计用课程" for it in all_items if it["action"] == "CREATE" and it["bizId"] == tid)

    r_task_only = client.get(f"{BASE}/grade-views/audit", headers=hdr,
                             params={"bizType": "AA_GRADE_TASK", "pageSize": 100})
    assert r_task_only.status_code == 200
    task_only_items = r_task_only.json()["data"]["items"]
    assert len(task_only_items) >= 3
    assert all(it["bizType"] == "AA_GRADE_TASK" for it in task_only_items)  # 未被 TRANSCRIPT 行污染

    r_transcript_only = client.get(f"{BASE}/grade-views/audit", headers=hdr,
                                   params={"bizType": "AA_GRADE_TRANSCRIPT", "pageSize": 100})
    assert r_transcript_only.status_code == 200
    transcript_items = r_transcript_only.json()["data"]["items"]
    assert len(transcript_items) == 1 and transcript_items[0]["action"] == "EXPORT"


def test_ra3_teacher_sees_only_own_operator_audit_rows(client, db_mode):
    """RA3：任课教师（COURSE 自查）看不到其他教师/管理员建的任务审计行，只看得到操作人=本人的记录——
    真实数据范围收敛，不是权限点通配即可放行。"""
    _seed(db_mode, 1)
    teacher_hdr = _hdr(client, "academic01")   # 赵敏 ACADEMIC_TEACHER
    admin_hdr = _hdr(client, "school_admin01")  # 陈校 SCHOOL_ADMIN
    own_tid = _task(client, teacher_hdr, course_name="教师自建课程")
    other_tid = _task(client, admin_hdr, course_name="管理员建的课程")
    assert own_tid != other_tid

    r = client.get(f"{BASE}/grade-views/audit", headers=teacher_hdr,
                   params={"bizType": "AA_GRADE_TASK", "pageSize": 100})
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert any(it["bizId"] == own_tid and it["action"] == "CREATE" for it in items)
    assert all(it["bizId"] != other_tid for it in items)
    assert all(it["operator"] == "赵敏" for it in items)


def test_ra4_student_forbidden_on_audit_endpoint_403(client, db_mode):
    """RA4：越权红线——学生令牌访问成绩操作审计一律 403（权限点门禁，早于服务层角色分层生效）。"""
    hdr = _hdr(client, "student01")
    r = client.get(f"{BASE}/grade-views/audit", headers=hdr)
    assert r.status_code == 403

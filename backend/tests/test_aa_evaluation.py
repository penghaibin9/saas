"""教学评价（/academic-affairs/evaluation/*）端点测试。

覆盖全链路：建批次→生成应评任务(挂教学任务)→发布→开放→提交(学生匿名多份)→关闭核算(均分分级)→
发布结果→教师查本人结果→申诉→审核；无任务不可发布400、非开放窗口提交409、匿名不存学生身份、学生越权403。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§8/§10。
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
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=1, course_name="高等数学",
                        teacher_key="counselor01", teacher_name="王老师")
    db.add(tt); db.flush()
    ids = {"term": term.id, "task": tt.id}
    db.commit(); db.close()
    return ids


def test_ev1_full_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin,
                      json={"batchName": "2024秋评教", "termId": str(ids["term"]),
                            "template": {"items": [{"q": "教学态度", "type": "scale5"}]}}).json()["data"]["batchId"]
    # 生成应评任务
    gen = client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin,
                      json={"teachingTaskIds": [str(ids["task"])]}).json()
    assert gen["data"]["taskCount"] == 1
    tasks = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin).json()["data"]["items"]
    tid_ = tasks[0]["taskId"]
    # 发布→开放
    client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    assert client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin).json()["data"]["status"] == "OPEN"
    # 学生匿名提交 2 份（90 和 80）
    for sn, sc in (("EV01", 90), ("EV02", 80)):
        r = client.post(f"{BASE}/evaluation/submit", headers=_stu_token("学生", sn),
                        json={"taskId": tid_, "objectiveScore": sc,
                              "answers": {"教学态度": 5}, "comment": "很好"}).json()
        assert r["code"] == 0
    # 关闭核算 → 均分 85 → GOOD
    assert client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin).json()["data"]["status"] == "RESULT_READY"
    # 发布结果
    client.post(f"{BASE}/evaluation/batches/{bid}/publish-results", headers=admin)
    results = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"]
    assert len(results) == 1 and results[0]["studentAvg"] == 85.0 and results[0]["level"] == "GOOD" and results[0]["studentCount"] == 2
    # 匿名校验：record 不存学生身份
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationRecord
    db = get_sessionmaker()()
    recs = db.query(AaEvaluationRecord).filter(AaEvaluationRecord.tenant_id == TID,
                                               AaEvaluationRecord.evaluator_type == "STUDENT").all()
    assert len(recs) == 2 and all(not hasattr(r, "evaluator_key") or getattr(r, "evaluator_key", None) is None for r in recs)
    db.close()
    # 教师查本人结果（已发布）
    my = client.get(f"{BASE}/evaluation/batches/{bid}/my-results", headers=_hdr(client, "counselor01")).json()["data"]["items"]
    assert any(x["level"] == "GOOD" for x in my)
    # 归档
    assert client.post(f"{BASE}/evaluation/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_ev_multisource_composite(client, db_mode):
    """多来源评教(正方教师端5.x)：学生均分 + 督导评价 → 按权重合成综合分，level 取综合分。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin,
                      json={"batchName": "多来源评教", "termId": str(ids["term"])}).json()["data"]["batchId"]
    # 生成 学生 + 督导 两类应评任务
    # 督导类必须走 /role-tasks 并指定 evaluatorKey（/tasks 仅限 STUDENT：非 STUDENT 类型若从
    # /tasks 生成将没有 evaluator_key，submit_evaluation 的越权校验会导致永远无法提交，见服务层注释）。
    g1 = client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin,
                     json={"teachingTaskIds": [str(ids["task"])], "evaluatorType": "STUDENT"}).json()
    assert g1["data"]["taskCount"] == 1 and g1["data"]["evaluatorType"] == "STUDENT"
    g2 = client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=admin,
                     json={"evaluatorType": "SUPERVISOR",
                           "assignments": [{"teachingTaskId": str(ids["task"]), "evaluatorKey": "school_admin01"}]}).json()
    assert g2["data"]["taskCount"] == 1
    client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin)
    stu_task = client.get(f"{BASE}/evaluation/batches/{bid}/tasks?evaluatorType=STUDENT",
                          headers=admin).json()["data"]["items"][0]["taskId"]
    sup_task = client.get(f"{BASE}/evaluation/batches/{bid}/tasks?evaluatorType=SUPERVISOR",
                          headers=admin).json()["data"]["items"][0]["taskId"]
    for sn, sc in (("EVM1", 90), ("EVM2", 80)):  # 学生均分 85
        client.post(f"{BASE}/evaluation/submit", headers=_stu_token("学生", sn),
                    json={"taskId": stu_task, "objectiveScore": sc, "answers": {"x": 5}})
    # 督导 95：evaluatorKey="school_admin01" 命中 admin 登录身份的 _derive_keys，本人可提交
    sup_resp = client.post(f"{BASE}/evaluation/submit", headers=admin,
                           json={"taskId": sup_task, "objectiveScore": 95, "answers": {"x": 5}}).json()
    assert sup_resp["code"] == 0, sup_resp
    client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin)
    r = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"][0]
    assert r["studentAvg"] == 85.0 and r["supervisorAvg"] == 95.0 and r["studentCount"] == 2
    # 综合分 = (0.6*85 + 0.2*95) / (0.6+0.2) = 87.5
    assert r["compositeScore"] == 87.5 and r["level"] == "GOOD"


def test_ev2_publish_without_task_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin, json={"batchName": "空评教"}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin).status_code == 400


def test_ev3_submit_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin, json={"batchName": "未开放"}).json()["data"]["batchId"]
    client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin, json={"teachingTaskIds": [str(ids["task"])]})
    tid_ = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)  # PUBLISHED，未 open
    assert client.post(f"{BASE}/evaluation/submit", headers=_stu_token("学生", "EV03"),
                       json={"taskId": tid_, "objectiveScore": 88}).status_code == 409


def test_ev4_appeal_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin,
                      json={"batchName": "申诉评教", "termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin, json={"teachingTaskIds": [str(ids["task"])]})
    tid_ = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin).json()["data"]["items"][0]["taskId"]
    client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin)
    client.post(f"{BASE}/evaluation/submit", headers=_stu_token("学生", "EV04"), json={"taskId": tid_, "objectiveScore": 55})
    client.post(f"{BASE}/evaluation/batches/{bid}/close-score", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid}/publish-results", headers=admin)
    rid = client.get(f"{BASE}/evaluation/batches/{bid}/results", headers=admin).json()["data"]["items"][0]["resultId"]
    # 教师申诉（原因过短 400）
    assert client.post(f"{BASE}/evaluation/appeals", headers=_hdr(client, "counselor01"),
                       json={"resultId": rid, "reason": "x"}).status_code == 400
    aid = client.post(f"{BASE}/evaluation/appeals", headers=_hdr(client, "counselor01"),
                      json={"resultId": rid, "reason": "评分异常，学生恶意打分"}).json()["data"]["appealId"]
    assert client.post(f"{BASE}/evaluation/appeals/{aid}/review", headers=admin,
                       json={"action": "RESOLVE"}).json()["data"]["status"] == "RESOLVED"


def test_ev5_student_cannot_manage_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("学生", "EV05")
    assert client.post(f"{BASE}/evaluation/batches", headers=stu, json={"batchName": "越权"}).status_code == 403

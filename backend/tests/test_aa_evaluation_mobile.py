"""教务中心 · 移动端教学评价（新聚合 affairs_academic_evaluation_my_results 跨批次聚合 +
submit_appeal 归属校验补丁）。全部经 HTTP client 走真库(db_mode)。PC 端既有
list_my_role_tasks/submit_evaluation/list_results 已自带范围校验；本文件专门覆盖移动端
「我的评价任务」提交全流程、「我的结果」跨批次聚合（PC 端本身只有按单个 batchId 查询的
my-results 入口，没有全部聚合），以及移动端在 submit_appeal 上新补的归属校验（PC 端本身
完全不校验 result 是否属于当前教师）。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, teacher_key="academic01", teacher_name="赵敏", code="EVMOB", year_code="2032-2033"):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm, College, Major, SchoolClass
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code=year_code, term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件3201", grade="2032", status="ACTIVE")
    db.add(klass); db.flush()
    co = AaCourse(tenant_id=TID, course_code=code, course_name="移动评教测试课", credit=3, status="ENABLED")
    db.add(co); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="移动评教测试任务批",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co.id, course_name="移动评教测试课",
                        class_id=klass.id, teaching_class_name="软件3201",
                        teacher_key=teacher_key, teacher_name=teacher_name)
    db.add(tt); db.flush()
    tt_id = tt.id
    db.commit(); db.close()
    return {"tt": tt_id}


def _eval_batch_ready_for_submit(client, admin, tt_id):
    """建批次→挂 STUDENT 任务(供出结果用)+SELF 任务(供教师提交)→发布→开放。返回 (bid, taskId[SELF])。"""
    bid = client.post(f"{BASE}/evaluation/batches", headers=admin,
                      json={"batchName": "移动评教测试批次"}).json()["data"]["batchId"]
    client.post(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin,
               json={"teachingTaskIds": [str(tt_id)]})
    client.post(f"{BASE}/evaluation/batches/{bid}/role-tasks", headers=admin,
               json={"evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(tt_id)}]})
    client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin)
    tasks = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin).json()["data"]["items"]
    self_task_id = next(t["taskId"] for t in tasks if t["evaluatorType"] == "SELF")
    return bid, self_task_id


def test_my_tasks_and_submit_flow_via_mobile(client, db_mode):
    """我的评价任务（按 evaluatorType=SELF 匹配本人 evaluator_key）+ 移动端提交全流程。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, task_id = _eval_batch_ready_for_submit(client, admin, ids["tt"])
    hdr = _hdr(client, "academic01")

    mine = client.get(f"{MOB}/teacher/academic/evaluation/tasks", headers=hdr,
                      params={"evaluatorType": "SELF"}).json()
    assert mine["code"] == 0
    assert any(t["taskId"] == task_id for t in mine["data"]["list"])

    sub = client.post(f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit", headers=hdr,
                      json={"objectiveScore": 92, "comment": "本学期教学任务完成良好"})
    assert sub.status_code == 200 and sub.json()["data"]["submittedCount"] == 1

    dup = client.post(f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit", headers=hdr,
                      json={"objectiveScore": 88})
    assert dup.status_code == 409


def test_cross_evaluator_submit_403_via_mobile(client, db_mode):
    """越权：非本任务指定评价人提交 → 403（复用 PC submit_evaluation 内部 evaluator_key 校验）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, task_id = _eval_batch_ready_for_submit(client, admin, ids["tt"])
    other_hdr = _hdr(client, "teacher01")

    r = client.post(f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit", headers=other_hdr,
                    json={"objectiveScore": 80})
    assert r.status_code == 403


def test_my_results_aggregation_and_appeal_ownership_via_mobile(client, db_mode):
    """我的评价结果跨批次聚合（新聚合，PC 端本身没有此入口）+ 申诉归属校验：
    本人结果可申诉；他人结果申诉 → 403（PC 端 submit_appeal 本身对此完全无校验，
    移动端主动收紧，不改 PC）。"""
    ids_a = _seed(db_mode, teacher_key="academic01", teacher_name="赵敏", code="EVMOBA", year_code="2033-2034")
    ids_b = _seed(db_mode, teacher_key="other_teacher", teacher_name="他人", code="EVMOBB", year_code="2034-2035")
    admin = _hdr(client, "school_admin01")

    bid_a, _ = _eval_batch_ready_for_submit(client, admin, ids_a["tt"])
    client.post(f"{BASE}/evaluation/batches/{bid_a}/close-score", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid_a}/publish-results", headers=admin)

    bid_b, _ = _eval_batch_ready_for_submit(client, admin, ids_b["tt"])
    client.post(f"{BASE}/evaluation/batches/{bid_b}/close-score", headers=admin)
    client.post(f"{BASE}/evaluation/batches/{bid_b}/publish-results", headers=admin)

    hdr = _hdr(client, "academic01")
    mine = client.get(f"{MOB}/teacher/academic/evaluation/results", headers=hdr).json()
    assert mine["code"] == 0
    my_results = mine["data"]["list"]
    assert any(r["batchId"] == str(bid_a) for r in my_results)
    assert not any(r["batchId"] == str(bid_b) for r in my_results)
    my_result_id = next(r["resultId"] for r in my_results if r["batchId"] == str(bid_a))

    ok = client.post(f"{MOB}/teacher/academic/evaluation/results/{my_result_id}/appeal", headers=hdr,
                     json={"reason": "评分与实际教学情况不符"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "COLLEGE_REVIEW"

    # other_teacher（种子里的 teacher_key，非 mock 账号登录名）没有对应的 mock 登录账号，
    # 直接查库拿到 bid_b 的 resultId 供越权测试（不影响归属校验本身：越权判定只依赖
    # resultId 对应的 teacher_key 是否命中当前登录人 _derive_keys）。
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationResult
    db = get_sessionmaker()()
    other_result = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.tenant_id == TID, AaEvaluationResult.batch_id == int(bid_b)).first()
    other_result_id = other_result.id
    db.close()

    forbidden = client.post(f"{MOB}/teacher/academic/evaluation/results/{other_result_id}/appeal", headers=hdr,
                            json={"reason": "这不是我的评价结果"})
    assert forbidden.status_code == 403

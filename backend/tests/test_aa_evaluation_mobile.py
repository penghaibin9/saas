"""教务中心 · 移动端教学评价。

覆盖教师移动端“我的评价任务”提交、跨批次结果聚合和申诉归属校验。
历史夹具已对齐正式 termId、APPROVED/READY 教学任务和官方 LOCKED 教学班名单；
移动端权限、重复提交、结果归属与申诉断言保持原强度。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode, teacher_key="academic01", teacher_name="赵敏", code="EVMOB1",
          year_code="2032-2033"):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
        College, Major, SchoolClass, StudentProfile,
    )
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as tc_service

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID,
        year_code=year_code,
        term_no=1,
        term_name=f"{year_code}第1学期",
        teaching_weeks=18,
        status="PUBLISHED",
        is_current=False,
    )
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name=f"软件学院-{code}", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name=f"软件技术-{code}", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name=f"软件班-{code}",
        grade=year_code[:4], status="ACTIVE",
    )
    db.add(klass); db.flush()
    course = AaCourse(
        tenant_id=TID, course_code=code,
        course_name="移动评教测试课", credit=3, status="ENABLED",
    )
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(
        tenant_id=TID, term_id=term.id, batch_name=f"移动评教测试任务批-{code}",
        college_id=col.id, status="APPROVED",
    )
    db.add(task_batch); db.flush()
    task = AaTeachingTask(
        tenant_id=TID, batch_id=task_batch.id,
        course_id=course.id, course_code=course.course_code, course_name=course.course_name,
        class_id=klass.id, teaching_class_name=klass.class_name,
        teacher_key=teacher_key, teacher_name=teacher_name,
        status="READY", weekly_hours=3, total_hours=54,
        start_week=1, end_week=18,
    )
    db.add(task); db.flush()

    student = StudentProfile(
        tenant_id=TID,
        student_no=f"S{int(task.id):05d}",
        real_name="移动评教名单学生",
        college_id=col.id,
        major_id=major.id,
        class_id=klass.id,
        grade=year_code[:4],
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student); db.flush()

    # 该 service 是生产服务，内部通过 _tid() fail-closed 读取请求级租户上下文。
    # 测试夹具直接调用 service 时必须显式提供并恢复上下文，不能依赖上一条 HTTP 请求残留。
    previous_tenant = get_tenant()
    set_tenant({"tenantId": str(TID)})
    try:
        teaching_class = tc_service.ensure_teaching_class_for_task(
            db, int(task.id), initialize_admin_roster=True
        )
    finally:
        set_tenant(previous_tenant)
    db.flush()
    assert teaching_class.roster_status == "LOCKED"
    assert teaching_class.current_roster_version_id is not None

    ids = {"tt": int(task.id), "term": int(term.id)}
    db.commit(); db.close()
    return ids


def _eval_batch_ready_for_submit(client, admin, ids, name="移动评教测试批次"):
    """正式学期建批次→学生匿名任务+SELF 任务→发布→开放。"""
    created = client.post(
        f"{BASE}/evaluation/batches",
        headers=admin,
        json={"batchName": name, "termId": str(ids["term"]), "anonymous": True},
    )
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]

    student_tasks = client.post(
        f"{BASE}/evaluation/batches/{bid}/tasks",
        headers=admin,
        json={"teachingTaskIds": [str(ids["tt"])], "evaluatorType": "STUDENT"},
    )
    assert student_tasks.status_code == 200, student_tasks.text
    self_tasks = client.post(
        f"{BASE}/evaluation/batches/{bid}/role-tasks",
        headers=admin,
        json={"evaluatorType": "SELF", "assignments": [{"teachingTaskId": str(ids["tt"])}]},
    )
    assert self_tasks.status_code == 200, self_tasks.text
    published = client.post(f"{BASE}/evaluation/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text
    opened = client.post(f"{BASE}/evaluation/batches/{bid}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    tasks = client.get(f"{BASE}/evaluation/batches/{bid}/tasks", headers=admin)
    assert tasks.status_code == 200, tasks.text
    rows = tasks.json()["data"]["items"]
    self_task_id = next(t["taskId"] for t in rows if t["evaluatorType"] == "SELF")
    return bid, self_task_id


def test_my_tasks_and_submit_flow_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, task_id = _eval_batch_ready_for_submit(client, admin, ids)
    hdr = _hdr(client, "academic01")

    mine = client.get(
        f"{MOB}/teacher/academic/evaluation/tasks",
        headers=hdr,
        params={"evaluatorType": "SELF"},
    ).json()
    assert mine["code"] == 0
    assert any(t["taskId"] == task_id for t in mine["data"]["list"])

    sub = client.post(
        f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit",
        headers=hdr,
        json={"objectiveScore": 92, "comment": "本学期教学任务完成良好"},
    )
    assert sub.status_code == 200 and sub.json()["data"]["submittedCount"] == 1

    dup = client.post(
        f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit",
        headers=hdr,
        json={"objectiveScore": 88},
    )
    assert dup.status_code == 409


def test_cross_evaluator_submit_403_via_mobile(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, task_id = _eval_batch_ready_for_submit(client, admin, ids)
    other_hdr = _hdr(client, "teacher01")

    r = client.post(
        f"{MOB}/teacher/academic/evaluation/tasks/{task_id}/submit",
        headers=other_hdr,
        json={"objectiveScore": 80},
    )
    assert r.status_code == 403


def test_my_results_aggregation_and_appeal_ownership_via_mobile(client, db_mode):
    ids_a = _seed(
        db_mode, teacher_key="academic01", teacher_name="赵敏",
        code="EVA101", year_code="2033-2034",
    )
    ids_b = _seed(
        db_mode, teacher_key="other_teacher", teacher_name="他人",
        code="EVB101", year_code="2034-2035",
    )
    admin = _hdr(client, "school_admin01")

    bid_a, _ = _eval_batch_ready_for_submit(client, admin, ids_a, name="本人结果批次")
    closed_a = client.post(f"{BASE}/evaluation/batches/{bid_a}/close-score", headers=admin)
    assert closed_a.status_code == 200, closed_a.text
    published_a = client.post(f"{BASE}/evaluation/batches/{bid_a}/publish-results", headers=admin)
    assert published_a.status_code == 200, published_a.text

    bid_b, _ = _eval_batch_ready_for_submit(client, admin, ids_b, name="他人结果批次")
    closed_b = client.post(f"{BASE}/evaluation/batches/{bid_b}/close-score", headers=admin)
    assert closed_b.status_code == 200, closed_b.text
    published_b = client.post(f"{BASE}/evaluation/batches/{bid_b}/publish-results", headers=admin)
    assert published_b.status_code == 200, published_b.text

    hdr = _hdr(client, "academic01")
    mine = client.get(f"{MOB}/teacher/academic/evaluation/results", headers=hdr).json()
    assert mine["code"] == 0
    my_results = mine["data"]["list"]
    assert any(r["batchId"] == str(bid_a) for r in my_results)
    assert not any(r["batchId"] == str(bid_b) for r in my_results)
    my_result_id = next(r["resultId"] for r in my_results if r["batchId"] == str(bid_a))

    ok = client.post(
        f"{MOB}/teacher/academic/evaluation/results/{my_result_id}/appeal",
        headers=hdr,
        json={"reason": "评分与实际教学情况不符"},
    )
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "COLLEGE_REVIEW"

    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationResult

    db = get_sessionmaker()()
    other_result = db.query(AaEvaluationResult).filter(
        AaEvaluationResult.tenant_id == TID,
        AaEvaluationResult.batch_id == int(bid_b),
    ).first()
    assert other_result is not None
    other_result_id = int(other_result.id)
    db.close()

    forbidden = client.post(
        f"{MOB}/teacher/academic/evaluation/results/{other_result_id}/appeal",
        headers=hdr,
        json={"reason": "这不是我的评价结果"},
    )
    assert forbidden.status_code == 403

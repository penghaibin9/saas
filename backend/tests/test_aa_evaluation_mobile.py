"""教务中心 · 移动端教学评价。

覆盖教师移动端“我的评价任务”提交、跨批次结果聚合和申诉归属校验。
历史夹具已对齐正式 termId、APPROVED/READY 教学任务和官方 LOCKED 教学班名单；
移动端权限、重复提交、结果归属与申诉断言保持原强度。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name, *, client_type="TEACHER_MINI"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any", "clientType": client_type}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _student_hdr(real_name, student_no, *, client_type="STUDENT_MINI"):
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name,
        "studentNo": student_no, "userType": "STUDENT",
        "tenantId": str(TID), "tid": "evaluation-mobile",
        "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": client_type,
    })}


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

    ids = {
        "tt": int(task.id), "term": int(term.id),
        "studentNo": student.student_no, "studentName": student.real_name,
    }
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


def test_student_evaluation_mobile_uses_formal_roster_and_actionable_contract(client, db_mode):
    """学生小程序必须拿到正式名单任务的窗口/提交状态，不能落回历史兼容读侧。"""
    ids = _seed(db_mode, code="EVSTU1")
    admin = _hdr(client, "school_admin01")
    _eval_batch_ready_for_submit(client, admin, ids, name="学生移动评教批次")
    student = _student_hdr(ids["studentName"], ids["studentNo"])

    first = client.get(f"{MOB}/academic/evaluation/tasks", headers=student)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["code"] == 0
    row = next(item for item in body["data"]["list"] if item["teachingTaskId"] == str(ids["tt"]))
    assert row["windowStatus"] == "OPEN"
    assert row["submitted"] is False
    assert row["canSubmit"] is True

    submitted = client.post(
        f"{MOB}/academic/evaluation/submit",
        headers=student,
        json={"taskId": row["taskId"], "objectiveScore": 91, "answers": {"overall": 91}},
    )
    assert submitted.status_code == 200, submitted.text

    reread = client.get(f"{MOB}/academic/evaluation/tasks", headers=student).json()
    latest = next(item for item in reread["data"]["list"] if item["taskId"] == row["taskId"])
    assert latest["submitted"] is True
    assert latest["canSubmit"] is False


def test_student_evaluation_mobile_tasks_are_server_paged_and_mobile_scoped(client, db_mode):
    """42 项本人评教任务只能按页读取；深链精确任务不依赖前端本地全量切片。"""
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationBatch, AaEvaluationTask, AaTeachingTask

    ids = _seed(db_mode, code="EVPG1", year_code="2035-2036")
    db = get_sessionmaker()()
    try:
        teaching_task = db.get(AaTeachingTask, ids["tt"])
        for index in range(42):
            batch = AaEvaluationBatch(
                tenant_id=TID, batch_name=f"移动评教分页批次{index:02d}", term_id=ids["term"],
                # 最新 20 个批次已经进入结果阶段：首页第 1 页不能把“当前页没有
                # 待评”错误地写成“本人没有待评”，仍须返回后页的 22 项待办。
                anonymous=True, status="RESULT_READY" if index >= 22 else "OPEN",
            )
            db.add(batch)
            db.flush()
            db.add(AaEvaluationTask(
                tenant_id=TID, batch_id=batch.id, teaching_task_id=teaching_task.id,
                course_id=teaching_task.course_id, course_name=teaching_task.course_name,
                class_id=teaching_task.class_id, teacher_key=teaching_task.teacher_key,
                teacher_name=teaching_task.teacher_name, evaluator_type="STUDENT", status="PENDING",
            ))
        db.commit()
    finally:
        db.close()

    student = _student_hdr(ids["studentName"], ids["studentNo"])
    pages = [client.get(
        f"{MOB}/academic/evaluation/tasks", headers=student,
        params={"page": page, "pageSize": 20},
    ) for page in (1, 2, 3)]
    assert all(response.status_code == 200 for response in pages)
    data = [response.json()["data"] for response in pages]
    assert [(item["pagination"]["page"], item["pagination"]["pageSize"], item["pagination"]["total"], item["pagination"]["hasMore"], len(item["list"])) for item in data] == [
        (1, 20, 42, True, 20), (2, 20, 42, True, 20), (3, 20, 42, False, 2),
    ]
    task_ids = [{item["taskId"] for item in page["list"]} for page in data]
    assert task_ids[0].isdisjoint(task_ids[1]) and task_ids[0].isdisjoint(task_ids[2]) and task_ids[1].isdisjoint(task_ids[2])
    assert [item["pending"] for item in data] == [22, 22, 22]
    assert data[0]["nextPendingTaskId"] not in task_ids[0]
    assert data[0]["nextPendingTaskId"] in task_ids[1]
    focused_id = next(iter(task_ids[2]))
    focused = client.get(
        f"{MOB}/academic/evaluation/tasks", headers=student,
        params={"page": 1, "pageSize": 20, "taskId": focused_id},
    ).json()["data"]
    assert focused["pagination"] == {"page": 1, "pageSize": 20, "total": 1, "hasMore": False}
    assert [item["taskId"] for item in focused["list"]] == [focused_id]

    teacher = _hdr(client, "academic01")
    assert client.get(f"{MOB}/academic/evaluation/tasks", headers=teacher).status_code == 403
    assert client.get(
        f"{MOB}/academic/evaluation/tasks",
        headers=_student_hdr(ids["studentName"], ids["studentNo"], client_type="MP"),
    ).status_code == 403
    assert client.get(
        f"{MOB}/academic/evaluation/tasks",
        headers=_student_hdr(ids["studentName"], ids["studentNo"], client_type="STUDENT_PC"),
    ).status_code == 200


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
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "SUBMITTED"
    assert ok.json()["data"]["currentNode"] == "COLLEGE"

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

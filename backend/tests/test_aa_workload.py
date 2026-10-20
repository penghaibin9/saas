"""教师工作量申报端到端（正方 教师端1.18/1.19 对标）：
教师申报(教学/监考/阅卷/出卷) → 教务台账可见 → 审核通过/驳回 → 通过计入工作量统计 declaredHours。MySQL-only。
"""
from __future__ import annotations

MB = "/api/v1/mobile"
AB = "/api/v1/academic-affairs"
MAIN = 1000000000000000001


def _teacher_token(real_name, login):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{login}", "realName": real_name, "loginName": login, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "ACADEMIC_TEACHER", "clientType": "TEACHER_MINI"})}


def _workload_submit(client, headers, command_key, **body):
    return client.post(f"{MB}/teacher/academic/workload/submit", headers=headers,
                       json={**body, "commandKey": command_key})


def _student_token(login="wl_student"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{login}", "realName": "测试学生", "loginName": login, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "STUDENT_MINI"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_teaching_task(teacher_key, hours=40):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    db.add(AaTeachingTask(tenant_id=MAIN, batch_id=1, course_id=1, course_name="高等数学",
                          teacher_key=teacher_key, teacher_name="王老师", total_hours=hours))
    db.commit(); db.close()


def test_workload_declare_review_and_stats(client, db_mode):
    _seed_teaching_task("wl_teacher", 40)
    hdr = _teacher_token("王老师", "wl_teacher")
    # 课时<=0 → 400
    bad = _workload_submit(client, hdr, "wl_invalid_hours_1", category="INVIGILATE", hours=0)
    assert bad.status_code == 400, bad.text
    # 类别非法 → 400
    bad2 = _workload_submit(client, hdr, "wl_invalid_category_1", category="XXX", hours=6)
    assert bad2.status_code == 400
    # 正常申报
    ok = _workload_submit(client, hdr, "wl_declare_review_1", category="INVIGILATE", hours=6,
                          termCode="2026-1", description="期末监考3场")
    assert ok.status_code == 200, ok.text
    my = client.get(f"{MB}/teacher/academic/workload/my", headers=hdr).json()["data"]["items"]
    assert len(my) == 1 and my[0]["status"] == "SUBMITTED" and my[0]["categoryLabel"] == "监考"
    did = my[0]["declarationId"]
    # 教务台账可见
    admin = _admin(client)
    lst = client.get(f"{AB}/workload-declarations", headers=admin).json()["data"]
    assert any(x["declarationId"] == did for x in lst["items"])
    # 审核通过
    rv = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin, json={"action": "APPROVE"})
    assert rv.status_code == 200 and rv.json()["data"]["status"] == "APPROVED"
    # 计入工作量统计 declaredHours（该教师授课40 + 申报6）
    ws = client.get(f"{AB}/stats/workload", headers=admin).json()["data"]
    row = [r for r in ws["ranking"] if r["teacherKey"] == "wl_teacher"]
    assert row and row[0]["declaredHours"] == 6.0 and row[0]["combinedHours"] == 46.0


def test_workload_reject_requires_reason(client, db_mode):
    hdr = _teacher_token("李老师", "wl_teacher2")
    did = _workload_submit(client, hdr, "wl_reject_reason_1", category="MARKING", hours=4).json()["data"]["declarationId"]
    admin = _admin(client)
    # 驳回原因过短 → 400
    bad = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin, json={"action": "REJECT", "note": "x"})
    assert bad.status_code == 400
    ok = client.post(f"{AB}/workload-declarations/{did}/review", headers=admin,
                     json={"action": "REJECT", "note": "重复申报，已在教学工作量中体现"})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "REJECTED"


def test_workload_teacher_only_sees_own(client, db_mode):
    a = _teacher_token("甲老师", "wl_a")
    b = _teacher_token("乙老师", "wl_b")
    client.post(f"{MB}/teacher/academic/workload/submit", headers=a,
                json={"category": "TEACHING", "hours": 8, "commandKey": "wl_own_scope_a_1"})
    mine_b = client.get(f"{MB}/teacher/academic/workload/my", headers=b).json()["data"]["items"]
    assert mine_b == []


def test_workload_teacher_identity_idempotency_and_receipt_scope(client, db_mode):
    """学生不能写；同一教师同一命令键只落一张正式申报并可只读核对。"""
    teacher = _teacher_token("工作量幂等教师", "wl_idem_teacher")
    command_key = "wl_idempotency_submit_1"
    body = {"category": "INVIGILATE", "hours": 3, "description": "正式监考工作量"}

    student_write = _workload_submit(client, _student_token(), command_key, **body)
    assert student_write.status_code == 403, student_write.text
    student_read = client.get(f"{MB}/teacher/academic/workload/my", headers=_student_token())
    assert student_read.status_code == 403, student_read.text

    first = _workload_submit(client, teacher, command_key, **body)
    replay = _workload_submit(client, teacher, command_key, **body)
    assert first.status_code == replay.status_code == 200, (first.text, replay.text)
    assert first.json()["data"]["declarationId"] == replay.json()["data"]["declarationId"]
    declaration_id = first.json()["data"]["declarationId"]
    mine = client.get(f"{MB}/teacher/academic/workload/my", headers=teacher).json()["data"]
    assert mine["total"] == 1 and [row["declarationId"] for row in mine["items"]] == [declaration_id]

    receipt = client.get(f"{MB}/teacher/academic/workload/command-receipts/{command_key}", headers=teacher)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["data"] == {
        "commandKey": command_key,
        "operation": "WORKLOAD_SUBMIT",
        "state": "SUCCESS",
        "result": first.json()["data"],
    }
    changed = _workload_submit(client, teacher, command_key, category="INVIGILATE", hours=4,
                                description="同键篡改请求")
    assert changed.status_code == 409, changed.text
    other = _teacher_token("另一位教师", "wl_idem_other")
    hidden = client.get(f"{MB}/teacher/academic/workload/command-receipts/{command_key}", headers=other)
    assert hidden.status_code == 200 and hidden.json()["data"]["state"] == "UNRESOLVED"
    assert hidden.json()["data"]["result"] is None


def test_workload_my_uses_independent_server_pages(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaWorkloadDeclaration

    teacher = _teacher_token("工作量分页教师", "wl_paged_teacher")
    db = get_sessionmaker()()
    try:
        for number in range(21):
            db.add(AaWorkloadDeclaration(
                tenant_id=MAIN, teacher_key="wl_paged_teacher", teacher_name="工作量分页教师",
                category="OTHER", hours=number + 1, description=f"分页申报{number + 1}", status="SUBMITTED",
            ))
        db.commit()
    finally:
        db.close()

    first = client.get(f"{MB}/teacher/academic/workload/my", headers=teacher,
                       params={"page": 1, "pageSize": 20})
    second = client.get(f"{MB}/teacher/academic/workload/my", headers=teacher,
                        params={"page": 2, "pageSize": 20})
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    page_one, page_two = first.json()["data"], second.json()["data"]
    assert page_one["total"] == 21 and page_one["page"] == 1 and page_one["pageSize"] == 20
    assert len(page_one["items"]) == 20 and page_one["hasMore"] is True
    assert page_two["page"] == 2 and len(page_two["items"]) == 1 and page_two["hasMore"] is False
    assert {row["declarationId"] for row in page_one["items"]}.isdisjoint(
        {row["declarationId"] for row in page_two["items"]})

def _create_review_probe_declaration(client, login):
    response = _workload_submit(
        client, _teacher_token("工作量审核测试教师", login), f"wl_probe_{login}",
        category="OTHER", hours=2, termCode="2026-1", description="真实审核回执测试",
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["declarationId"]


def test_workload_review_receipt_uses_persisted_mysql_time(client, db_mode, monkeypatch):
    """DATETIME(0) may round .600000; POST and GET must describe the same persisted review."""
    from datetime import datetime
    from app.db.session import get_engine
    from app.modules.academic_affairs.services import academic_affairs_workload_service as service

    assert get_engine().dialect.name == "mysql"
    declaration_id = _create_review_probe_declaration(client, "wl_review_time")
    admin = _admin(client)

    class ReviewClock(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 9, 8, 10, 0, 0, 600000)

    # Only the clock is fixed. Permissions, tenancy, DTO, session and commands remain real.
    monkeypatch.setattr(service, "datetime", ReviewClock)
    response = client.post(
        f"{AB}/workload-declarations/{declaration_id}/review",
        headers=admin, json={"action": "APPROVE"},
    )
    assert response.status_code == 200, response.text
    command = response.json()["data"]
    response = client.get(f"{AB}/workload-declarations", headers=admin, params={"termCode": "2026-1"})
    assert response.status_code == 200, response.text
    persisted = next(row for row in response.json()["data"]["items"] if row["declarationId"] == declaration_id)
    assert command["status"] == persisted["status"] == "APPROVED"
    assert command["reviewedBy"]
    assert command["reviewedAt"]
    for key in ("declarationId", "teacherKey", "teacherName", "termCode", "category", "hours", "description", "createdAt", "status", "reviewNote", "reviewedBy", "reviewedAt"):
        assert command[key] == persisted[key], (key, command[key], persisted[key])


def test_workload_concurrent_reviews_only_one_commits(client, db_mode, monkeypatch):
    """Hold the first real review before commit; a second reviewer must wait then get 409."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from fastapi.testclient import TestClient
    from sqlalchemy import event, select
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_workload_service as service

    engine = get_engine()
    assert engine.dialect.name == "mysql"
    declaration_id = _create_review_probe_declaration(client, "wl_review_race")
    admin = _admin(client)
    first_in_audit, second_read, second_in_audit, release_first = Event(), Event(), Event(), Event()
    real_audit = service._audit

    def audit_gate(db, biz_id, action, detail=""):
        if str(biz_id) == declaration_id:
            if action == "WORKLOAD_APPROVE":
                first_in_audit.set()
                assert release_first.wait(10), "test did not release first review"
            elif action == "WORKLOAD_REJECT":
                second_in_audit.set()
        return real_audit(db, biz_id, action, detail)

    def observe_second_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        text = statement.lower()
        if first_in_audit.is_set() and not release_first.is_set() and text.lstrip().startswith("select") and "t_aa_workload_declaration" in text:
            second_read.set()

    def run(action, note):
        peer = TestClient(client.app)
        try:
            return peer.post(f"{AB}/workload-declarations/{declaration_id}/review", headers=admin, json={"action": action, "note": note})
        finally:
            peer.close()

    monkeypatch.setattr(service, "_audit", audit_gate)
    event.listen(engine, "before_cursor_execute", observe_second_select)
    second_reached_write = False
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, "APPROVE", "")
            try:
                assert first_in_audit.wait(5), "first review never reached the real write transaction"
                second = pool.submit(run, "REJECT", "并发审核应当拒绝覆盖")
                assert second_read.wait(5), "second review never attempted the database read"
                second_reached_write = second_in_audit.wait(0.5)
            finally:
                release_first.set()
            first_response, second_response = first.result(timeout=5), second.result(timeout=5)
    finally:
        release_first.set()
        event.remove(engine, "before_cursor_execute", observe_second_select)

    assert not second_reached_write, "second review passed the still-uncommitted first review"
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 409, second_response.text
    response = client.get(f"{AB}/workload-declarations", headers=admin, params={"termCode": "2026-1"})
    assert response.status_code == 200, response.text
    persisted = next(row for row in response.json()["data"]["items"] if row["declarationId"] == declaration_id)
    assert persisted["status"] == "APPROVED"
    with get_sessionmaker()() as db:
        actions = db.scalars(select(AffairsAuditTrail.action).where(
            AffairsAuditTrail.tenant_id == MAIN,
            AffairsAuditTrail.biz_type == "AA_WORKLOAD_DECL",
            AffairsAuditTrail.biz_id == int(declaration_id),
            AffairsAuditTrail.action.in_(["WORKLOAD_APPROVE", "WORKLOAD_REJECT"]),
        )).all()
    assert actions == ["WORKLOAD_APPROVE"]

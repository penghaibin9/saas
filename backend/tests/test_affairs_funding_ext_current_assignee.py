from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import event, select

from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from test_funding_application_workspace import _accounts

BASE = "/api/v1"
TID = 1000000000000000001


def _application(client, owner, student, domain):
    if domain == "WORK_STUDY":
        post = _data(client.post(BASE + "/student-affairs/work-study/posts", headers=owner,
            json={"deptName": "图书馆", "postName": "范围核验岗位", "headcount": 3}))
        row = _data(client.post(f"{BASE}/portal/affairs/work-study/posts/{post['postId']}/apply",
            headers=student, json={"statement": "本人自愿申请课余服务岗位", "availability": "课余时间", "confirm": True}))
        return row, "recordId", "work-study/records", "APPROVE", "WORK_STUDY_REVIEW"
    if domain == "STUDENT_LOAN":
        row = _data(client.post(BASE + "/portal/affairs/loans", headers=student,
            json={"loanType": "ORIGIN", "yearCode": "2090-2091", "amount": "12000.00",
                  "receiptCode": "TEST-RECEIPT-901234", "confirm": True}))
        return row, "loanId", "loans", "VERIFY", "STUDENT_LOAN_REVIEW"
    evidence = _data(client.post(BASE + "/files", headers=student, data={"bizType": "REDUCTION"},
        files={"file": ("scope-evidence.txt", b"isolated test evidence", "text/plain")}))
    row = _data(client.post(BASE + "/portal/affairs/fee-reductions", headers=student,
        json={"itemType": "TEMP_AID", "yearCode": "2090-2091", "reasonCategory": "FAMILY_CHANGE",
              "amount": "1800.00", "reason": "隔离测试家庭情况变化申请临时补助", "attachmentIds": [evidence["fileId"]], "confirm": True}))
    return row, "feeId", "fee-reductions", "APPROVE", "FEE_REDUCTION_REVIEW"


@pytest.mark.parametrize("domain", ["WORK_STUDY", "STUDENT_LOAN", "FEE_REDUCTION"])
def test_only_current_receiver_can_advance_and_audit_keeps_numeric_actor(client, db_mode, domain):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, UnifiedTodo, User
    _accounts(db_mode)
    owner = _login(client, "funding_college01", "PC")
    other = _login(client, "funding_school01", "TEACHER_MINI")
    student = _login(client, "fund_student", "PC")
    row, key, path, action, todo_type = _application(client, owner, student, domain)
    record_id = row[key]
    payload = {"action": action, "version": row["version"]}
    denied = client.post(f"{BASE}/mobile/teacher/affairs/{path}/{record_id}/action", headers=other, json=payload)
    assert denied.status_code == 403, denied.text
    with get_sessionmaker()() as db:
        todo = db.scalar(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_biz_type == domain, UnifiedTodo.source_biz_id == int(record_id),
            UnifiedTodo.todo_type == todo_type, UnifiedTodo.status == "PENDING"))
        owner_id, todo_id = todo.assignee_id, todo.id
        assert db.get(User, owner_id).login_name == "funding_college01"
        todo.status = "DONE"
        db.commit()
    missing = client.post(f"{BASE}/student-affairs/{path}/{record_id}/action", headers=owner, json=payload)
    assert missing.status_code in (403, 409), missing.text
    with get_sessionmaker()() as db:
        db.get(UnifiedTodo, todo_id).status = "PENDING"
        db.commit()
    for headers, actionable in ((owner, True), (other, False)):
        listed = _data(client.get(f"{BASE}/student-affairs/{path}", headers=headers, params={"recordId": record_id}))["items"][0]
        assert (action in listed["allowedActions"]) is actionable
        assert listed["version"] == row["version"]
    done = client.post(f"{BASE}/student-affairs/{path}/{record_id}/action", headers=owner, json=payload)
    assert done.status_code == 200, done.text
    with get_sessionmaker()() as db:
        audit = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "FUNDING_EXT", AffairsAuditTrail.biz_id == int(record_id)).order_by(AffairsAuditTrail.id.desc()))
        assert audit.created_by == owner_id


@pytest.mark.parametrize("hours,successes", [("25", 1), ("20", 2)])
def test_same_student_month_is_serialized_across_different_posts(client, db_mode, hours, successes):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import WorkStudyMonthly
    ids = _accounts(db_mode)
    owner = _login(client, "funding_college01", "PC")
    student = _login(client, "fund_student", "PC")
    records = []
    for _ in range(2):
        row, key, path, _, _ = _application(client, owner, student, "WORK_STUDY")
        row = _data(client.post(f"{BASE}/student-affairs/{path}/{row[key]}/action", headers=owner,
            json={"action": "APPROVE", "version": row["version"]}))
        row = _data(client.post(f"{BASE}/student-affairs/{path}/{row[key]}/action", headers=owner,
            json={"action": "ONBOARD", "agreementConfirmed": True, "version": row["version"]}))
        records.append(row[key])
    start, stale_reads = Barrier(2), Barrier(2)

    def hold_old_aggregate(_conn, _cursor, statement, _params, _context, _many):
        # Force the original unlocked aggregates to both finish before either write.
        if "sum(" in statement.lower() and "t_affairs_work_study_monthly" in statement.lower():
            stale_reads.wait(timeout=15)

    def submit(record_id):
        start.wait(timeout=15)
        return client.post(f"{BASE}/student-affairs/work-study/records/{record_id}/monthly", headers=owner,
            json={"monthCode": "2090-05", "workHours": hours, "rating": "PASS", "subsidyAmount": "400.00"})

    engine = get_engine()
    with engine.connect() as connection:
        assert connection.get_isolation_level() == "REPEATABLE READ"
    event.listen(engine, "after_cursor_execute", hold_old_aggregate)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, records))
    finally:
        event.remove(engine, "after_cursor_execute", hold_old_aggregate)
    assert sum(r.status_code == 200 for r in results) == successes, [r.text for r in results]
    assert all(r.status_code in (200, 409) for r in results)
    with get_sessionmaker()() as db:
        rows = db.scalars(select(WorkStudyMonthly).where(WorkStudyMonthly.tenant_id == TID,
            WorkStudyMonthly.student_id == ids["sa"], WorkStudyMonthly.month_code == "2090-05")).all()
        assert sum((row.work_hours for row in rows), Decimal(0)) <= 40


@pytest.mark.parametrize("value,expected", [("db-123", 123), (123, 123), ("123", 123), (None, None), ("unknown", None)])
def test_funding_actor_keeps_real_numeric_identity(value, expected):
    from app.services.affairs_funding_ext_service import _uid
    assert _uid({"userId": value}) == expected


def test_same_receiver_cannot_borrow_funding_authority_from_another_current_role(client, db_mode):
    from affairs_contract_test_support import ensure_role_user
    from app.db.session import get_sessionmaker
    from app.models import Role
    _accounts(db_mode)
    owner = _login(client, "funding_college01", "PC")
    student = _login(client, "fund_student", "PC")
    row, key, path, action, _ = _application(client, owner, student, "STUDENT_LOAN")
    ensure_role_user("SCHOOL_ADMIN", "funding_college01", "资助兼岗验收")
    owner = _login(client, "funding_college01", "PC")
    with get_sessionmaker()() as db:
        roles = {r.role_code: r.id for r in db.scalars(select(Role).where(Role.tenant_id == TID,
            Role.role_code.in_(("SCHOOL_ADMIN", "FUNDING_TEACHER"))))}
    for code, expected in (("SCHOOL_ADMIN", 403), ("FUNDING_TEACHER", 200)):
        switched = client.post(BASE + "/auth/switch-role", headers=owner,
            json={"contextId": f"role:{roles[code]}", "clientType": "PC"})
        assert switched.status_code == 200, switched.text
        owner = {"Authorization": "Bearer " + switched.json()["data"]["accessToken"]}
        result = client.post(f"{BASE}/student-affairs/{path}/{row[key]}/action", headers=owner,
            json={"action": action, "version": row["version"]})
        assert result.status_code == expected, result.text


def test_conflicting_pending_receivers_block_both_the_button_and_the_write(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, User
    _accounts(db_mode)
    owner = _login(client, "funding_college01", "PC")
    student = _login(client, "fund_student", "PC")
    row, key, path, action, todo_type = _application(client, owner, student, "STUDENT_LOAN")
    with get_sessionmaker()() as db:
        other = db.scalar(select(User.id).where(User.tenant_id == TID, User.login_name == "funding_school01"))
        db.add(UnifiedTodo(tenant_id=TID, source_module="student-affairs", source_biz_type="STUDENT_LOAN",
            source_biz_id=int(row[key]), todo_type=todo_type, assignee_id=other, student_id=int(row["studentId"]),
            title="旧错误重复受理待办", status="PENDING"))
        db.commit()
    result = client.post(f"{BASE}/student-affairs/{path}/{row[key]}/action", headers=owner,
        json={"action": action, "version": row["version"]})
    assert result.status_code == 409, result.text
    current = _data(client.get(f"{BASE}/student-affairs/{path}", headers=owner, params={"recordId": row[key]}))["items"][0]
    assert current["allowedActions"] == [] and current["version"] == row["version"]

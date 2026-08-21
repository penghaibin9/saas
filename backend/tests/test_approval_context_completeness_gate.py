"""TP-A07：审批高风险动作（approve/return/reject）前的业务 Context 硬门。

`approval_business_context_service`（TP-A06）已经能把源业务对象解析成 FULL/PARTIAL/
MISSING/UNSUPPORTED/ERROR，但此前只用来"展示"——`approve()`/`reject()` 调用
`get_task()` 只是为了复用 assignee 校验，返回值被直接丢弃；`return_for_revision()`
甚至不读业务 Context。源对象被软删/字段缺失/内容已变，旧的审批任务照样能被通过。

本测试锁死新的硬门：
- 已接入 adapter 的业务类型（LEAVE 等）source 记录不是 FULL 时拦截，返回
  APPROVAL_CONTEXT_INCOMPLETE（409）；
- 传入 expectedSourceVersion 且与当前 sourceVersion 不一致时返回
  APPROVAL_CONTEXT_VERSION_CONFLICT（409）；
- 未接入 adapter 的业务类型（UNSUPPORTED）不受影响，继续沿用 TP-A06 之前的行为，
  不能让"没有 Context"变成"审批全部被拦"。

全部用真实 MySQL 跑（db_mode），不是字符串契约测试。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _hdr(client, login_name="counselor01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_assignee(db, login_name="counselor01"):
    from app.models import User
    user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
    if user is None:
        user = User(tenant_id=TID, login_name=login_name, real_name="审批员",
                   password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
        db.add(user)
        db.flush()
    else:
        user.status = "ACTIVE"
        user.is_deleted = False
    db.flush()
    return user


def _seed_leave_task(db, assignee_id, *, leave_kwargs=None, biz_type="LEAVE"):
    from app.models import CsLeave, WorkflowInstance, WorkflowTask
    leave = CsLeave(tenant_id=TID, leave_type="SICK", reason="生病请假",
                    start_time=datetime(2026, 8, 5), end_time=datetime(2026, 8, 6),
                    days=1, status="PENDING_REVIEW", affairs_status="IN_REVIEW",
                    **(leave_kwargs or {}))
    db.add(leave)
    db.flush()
    inst = WorkflowInstance(tenant_id=TID, workflow_code="LEAVE_WF",
                            source_module="student-affairs", source_biz_type=biz_type,
                            source_biz_id=leave.id, applicant_id=1, status="RUNNING",
                            current_node="NODE_1")
    db.add(inst)
    db.flush()
    task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="NODE_1",
                        assignee_id=assignee_id, status="PENDING")
    db.add(task)
    db.flush()
    return leave, task


def test_approve_blocked_when_source_soft_deleted(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        leave.is_deleted = True
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0}, headers=headers)
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_INCOMPLETE"

    from app.db.session import get_sessionmaker
    verify = get_sessionmaker()()
    from app.models import WorkflowTask
    row = verify.get(WorkflowTask, task_id)
    assert row.status == "PENDING", "拦截后任务状态不得被推进"
    verify.close()


def test_approve_succeeds_when_context_full(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        _, task = _seed_leave_task(db, user.id)
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0


def test_approve_blocked_on_source_version_conflict(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        task_id = task.id
        # 详情页读到的是 version=0；这里模拟提交审批前源记录又被业务动作改了一次
        # （真实场景下 version 前进由具体业务 service 显式做，不是 ORM 自动 onupdate）。
        leave.reason = "补充说明后的事由"
        leave.version = int(leave.version or 0) + 1
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0, "expectedSourceVersion": 0},
                       headers=headers)
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_VERSION_CONFLICT"


def test_approve_succeeds_when_expected_source_version_matches(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        task_id = task.id
        current_version = leave.version
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0, "expectedSourceVersion": current_version},
        headers=headers)
    assert resp.status_code == 200, resp.text


def test_return_for_revision_blocked_when_source_missing(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        leave.is_deleted = True
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/return",
                       json={"reason": "请补充材料", "version": 0}, headers=headers)
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_INCOMPLETE"


def test_unsupported_biz_type_is_not_blocked_by_completeness_gate(client, db_mode):
    """未接入 adapter 的业务类型没有可比对的 Context，硬门必须放行——不能因为
    TP-A06 只接了 4 个类型就把其它所有正常审批全部拦死。"""
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        inst = WorkflowInstance(tenant_id=TID, workflow_code="OTHER_WF",
                                source_module="internship", source_biz_type="COMPANY_CHANGE",
                                source_biz_id=999001, applicant_id=1, status="RUNNING",
                                current_node="NODE_1")
        db.add(inst)
        db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="NODE_1",
                            assignee_id=user.id, status="PENDING")
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text

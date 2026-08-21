"""TP-A07：审批高风险动作（approve/return/reject）前的业务 Context 硬门。

本测试锁死生产合同：
- 已接入 adapter 的业务类型（LEAVE 等）source 记录不是 FULL 时拦截；
- supported Context 必须携带调用方实际读取到的 expectedSourceVersion，缺失也 fail-closed；
- expectedSourceVersion 与当前 sourceVersion 不一致时 409；
- 单条与批量 APPROVE/RETURN/REJECT 使用同一条规则，batch 不得绕过；
- 未接入 adapter 的业务类型（UNSUPPORTED）保持既有审批能力，不因没有 Context 被误拦。

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


def _assert_task_pending(task_id):
    from app.db.session import get_sessionmaker
    from app.models import WorkflowTask

    db = get_sessionmaker()()
    try:
        row = db.get(WorkflowTask, task_id)
        assert row.status == "PENDING", "拦截后任务状态不得被推进"
    finally:
        db.close()


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

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0, "expectedSourceVersion": 0},
        headers=_hdr(client),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_INCOMPLETE"
    _assert_task_pending(task_id)


def test_approve_requires_source_version_when_context_supported(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        _, task = _seed_leave_task(db, user.id)
        task_id = task.id
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0},
        headers=_hdr(client),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_VERSION_REQUIRED"
    _assert_task_pending(task_id)


def test_approve_blocked_on_source_version_conflict(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        task_id = task.id
        # 详情页读到 version=0；提交审批前源业务事实被其它业务动作修改。
        leave.reason = "补充说明后的事由"
        leave.version = int(leave.version or 0) + 1
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0, "expectedSourceVersion": 0},
        headers=_hdr(client),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_VERSION_CONFLICT"
    _assert_task_pending(task_id)


def test_approve_succeeds_when_expected_source_version_matches(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        task_id = task.id
        current_version = int(leave.version or 0)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0, "expectedSourceVersion": current_version},
        headers=_hdr(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0


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

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/return",
        json={"reason": "请补充材料", "version": 0, "expectedSourceVersion": 0},
        headers=_hdr(client),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["bizCode"] == "APPROVAL_CONTEXT_INCOMPLETE"
    _assert_task_pending(task_id)


def test_return_and_reject_require_source_version_when_supported(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        _, return_task = _seed_leave_task(db, user.id)
        _, reject_task = _seed_leave_task(db, user.id)
        return_id = return_task.id
        reject_id = reject_task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client)
    returned = client.post(
        f"/api/v1/approvals/tasks/{return_id}/return",
        json={"reason": "请补充材料", "version": 0}, headers=headers,
    )
    rejected = client.post(
        f"/api/v1/approvals/tasks/{reject_id}/reject",
        json={"reason": "材料事实不符合要求", "version": 0}, headers=headers,
    )
    assert returned.status_code == 409, returned.text
    assert returned.json()["bizCode"] == "APPROVAL_CONTEXT_VERSION_REQUIRED"
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["bizCode"] == "APPROVAL_CONTEXT_VERSION_REQUIRED"
    _assert_task_pending(return_id)
    _assert_task_pending(reject_id)


def test_batch_supported_context_missing_source_version_is_failed_not_approved(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        _, task = _seed_leave_task(db, user.id)
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = {**_hdr(client), "Idempotency-Key": f"ctx-batch-missing-{task_id}"}
    resp = client.post(
        "/api/v1/approvals/batch",
        json={"action": "APPROVE", "items": [{"taskId": str(task_id), "version": 0}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["succeeded"] == 0 and data["failed"] == 1
    assert data["results"][0]["errorCode"] == "APPROVAL_CONTEXT_VERSION_REQUIRED"
    _assert_task_pending(task_id)


def test_batch_supported_context_with_matching_source_version_succeeds(client, db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        user = _seed_assignee(db)
        leave, task = _seed_leave_task(db, user.id)
        task_id = task.id
        source_version = int(leave.version or 0)
        db.commit()
    finally:
        db.close()

    headers = {**_hdr(client), "Idempotency-Key": f"ctx-batch-match-{task_id}"}
    resp = client.post(
        "/api/v1/approvals/batch",
        json={
            "action": "APPROVE",
            "items": [{
                "taskId": str(task_id),
                "version": 0,
                "expectedSourceVersion": source_version,
            }],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["succeeded"] == 1 and data["failed"] == 0
    assert data["results"][0]["result"] == "SUCCESS"


def test_unsupported_biz_type_is_not_blocked_by_context_version_gate(client, db_mode):
    """未接 adapter 的业务类型没有可比对的 sourceVersion，继续沿用既有审批合同。"""
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

    resp = client.post(
        f"/api/v1/approvals/tasks/{task_id}/approve",
        json={"comment": "同意", "version": 0}, headers=_hdr(client),
    )
    assert resp.status_code == 200, resp.text

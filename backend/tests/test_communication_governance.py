"""SYS-15 统一消息、待办与通知治理（真库）。

对应必测 SYS15-T01～T04：
dedupeKey 不重复发消息/建待办 / 渠道失败可重试且不重复业务动作 /
业务完成证据自动关闭待办 / 无责任人进入异常队列。

本卡第一阶段只做注册表 + adapter，不新建统一大表——去重权威仍是
t_message_event_outbox.dedup_key 与 t_unified_todo.uk_todo_dedup 的既有唯一约束，
下面的用例直接打真实服务函数，是回归锁而不是新发明一套去重逻辑。
"""
from datetime import datetime, timedelta

import pytest

from app.core.context import set_tenant

MAIN_TENANT_ID = 1000000000000000002


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant
    from app.services import platform_service as platform

    with _session() as db:
        if db.get(Tenant, MAIN_TENANT_ID) is None:
            db.add(Tenant(id=MAIN_TENANT_ID, tenant_code="demo15",
                          school_name="消息治理测试学校", status="ACTIVE"))
            db.commit()
    platform.put_config_json(MAIN_TENANT_ID, "TENANT_META", "-",
                             {"status": "active", "packageCode": "professional"})
    set_tenant({"tenantId": str(MAIN_TENANT_ID)})
    try:
        yield MAIN_TENANT_ID
    finally:
        set_tenant(None)


def _make_role(role_code: str, tenant_id: int = MAIN_TENANT_ID) -> int:
    from sqlalchemy import select

    from app.models import Role

    with _session() as db:
        row = db.scalars(select(Role).where(
            Role.tenant_id == tenant_id, Role.role_code == role_code)).first()
        if row is None:
            row = Role(tenant_id=tenant_id, role_code=role_code, role_name=role_code,
                      role_type="SYSTEM", status="ACTIVE")
            db.add(row)
            db.commit()
        return int(row.id)


def _make_user(login_name: str, *, password: str = "Init123456", role_code: str | None = None,
              tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.core.security import hash_password
    from app.models import User, UserRole

    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name="消息治理测试账号",
                  password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")
        db.add(row)
        db.flush()
        if role_code:
            role_id = _make_role(role_code, tenant_id)
            db.add(UserRole(tenant_id=tenant_id, user_id=row.id, role_id=role_id, status="ACTIVE"))
        db.commit()
        return int(row.id)


def _login(client, login_name: str, password: str = "Init123456") -> dict:
    result = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo15", "loginName": login_name, "password": password, "clientType": "PC"}).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}


# ── SYS15-T01：dedupeKey 不重复发消息/建待办 ─────────────────────────────────
def test_t01_emit_message_event_same_dedup_key_returns_existing_row(tenant_ctx):
    from app.services.message_event_outbox_service import emit_message_event

    with _session() as db:
        row1 = emit_message_event(
            db, event_code="LEAVE.APPROVED", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=90001,
            recipient_refs=[{"type": "STUDENT", "id": 1}], dedup_key="sys15-t01-dedup")
        db.commit()
        row2 = emit_message_event(
            db, event_code="LEAVE.APPROVED", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=90001,
            recipient_refs=[{"type": "STUDENT", "id": 1}], dedup_key="sys15-t01-dedup")
        db.commit()
        assert row1.id == row2.id

    from sqlalchemy import func, select

    from app.models import MessageEventOutbox
    with _session() as db:
        cnt = db.scalar(select(func.count()).select_from(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == MAIN_TENANT_ID,
            MessageEventOutbox.dedup_key == "sys15-t01-dedup"))
        assert cnt == 1


def test_t01b_create_todo_idempotent_same_key_returns_existing_row(tenant_ctx):
    from app.services import todo_task_service as tts

    assignee_id = _make_user("sys15_t01b_assignee")
    with _session() as db:
        row1 = tts.create_todo_idempotent(
            db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=1,
            todo_type="SYS15_TEST_TODO", assignee_id=assignee_id, title="第一次创建")
        db.commit()
        row2 = tts.create_todo_idempotent(
            db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=1,
            todo_type="SYS15_TEST_TODO", assignee_id=assignee_id, title="第二次创建（应复用）")
        db.commit()
        assert row1.id == row2.id
        assert row2.title == "第一次创建"  # 命中去重时返回既有行，不覆盖标题

    from sqlalchemy import func, select

    from app.models import UnifiedTodo
    with _session() as db:
        cnt = db.scalar(select(func.count()).select_from(UnifiedTodo).where(
            UnifiedTodo.tenant_id == MAIN_TENANT_ID, UnifiedTodo.source_module == "sys15-test",
            UnifiedTodo.source_biz_id == 1, UnifiedTodo.todo_type == "SYS15_TEST_TODO"))
        assert cnt == 1


def test_t01c_create_todo_requires_assignee(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import todo_task_service as tts

    with _session() as db:
        with pytest.raises(AppException):
            tts.create_todo_idempotent(
                db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=2,
                todo_type="SYS15_TEST_TODO", assignee_id=0, title="无责任人")


# ── SYS15-T02：渠道失败可重试且不重复业务动作 ────────────────────────────────
def test_t02_retry_dead_outbox_resets_status_without_duplicating_row(tenant_ctx):
    from app.services.message_event_outbox_service import retry_dead_outbox
    from app.models import MessageEventOutbox

    with _session() as db:
        row = MessageEventOutbox(
            tenant_id=MAIN_TENANT_ID, event_code="LEAVE.APPROVED", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=90002, dedup_key="sys15-t02-dedup",
            status="DEAD", attempt_count=5, last_error_code="PROVIDER_TIMEOUT")
        db.add(row)
        db.commit()
        outbox_id = row.id

    result = retry_dead_outbox(outbox_id)
    assert result["status"] == "PENDING"

    from sqlalchemy import func, select
    with _session() as db:
        cnt = db.scalar(select(func.count()).select_from(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == MAIN_TENANT_ID,
            MessageEventOutbox.dedup_key == "sys15-t02-dedup"))
        assert cnt == 1  # 重试只重置原行状态，不产生第二条业务事件
        refreshed = db.get(MessageEventOutbox, outbox_id)
        assert refreshed.status == "PENDING"
        assert refreshed.attempt_count == 0


def test_t02b_retry_dead_outbox_rejects_non_dead_status(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services.message_event_outbox_service import retry_dead_outbox
    from app.models import MessageEventOutbox

    with _session() as db:
        row = MessageEventOutbox(
            tenant_id=MAIN_TENANT_ID, event_code="LEAVE.APPROVED", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=90003, dedup_key="sys15-t02b-dedup",
            status="PENDING")
        db.add(row)
        db.commit()
        outbox_id = row.id

    with pytest.raises(AppException):
        retry_dead_outbox(outbox_id)


# ── SYS15-T03：业务完成证据关闭待办 ──────────────────────────────────────────
def test_t03_close_todo_requires_evidence_and_writes_audit(tenant_ctx):
    from app.services import audit_log
    from app.services import todo_task_service as tts

    assignee_id = _make_user("sys15_t03_assignee")
    with _session() as db:
        todo = tts.create_todo_idempotent(
            db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=3,
            todo_type="SYS15_TEST_TODO_CLOSE", assignee_id=assignee_id, title="待关闭事项")
        db.commit()
        todo_id = todo.id

        from app.core.exceptions import AppException
        with pytest.raises(AppException):
            tts.close_todo_with_evidence(db, todo_id=todo_id, evidence="")

        row = tts.close_todo_with_evidence(
            db, todo_id=todo_id, evidence="学生已完成材料补交，附件编号SYS15-EVD-01",
            actor={"userId": "db-1"})
        db.commit()
        assert row.status == "DONE"
        assert "SYS15-EVD-01" in row.remark

    assert audit_log._LOGS
    latest = audit_log._LOGS[0]
    assert latest["action"] == "TODO_CLOSED_WITH_EVIDENCE"
    assert latest["detail"]["evidence"].endswith("SYS15-EVD-01")


def test_t03b_close_todo_not_found_raises(tenant_ctx):
    from app.core.exceptions import AppException
    from app.services import todo_task_service as tts

    with _session() as db:
        with pytest.raises(AppException):
            tts.close_todo_with_evidence(db, todo_id=999999999, evidence="不存在的待办")


# ── SYS15-T04：无责任人进入异常队列 ──────────────────────────────────────────
def test_t04_governance_overview_flags_unowned_todo_type_and_duplicate_template(tenant_ctx):
    from app.services import communication_registry as cr
    from app.services import todo_task_service as tts
    from app.models import NotificationTemplate

    assignee_id = _make_user("sys15_t04_assignee")
    with _session() as db:
        tts.create_todo_idempotent(
            db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=4,
            todo_type="SYS15_UNREGISTERED_TODO_TYPE", assignee_id=assignee_id,
            title="未登记类型的待办", due_at=datetime.utcnow() - timedelta(days=1))
        db.commit()

        db.add(NotificationTemplate(
            tenant_id=MAIN_TENANT_ID, template_code="SYS15_DUP_A", channel="SMS",
            content="模板A：{name}", event_code="SYS15_DUP_EVENT"))
        db.add(NotificationTemplate(
            tenant_id=MAIN_TENANT_ID, template_code="SYS15_DUP_B", channel="SMS",
            content="模板B：{name}", event_code="SYS15_DUP_EVENT"))
        db.commit()

        overview = cr.governance_overview(db)

    assert "SYS15_UNREGISTERED_TODO_TYPE" in overview["exceptionQueue"]["unownedTodoTypes"]
    assert overview["todoOverdue"] >= 1
    dup_codes = {(d["eventCode"], d["channel"]) for d in overview["duplicateTemplates"]}
    assert ("SYS15_DUP_EVENT", "SMS") in dup_codes


def test_t04b_validate_registry_reports_gap_between_yaml_and_code(tenant_ctx):
    from app.services import communication_registry as cr
    from app.services.message_event_outbox_service import _EVENT_TEMPLATES

    result = cr.validate_registry()
    reg_codes = cr.registered_event_codes()
    assert not (reg_codes - set(_EVENT_TEMPLATES.keys()))  # 注册表登记的事件码必须真实存在于代码
    assert "registryVersion" in result


# ── HTTP 端点冒烟（真实鉴权路径）──────────────────────────────────────────────
def test_http_endpoints(client, tenant_ctx):
    admin_id = _make_user("sys15_http_admin", role_code="SYS_ADMIN")
    headers = _login(client, "sys15_http_admin")

    r = client.get("/api/v1/system/communication-governance/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/communication-governance/registry", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/communication-governance/todo-backlog", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/communication-governance/dead-outbox", headers=headers)
    assert r.json()["code"] == 0, r.json()

    with _session() as db:
        from app.services import todo_task_service as tts
        todo = tts.create_todo_idempotent(
            db, source_module="sys15-test", source_biz_type="TEST", source_biz_id=5,
            todo_type="SYS15_HTTP_TODO", assignee_id=admin_id, title="HTTP关闭测试")
        db.commit()
        todo_id = todo.id

    r = client.post(f"/api/v1/system/communication-governance/todos/{todo_id}/close",
                    headers=headers, json={"evidence": "HTTP 路径关闭验证"})
    assert r.json()["code"] == 0, r.json()

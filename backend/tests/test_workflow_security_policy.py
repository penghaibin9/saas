"""SYS-14 流程定义、流程安全与运行异常（真库）。

对应必测 SYS14-T01～T04：
有页面权限但无节点动作权限时拒绝 / 导师不能最终评阅自己学生 /
在途实例按选定策略处理版本变化 / 人工推进有理由和审计。
"""
from datetime import datetime, timedelta

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.services import workflow_security_policy_service as wsp

MAIN_TENANT_ID = 1000000000000000001
ADMIN = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant
    from app.services import platform_service as platform

    with _session() as db:
        if db.get(Tenant, MAIN_TENANT_ID) is None:
            db.add(Tenant(id=MAIN_TENANT_ID, tenant_code="demo",
                          school_name="流程安全测试学校", status="ACTIVE"))
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


def _make_user(login_name: str, *, password: str = "Init123456", user_type: str = "TEACHER",
              role_code: str | None = None, tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.core.security import hash_password
    from app.models import Role, User, UserRole

    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name="流程测试账号",
                  password_hash=hash_password(password), user_type=user_type, status="ACTIVE")
        db.add(row)
        db.flush()
        if role_code:
            role_id = _make_role(role_code, tenant_id)
            db.add(UserRole(tenant_id=tenant_id, user_id=row.id, role_id=role_id, status="ACTIVE"))
        db.commit()
        return int(row.id)


def _login(client, login_name: str, password: str = "Init123456") -> dict:
    result = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": login_name, "password": password, "clientType": "PC"}).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}


def _make_workflow(workflow_code: str, node_code: str = "COUNSELOR_REVIEW",
                   approver_role_code: str = "COUNSELOR") -> int:
    from app.models import WorkflowDefinition, WorkflowNodeDefinition

    with _session() as db:
        wf = WorkflowDefinition(
            tenant_id=MAIN_TENANT_ID, workflow_code=workflow_code, workflow_name=workflow_code,
            source_module="student", source_biz_type="TEST", status="ENABLED",
            policy_confirmed=True, source_profile="TEST", installed_project_id=0)
        db.add(wf)
        db.flush()
        db.add(WorkflowNodeDefinition(
            tenant_id=MAIN_TENANT_ID, workflow_definition_id=wf.id, node_code=node_code,
            node_name=node_code, sequence_no=1, approver_role_code=approver_role_code))
        db.commit()
        return int(wf.id)


def _make_task(workflow_code: str, assignee_id: int, *, node_code: str = "COUNSELOR_REVIEW") -> int:
    from app.models import WorkflowInstance, WorkflowTask

    with _session() as db:
        inst = WorkflowInstance(
            tenant_id=MAIN_TENANT_ID, workflow_code=workflow_code, source_module="student",
            source_biz_type="TEST", source_biz_id=1, applicant_id=1, status="RUNNING")
        db.add(inst)
        db.flush()
        task = WorkflowTask(tenant_id=MAIN_TENANT_ID, instance_id=inst.id, node_code=node_code,
                            assignee_id=assignee_id, status="PENDING")
        db.add(task)
        db.commit()
        return int(task.id)


def _activate_node_policy(workflow_code: str, node_code: str, action_permission_code: str) -> None:
    """草稿 -> 提交 -> 用不同的复核人激活，走真实两人复核流程。"""
    reviewer = {"userId": "db-999999", "currentRoleCode": "SCHOOL_ADMIN"}
    saved = wsp.save_draft(workflow_code, node_code=node_code, policy_type="NODE_ACTION",
                           action_permission_code=action_permission_code,
                           reason="限制该节点的通配旁路", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    submitted = wsp.submit_for_review(int(saved["policyId"]), tenant_id=MAIN_TENANT_ID, user=ADMIN)
    wsp.activate(int(submitted["policyId"]), reason="复核通过，正式启用节点动作策略",
                tenant_id=MAIN_TENANT_ID, user=reviewer)


# ── SYS14-T01：有页面权限但无节点动作权限时拒绝（真实 HTTP 执行路径）──────────
def test_t01_page_permission_without_node_action_permission_is_denied(client, tenant_ctx):
    workflow_code = "SYS14_T01_WF"
    _make_workflow(workflow_code)
    assignee_id = _make_user("sys14_assignee", role_code="COUNSELOR")
    bypass_id = _make_user("sys14_bypasser", role_code="STUDENT_AFFAIRS_ADMIN")  # 持有 approval.manage，非 assignee
    bypass_headers = _login(client, "sys14_bypasser")

    # 激活前：approval.manage 的通配旁路按旧行为放行（向后兼容）
    baseline_task = _make_task(workflow_code, assignee_id)
    control = client.post(f"/api/v1/approvals/tasks/{baseline_task}/approve", headers=bypass_headers,
                          json={"version": 0})
    assert control.status_code == 200 and control.json()["code"] == 0, control.text

    # 激活节点动作策略：约定权限码 bypasser 并不持有
    _activate_node_policy(workflow_code, "COUNSELOR_REVIEW", "systemAdmin.workflow.override")

    # 激活后：同一个 approval.manage 账号面对新任务被拒绝，不是 assignee 也没有该动作权限
    protected_task = _make_task(workflow_code, assignee_id)
    denied = client.post(f"/api/v1/approvals/tasks/{protected_task}/approve", headers=bypass_headers,
                         json={"version": 0})
    assert denied.status_code == 404, denied.text  # not_found 语义：越权时不暴露资源存在

    # 真正的 assignee 不受影响，策略激活后依然能处理自己的任务
    assignee_headers = _login(client, "sys14_assignee")
    ok = client.post(f"/api/v1/approvals/tasks/{protected_task}/approve", headers=assignee_headers,
                     json={"version": 0})
    assert ok.status_code == 200 and ok.json()["code"] == 0, ok.text


def test_t01b_simulate_matches_real_decision(tenant_ctx):
    workflow_code = "SYS14_T01B_WF"
    _make_workflow(workflow_code)
    assignee_id = _make_user("sys14b_assignee", role_code="COUNSELOR")
    _activate_node_policy(workflow_code, "COUNSELOR_REVIEW", "systemAdmin.workflow.override")

    as_assignee = wsp.simulate(workflow_code, "COUNSELOR_REVIEW", actor_user_id=str(assignee_id),
                               actor_permissions=[], task_assignee_id=str(assignee_id))
    assert as_assignee["allowed"] is True

    as_bypasser = wsp.simulate(workflow_code, "COUNSELOR_REVIEW", actor_user_id="777",
                               actor_permissions=["approval.manage"], task_assignee_id=str(assignee_id))
    assert as_bypasser["allowed"] is False
    assert as_bypasser["policyActive"] is True

    as_permitted = wsp.simulate(workflow_code, "COUNSELOR_REVIEW", actor_user_id="778",
                                actor_permissions=["systemAdmin.workflow.override"],
                                task_assignee_id=str(assignee_id))
    assert as_permitted["allowed"] is True


def test_t01c_super_wildcard_still_bypasses(tenant_ctx):
    """`*` 是真超管通配，不受 SYS-14 节点策略约束——只收紧 approval.manage 这一层。"""
    workflow_code = "SYS14_T01C_WF"
    _make_workflow(workflow_code)
    assignee_id = _make_user("sys14c_assignee", role_code="COUNSELOR")
    _activate_node_policy(workflow_code, "COUNSELOR_REVIEW", "systemAdmin.workflow.override")

    as_super = wsp.simulate(workflow_code, "COUNSELOR_REVIEW", actor_user_id="999",
                            actor_permissions=["*"], task_assignee_id=str(assignee_id))
    assert as_super["allowed"] is True


def test_t01d_draft_lifecycle_requires_different_reviewer(tenant_ctx):
    workflow_code = "SYS14_T01D_WF"
    _make_workflow(workflow_code)
    saved = wsp.save_draft(workflow_code, node_code="COUNSELOR_REVIEW", policy_type="NODE_ACTION",
                           action_permission_code="systemAdmin.workflow.override",
                           reason="草稿生命周期验证", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert saved["status"] == "DRAFT"
    submitted = wsp.submit_for_review(int(saved["policyId"]), tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert submitted["status"] == "PENDING_REVIEW"

    with pytest.raises(AppException) as same_reviewer:
        wsp.activate(int(submitted["policyId"]), reason="提交人自己激活",
                    tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert "selfReviewAck" in same_reviewer.value.message

    activated = wsp.activate(int(submitted["policyId"]), reason="换人复核后激活",
                             self_review_ack=wsp.SELF_REVIEW_TEXT,
                             tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert activated["status"] == "ACTIVE"


def test_t01e_active_policy_cannot_be_edited_in_place(tenant_ctx):
    workflow_code = "SYS14_T01E_WF"
    _make_workflow(workflow_code)
    _activate_node_policy(workflow_code, "COUNSELOR_REVIEW", "systemAdmin.workflow.override")
    with pytest.raises(AppException) as caught:
        wsp.save_draft(workflow_code, node_code="COUNSELOR_REVIEW", policy_type="NODE_ACTION",
                       action_permission_code="systemAdmin.workflow.override.v2",
                       reason="想直接改生效中的策略", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert caught.value.code == "DATA_CONFLICT"


# ── SYS14-T02：导师不能最终评阅自己学生（回归锁：真实业务 SoD 已在毕设域生效）──
def test_t02_mentor_cannot_review_own_advisee(tenant_ctx):
    from app.core.context import set_current_user
    from app.models import GraduationBatch, GraduationMentor, GraduationStudent
    from app.modules.graduation.services import graduation_review_service as review_svc

    with _session() as db:
        batch = GraduationBatch(tenant_id=MAIN_TENANT_ID, batch_name="SYS14 测试批次",
                                batch_no="SYS14-BATCH-01", planned_count=1, status="RUNNING")
        db.add(batch)
        db.flush()
        mentor = GraduationMentor(tenant_id=MAIN_TENANT_ID, teacher_no="sys14_mentor_01",
                                  teacher_name="毕设导师", qualification_status="QUALIFIED")
        db.add(mentor)
        db.flush()
        stu = GraduationStudent(tenant_id=MAIN_TENANT_ID, name="导师自己的学生", batch_id=batch.id,
                                mentor_id=mentor.id, stage="MIDTERM", record_status="ACTIVE")
        db.add(stu)
        db.commit()
        mentor_id, student_id = int(mentor.id), int(stu.id)

    set_current_user({"tenantId": str(MAIN_TENANT_ID), "userId": "db-1",
                          "currentRoleCode": "SCHOOL_ADMIN"})
    try:
        with pytest.raises(AppException) as caught:
            review_svc.assign_review(student_id, reviewer_mentor_id=mentor_id)
        assert "SoD" in caught.value.message or "指导教师" in caught.value.message
    finally:
        set_current_user(None)


# ── SYS14-T03：在途实例按选定策略处理版本变化 ───────────────────────────────
def _project_with_workflow(workflow_code: str = "AFFAIRS_LEAVE") -> int:
    """借用实施安装真实链路装一条预置流程，拿到货真价实的 installed_project_id。"""
    from app.services import system_implementation_service as impl

    impl.create_project(ADMIN, {"projectName": "SYS14 版本策略测试项目", "profileCode": "PILOT_FAST"})
    project = impl.current_project()
    impl.preview_project(ADMIN, int(project["id"]))
    impl.apply_snapshot(ADMIN, int(project["id"]), {"confirmText": "确认应用", "reason": "装流程定义"})
    return int(project["id"])


def _running_instance_for(workflow_code: str) -> int:
    from app.models import WorkflowInstance

    with _session() as db:
        inst = WorkflowInstance(tenant_id=MAIN_TENANT_ID, workflow_code=workflow_code,
                                source_module="student", source_biz_type="TEST",
                                source_biz_id=1, applicant_id=1, status="RUNNING")
        db.add(inst)
        db.commit()
        return int(inst.id)


def test_t03_snapshot_strategy_blocks_definition_change(tenant_ctx):
    from app.services import runtime_preset_install_service as runtime

    project_id = _project_with_workflow()
    workflow_code = "AFFAIRS_LEAVE"
    saved = wsp.save_draft(workflow_code, node_code=wsp.WORKFLOW_LEVEL_NODE,
                           policy_type="VERSION_STRATEGY", version_strategy="SNAPSHOT",
                           reason="在途实例期间冻结流程定义", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    submitted = wsp.submit_for_review(int(saved["policyId"]), tenant_id=MAIN_TENANT_ID, user=ADMIN)
    wsp.activate(int(submitted["policyId"]), reason="启用 SNAPSHOT 策略",
                self_review_ack=wsp.SELF_REVIEW_TEXT, tenant_id=MAIN_TENANT_ID, user=ADMIN)

    _running_instance_for(workflow_code)
    with pytest.raises(AppException) as caught:
        runtime.update_workflow(ADMIN, project_id, workflow_code, {"timeoutHours": 72})
    assert caught.value.code == "DATA_CONFLICT"
    assert "SNAPSHOT" in caught.value.message


def test_t03b_migrate_strategy_allows_and_logs(tenant_ctx):
    from sqlalchemy import select

    from app.models.workflow_security_policy import WorkflowVersionMigrationEvent
    from app.services import runtime_preset_install_service as runtime

    project_id = _project_with_workflow()
    workflow_code = "AFFAIRS_LEAVE"
    saved = wsp.save_draft(workflow_code, node_code=wsp.WORKFLOW_LEVEL_NODE,
                           policy_type="VERSION_STRATEGY", version_strategy="MIGRATE",
                           reason="允许改动但需要留痕", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    submitted = wsp.submit_for_review(int(saved["policyId"]), tenant_id=MAIN_TENANT_ID, user=ADMIN)
    wsp.activate(int(submitted["policyId"]), reason="启用 MIGRATE 策略",
                self_review_ack=wsp.SELF_REVIEW_TEXT, tenant_id=MAIN_TENANT_ID, user=ADMIN)

    inst_id = _running_instance_for(workflow_code)
    result = runtime.update_workflow(ADMIN, project_id, workflow_code, {"timeoutHours": 96})
    assert result["code"] == workflow_code

    with _session() as db:
        events = db.scalars(select(WorkflowVersionMigrationEvent).where(
            WorkflowVersionMigrationEvent.tenant_id == MAIN_TENANT_ID,
            WorkflowVersionMigrationEvent.workflow_code == workflow_code)).all()
    assert len(events) == 1
    assert events[0].affected_instance_count == 1
    assert inst_id in (events[0].affected_instance_ids_json or [])


def test_t03c_dynamic_default_is_unaffected(tenant_ctx):
    """不设策略＝默认 DYNAMIC：有在途实例也照样能改，行为跟改造前一致。"""
    from app.services import runtime_preset_install_service as runtime

    project_id = _project_with_workflow()
    workflow_code = "AFFAIRS_LEAVE"
    _running_instance_for(workflow_code)
    result = runtime.update_workflow(ADMIN, project_id, workflow_code, {"timeoutHours": 60})
    assert result["code"] == workflow_code


# ── SYS14-T04：人工推进有理由和审计 ─────────────────────────────────────────
def test_t04_force_advance_requires_reason_and_leaves_audit(tenant_ctx):
    workflow_code = "SYS14_T04_WF"
    _make_workflow(workflow_code)
    assignee_id = _make_user("sys14_t04_assignee", role_code="COUNSELOR")
    task_id = _make_task(workflow_code, assignee_id)

    with pytest.raises(AppException):
        wsp.force_advance_task(task_id, action="APPROVED", reason="短",
                               tenant_id=MAIN_TENANT_ID, user=ADMIN)

    result = wsp.force_advance_task(task_id, action="APPROVED",
                                    reason="assignee 长期请假，管理员人工推进解卡",
                                    tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert result["afterStatus"] == "APPROVED"

    from app.models import WorkflowTask

    with _session() as db:
        task = db.get(WorkflowTask, task_id)
        assert task.status == "APPROVED"
        assert "人工推进" in (task.action_reason or "")

    # 已处理的任务不能再被强推
    with pytest.raises(AppException) as caught:
        wsp.force_advance_task(task_id, action="REJECTED", reason="重复人工推进",
                               tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert caught.value.code == "DATA_CONFLICT"


def test_t04b_force_advance_rejects_unknown_action(tenant_ctx):
    workflow_code = "SYS14_T04B_WF"
    _make_workflow(workflow_code)
    assignee_id = _make_user("sys14_t04b_assignee", role_code="COUNSELOR")
    task_id = _make_task(workflow_code, assignee_id)
    with pytest.raises(AppException):
        wsp.force_advance_task(task_id, action="MAGIC", reason="非法动作测试合法性校验",
                               tenant_id=MAIN_TENANT_ID, user=ADMIN)


# ── 首屏结论与列表 ───────────────────────────────────────────────────────────
def test_governance_overview_reports_no_approver_nodes(tenant_ctx):
    workflow_code = "SYS14_OVERVIEW_WF"
    _make_workflow(workflow_code, approver_role_code="ROLE_WITHOUT_MEMBERS")
    overview = wsp.governance_overview(tenant_id=MAIN_TENANT_ID)
    assert any(n["workflowCode"] == workflow_code for n in overview["noApproverNodes"])
    assert overview["totalWorkflows"] >= 1


def test_list_policies_filters_by_workflow(tenant_ctx):
    workflow_code = "SYS14_LIST_WF"
    _make_workflow(workflow_code)
    wsp.save_draft(workflow_code, node_code="COUNSELOR_REVIEW", policy_type="NODE_ACTION",
                   action_permission_code="systemAdmin.workflow.override",
                   reason="列表过滤验证", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    listed = wsp.list_policies(workflow_code=workflow_code, tenant_id=MAIN_TENANT_ID)
    assert listed["total"] == 1
    assert listed["list"][0]["workflowCode"] == workflow_code


# ── 接口层 ───────────────────────────────────────────────────────────────────
def test_http_endpoints(client, auth_headers, tenant_ctx):
    workflow_code = "SYS14_HTTP_WF"
    _make_workflow(workflow_code)

    draft = client.put(f"/api/v1/system/workflow-security-policies/{workflow_code}/draft",
                       headers=auth_headers,
                       json={"nodeCode": "COUNSELOR_REVIEW", "policyType": "NODE_ACTION",
                             "actionPermissionCode": "systemAdmin.workflow.override",
                             "reason": "接口层保存草稿"}).json()
    assert draft["code"] == 0
    policy_id = draft["data"]["policyId"]

    submitted = client.post(f"/api/v1/system/workflow-security-policies/{policy_id}/submit",
                            headers=auth_headers).json()
    assert submitted["code"] == 0

    overview = client.get("/api/v1/system/workflow-governance/overview", headers=auth_headers).json()
    assert overview["code"] == 0
    assert "runningInstances" in overview["data"]

    listed = client.get("/api/v1/system/workflow-security-policies", headers=auth_headers,
                        params={"workflow_code": workflow_code}).json()
    assert listed["code"] == 0 and listed["data"]["total"] == 1

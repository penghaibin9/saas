from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("domain", ["DISCIPLINE", "DISCIPLINE_REMOVE"])
def test_generic_approval_cannot_bypass_discipline(domain):
    from app.core.exceptions import AppException
    from app.services.approval_business_context_service import assert_domain_action_entry
    with pytest.raises(AppException) as caught:
        assert_domain_action_entry(SimpleNamespace(source_module="student-affairs", source_biz_type=domain))
    assert caught.value.code == "DOMAIN_WORKSPACE_REQUIRED"


def test_discipline_registrar_and_original_reviewers_must_recuse(client, db_mode):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user, post_versioned, role_headers
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase, Role, RoleAssignmentScope, StudentAccountLink, UnifiedTodo, User, UserRole, WorkflowTask
    from app.core.security import hash_password
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_discipline import BASE, TID, _hdr, _register, _seed
    ids = _seed(db_mode)
    other_id = ensure_role_user("STUDENT_AFFAIRS_ADMIN", login_name="disc_independent", real_name="独立处分审核人")
    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "STUDENT_AFFAIRS_ADMIN"))
        member = db.scalar(select(UserRole).where(UserRole.tenant_id == TID, UserRole.user_id == other_id, UserRole.role_id == role.id))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=other_id, user_role_id=member.id,
            role_code="STUDENT_AFFAIRS_ADMIN", scope_type="SCHOOL", scope_id=0, status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        registrar = db.scalar(select(User).where(User.tenant_id == TID, User.login_name == "sa_admin01"))
        registrar_id = registrar.id
        from app.services.saas_role_service import ensure_builtin_roles
        ensure_builtin_roles(db, TID)
        student_role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "STUDENT"))
        student_user = User(tenant_id=TID, login_name="disc_self_student", real_name="处分学生本人",
            user_type="STUDENT", status="ACTIVE", must_change_password=False, password_hash=hash_password(TEST_LOGIN_PASSWORD))
        db.add(student_user); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student_user.id, role_id=student_role.id, status="ACTIVE"))
        db.add(StudentAccountLink(tenant_id=TID, user_id=student_user.id, student_id=ids["sa"], link_status="ACTIVE", source="MANUAL"))
        db.commit()
    register_header = _hdr(client, "sa_admin01")
    other_header = role_headers("STUDENT_AFFAIRS_ADMIN", "disc_independent", "独立处分审核人")
    case = _register(client, register_header, ids["sa"]).json()["data"]
    cid = case["caseId"]
    submitted = post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=register_header)
    assert submitted.status_code == 200, submitted.text
    first = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "college_admin01"), json={"action": "APPROVE"})
    assert first.status_code == 200, first.text
    ensure_role_user("SCHOOL_ADMIN", "disc_independent", "独立处分审核人")
    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "SCHOOL_ADMIN"))
        member = db.scalar(select(UserRole).where(UserRole.user_id == other_id, UserRole.role_id == role.id))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=other_id, user_role_id=member.id,
            role_code="SCHOOL_ADMIN", scope_type="SCHOOL", scope_id=0, status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        db.commit()
    wrong_duty = role_headers("SCHOOL_ADMIN", "disc_independent", "独立处分审核人")
    queue_url = "/api/v1/mobile/teacher/affairs/discipline/pending"
    wrong_queue = client.get(queue_url, headers=wrong_duty, params={"kind": "DISCIPLINE_APPROVAL"})
    assert wrong_queue.status_code == 200 and wrong_queue.json()["data"]["total"] == 0, wrong_queue.text
    own_queue = client.get(queue_url, headers=other_header, params={"kind": "DISCIPLINE_APPROVAL"})
    assert own_queue.status_code == 200 and [row["caseId"] for row in own_queue.json()["data"]["list"]] == [cid], own_queue.text
    detail = client.get(f"{BASE}/discipline/cases/{cid}", headers=wrong_duty)
    assert detail.status_code == 200 and detail.json()["data"]["allowedActions"] == [], detail.text
    with get_sessionmaker()() as db:
        source = db.get(DisciplineCase, int(cid))
        task = db.scalar(select(WorkflowTask).where(WorkflowTask.instance_id == source.workflow_instance_id,
            WorkflowTask.node_code == "STUDENT_AFFAIRS_REVIEW", WorkflowTask.status == "PENDING").order_by(WorkflowTask.id.desc()))
        assert task.assignee_id == other_id
        # 错误旧交接即便把受理人重新指向登记人，也不能绕过领域回避。
        task.assignee_id = registrar_id; task_id = task.id; db.commit()
    denied = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=register_header, json={"action": "APPROVE"})
    assert denied.status_code == 403, denied.text
    with get_sessionmaker()() as db:
        db.get(WorkflowTask, task_id).assignee_id = other_id; db.commit()
    effective = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=other_header, json={"action": "APPROVE"})
    assert effective.status_code == 200 and effective.json()["data"]["status"] == "EFFECTIVE", effective.text
    appeal = client.post("/api/v1/mobile/affairs/discipline/appeal", headers=_real_hdr(client, "disc_self_student", client_type="STUDENT_MINI"),
        json={"caseId": cid, "reason": "对处分事实提出正式申诉，请由独立人员复核"})
    assert appeal.status_code == 200, appeal.text
    aid = appeal.json()["data"]["appealId"]
    with get_sessionmaker()() as db:
        todo = db.scalar(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_biz_id == int(aid), UnifiedTodo.todo_type == "DISCIPLINE_APPEAL_REVIEW", UnifiedTodo.status == "PENDING"))
        assert todo.assignee_id == registrar_id
        todo.assignee_id = other_id; todo_id = todo.id; db.commit()
    queue = client.get("/api/v1/mobile/teacher/affairs/appeals/DISCIPLINE_APPEAL", headers=other_header)
    assert queue.status_code == 200 and queue.json()["data"]["total"] == 0, queue.text
    route = f"{BASE}/discipline/appeals/{aid}/review"
    denied = post_versioned(client, route, headers=other_header, json={"result": "UPHELD", "opinion": "原决定审核人不能再自行维持"})
    assert denied.status_code == 403, denied.text
    with get_sessionmaker()() as db:
        db.get(UnifiedTodo, todo_id).assignee_id = registrar_id; db.commit()
    queue = client.get("/api/v1/mobile/teacher/affairs/appeals/DISCIPLINE_APPEAL", headers=register_header)
    assert queue.status_code == 200 and [item["appealId"] for item in queue.json()["data"]["items"]] == [aid], queue.text
    result = post_versioned(client, route, headers=register_header, json={"result": "UPHELD", "opinion": "未参与原决定审核的独立复核意见"})
    assert result.status_code == 200 and result.json()["data"]["status"] == "UPHELD", result.text


def test_removal_workspace_targets_original_case_not_removal_id(db_mode):
    from sqlalchemy import select
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase, DisciplineRemoveApply, WorkflowInstance
    from app.services.approval_business_context_service import resolve_context
    previous = get_tenant(); set_tenant(1000000000000000001)
    try:
        with get_sessionmaker()() as db:
            case = DisciplineCase(id=8201, tenant_id=1000000000000000001, student_id=db_mode["student"],
                disc_type="WARNING", reason="解除历史原案对照", status="REMOVE_REVIEW")
            db.add(case); db.flush()
            removal = DisciplineRemoveApply(id=8301, tenant_id=1000000000000000001, case_id=case.id,
                student_id=case.student_id, apply_reason="解除申请回原案核验", status="COUNSELOR_REVIEW", current_node="COUNSELOR_REVIEW")
            db.add(removal); db.flush()
            flow = WorkflowInstance(tenant_id=1000000000000000001, workflow_code="AFFAIRS_DISCIPLINE_REMOVE",
                source_module="student-affairs", source_biz_type="DISCIPLINE_REMOVE", source_biz_id=removal.id,
                applicant_id=1, title="解除原案定位", status="RUNNING", current_node="COUNSELOR_REVIEW")
            db.add(flow); db.flush()
            context = resolve_context(db, flow)
            assert context["domainWorkspace"] == {"path": "/admin/student-affairs/discipline", "query": {"recordId": "8201"}}
    finally:
        set_tenant(previous)


@pytest.mark.parametrize("return_at", ["COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW"])
def test_returned_discipline_resubmits_same_flow_with_new_pending_task(client, db_mode, return_at):
    from sqlalchemy import select
    from affairs_contract_test_support import post_versioned
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase, WorkflowTask
    from test_affairs_discipline import BASE, _hdr, _register, _seed
    ids = _seed(db_mode)
    registrar = _hdr(client, "school_admin01"); college = _hdr(client, "college_admin01"); school = _hdr(client, "sa_admin01")
    response = _register(client, registrar, ids["sa"])
    cid = response.json()["data"]["caseId"]
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=registrar).status_code == 200
    with get_sessionmaker()() as db:
        flow_id = db.get(DisciplineCase, int(cid)).workflow_instance_id
    if return_at == "STUDENT_AFFAIRS_REVIEW":
        assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=college, json={"action": "APPROVE"}).status_code == 200
    returned = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=college if return_at == "COLLEGE_REVIEW" else school,
        json={"action": "RETURN", "reason": "请补充核实原始事实依据后重新提交"})
    assert returned.status_code == 200, returned.text
    resubmitted = post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=registrar)
    assert resubmitted.status_code == 200, resubmitted.text
    with get_sessionmaker()() as db:
        assert db.get(DisciplineCase, int(cid)).workflow_instance_id == flow_id
        tasks = db.scalars(select(WorkflowTask).where(WorkflowTask.instance_id == flow_id)).all()
        assert len([task for task in tasks if task.status == "PENDING" and task.node_code == "COLLEGE_REVIEW"]) == 1
        assert any(task.status == "TRANSFERRED" and task.node_code == return_at and task.updated_by for task in tasks)
    approved = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=college, json={"action": "APPROVE"})
    assert approved.status_code == 200, approved.text

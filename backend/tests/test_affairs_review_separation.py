from datetime import datetime
from types import SimpleNamespace

import pytest

TID = 1000000000000000001


@pytest.mark.parametrize("domain", ["aid", "funding"])
@pytest.mark.parametrize("history", ["same_actor", "different_actor", "missing_actor", "valid_transfer", "prior_return"])
def test_school_review_uses_actual_actor_not_assigned_user(db_mode, domain, history):
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import affairs_aid_service as aid, affairs_funding_service as funding
    from app.services.affairs_assignee_service import completed_review_actor_ids

    previous = get_tenant(); set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            flow = WorkflowInstance(tenant_id=TID, workflow_code="TEST_SEPARATION",
                source_module="student-affairs", source_biz_type=domain.upper(), source_biz_id=1,
                applicant_id=20, title="真实办理人回避", status="RUNNING", current_node="SCHOOL_REVIEW")
            db.add(flow); db.flush()
            nodes = aid.AID_NODES[:-1] if domain == "aid" else funding.FUND_NODES[:-1]
            actor = None if history == "missing_actor" else 44 if history == "same_actor" else 55
            for node in nodes:
                db.add(WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code=node,
                    assignee_id=99, updated_by=actor, acted_at=datetime.utcnow(), status="APPROVED"))
            if history in {"valid_transfer", "prior_return"}:
                db.add(WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code=nodes[0],
                    assignee_id=44, updated_by=44 if history == "prior_return" else None,
                    acted_at=datetime.utcnow(), status="TRANSFERRED",
                    remark="TRANSFER_TO:55" if history == "valid_transfer" else None))
            db.add(WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code="SCHOOL_REVIEW",
                                assignee_id=44, status="PENDING"))
            db.flush()
            record = SimpleNamespace(id=1, status="SCHOOL_REVIEW", workflow_instance_id=flow.id)
            user = {"userId": "db-44", "currentRoleCode": "STUDENT_AFFAIRS_ADMIN"}
            check = aid._check_aid_assignee if domain == "aid" else funding._check_fund_review_node
            if history in {"different_actor", "valid_transfer"}:
                assert completed_review_actor_ids(db, flow.id, nodes) == {55}
                check(db, record, user)
            else:
                with pytest.raises(AppException):
                    check(db, record, user)
    finally:
        set_tenant(previous)


def test_assignee_exclusion_does_not_change_default_selection(db_mode, monkeypatch):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.core.exceptions import AppException
    from app.services import affairs_assignee_service as service
    monkeypatch.setattr(service, "resolve_assignee_ids", lambda *a, **k: [44, 55])
    previous = get_tenant(); set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            assert service.require_assignee_id(db, "SCHOOL_REVIEW") == 44
            assert service.require_assignee_id(db, "SCHOOL_REVIEW", exclude_user_ids={44}) == 55
            with pytest.raises(AppException):
                service.require_assignee_id(db, "SCHOOL_REVIEW", exclude_user_ids={44, 55})
    finally:
        set_tenant(previous)


@pytest.mark.parametrize("domain", ["LEAVE", "AID", "FUNDING", "DORM_TRANSFER"])
@pytest.mark.parametrize("action", ["APPROVED", "REJECTED", "TRANSFERRED"])
def test_generic_task_action_cannot_bypass_affairs_domain(db_mode, domain, action):
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service
    from app.services.approval_business_context_service import resolve_context
    previous = get_tenant(); set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            flow = WorkflowInstance(tenant_id=TID, workflow_code="TEST_DOMAIN_GUARD",
                source_module="student-affairs", source_biz_type=domain, source_biz_id=1,
                applicant_id=20, title="通用审批禁止绕行", status="RUNNING", current_node="SCHOOL_REVIEW")
            db.add(flow); db.flush()
            task = WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code="SCHOOL_REVIEW",
                                assignee_id=44, status="PENDING", version=1)
            db.add(task); db.commit()
            assert resolve_context(db, flow)["domainWorkspace"]["query"] == {"recordId": "1"}
            with pytest.raises(AppException) as caught:
                db_service.act_task(task.id, action, "核验同人回避的直接入口",
                    user={"userId": "db-44", "currentRoleCode": "STUDENT_AFFAIRS_ADMIN"}, version=1)
            assert caught.value.code == "DOMAIN_WORKSPACE_REQUIRED"
            db.refresh(task); db.refresh(flow)
            assert task.status == "PENDING" and task.version == 1 and flow.status == "RUNNING"
    finally:
        set_tenant(previous)

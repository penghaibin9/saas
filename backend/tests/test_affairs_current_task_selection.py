"""Authorization and completion must select the same current task after a handoff."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("domain", ["leave", "aid", "discipline", "funding"])
def test_completion_uses_latest_pending_task(db_mode, domain):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import affairs_leave_service, affairs_aid_service, affairs_discipline_service, affairs_funding_service

    tenant = 1000000000000000001
    previous = get_tenant()
    set_tenant(tenant)
    try:
        with get_sessionmaker()() as db:
            flow = WorkflowInstance(tenant_id=tenant, workflow_code="AFFAIRS_LEAVE",
                source_module="student-affairs", source_biz_type=domain.upper(), source_biz_id=1,
                applicant_id=1, title="交接任务测试", status="RUNNING", current_node="COLLEGE_REVIEW")
            db.add(flow); db.flush()
            old = WorkflowTask(tenant_id=tenant, instance_id=flow.id, node_code="COLLEGE_REVIEW",
                               assignee_id=100, status="PENDING")
            db.add(old); db.flush()
            current = WorkflowTask(tenant_id=tenant, instance_id=flow.id, node_code="COLLEGE_REVIEW",
                                   assignee_id=200, status="PENDING")
            db.add(current); db.flush()
            if domain == "discipline":
                affairs_discipline_service._act_task(db,
                    SimpleNamespace(workflow_instance_id=flow.id, status="COLLEGE_REVIEW"), "APPROVED")
                assert current.status == "APPROVED"
                assert old.status == "PENDING"
            else:
                service = {"leave": affairs_leave_service, "aid": affairs_aid_service,
                           "funding": affairs_funding_service}[domain]
                assert service._cur_task(db, flow.id, "COLLEGE_REVIEW").id == current.id
    finally:
        set_tenant(previous)

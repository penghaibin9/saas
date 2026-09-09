from __future__ import annotations

from app.core.security import create_access_token


def _owner_headers() -> dict[str, str]:
    token = create_access_token({
        "userId": "w2-owner", "realName": "W2平台主管", "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "tenantId": "0", "tid": "platform",
        "activeContextId": "ctx-w2", "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_w2_workflow_projection_prefers_definition_over_legacy_json(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant, WorkflowDefinition
    from app.services import platform_control_authority_service as authority
    from app.services import platform_service

    tenant_id = 1000000000000096201
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            db.add(Tenant(id=tenant_id, tenant_code="w2-authority", school_name="W2流程学校", status="ACTIVE"))
            db.flush()
        row = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.workflow_code == "W2_TEST_FLOW",
        ).first()
        if row is None:
            db.add(WorkflowDefinition(
                tenant_id=tenant_id,
                workflow_code="W2_TEST_FLOW",
                workflow_name="W2测试流程",
                source_module="student",
                source_biz_type="TEST",
                source_profile="TEST",
                installed_project_id=0,
                status="ENABLED",
                policy_confirmed=True,
                timeout_hours=48,
            ))
        db.commit()
    finally:
        db.close()

    platform_service.put_config_json(tenant_id, "WORKFLOWS", "-", {
        "W2_TEST_FLOW": {"enabled": False, "timeoutHours": 24}
    })
    projection = authority.workflow_projection(tenant_id)
    assert projection["authority"] == "WORKFLOW_DEFINITION"
    assert projection["workflows"]["W2_TEST_FLOW"]["enabled"] is True
    assert projection["workflows"]["W2_TEST_FLOW"]["timeoutHours"] == 48
    drift = {item["workflowCode"]: item["state"] for item in projection["drift"]}
    assert drift["W2_TEST_FLOW"] == "CONFLICT"
    assert projection["legacyOverrideReadOnly"] is True


def test_w2_legacy_workflow_put_is_closed(client, db_mode):
    response = client.put(
        "/api/v1/platform/tenants/1000000000000000001/workflows/AFFAIRS_LEAVE",
        headers=_owner_headers(),
        json={"enabled": True, "timeoutHours": 48},
    )
    body = response.json()
    assert response.status_code == 409
    assert body["bizCode"] == "WORKFLOW_AUTHORITY_MOVED"
    assert body["details"]["authority"] == "WORKFLOW_DEFINITION"

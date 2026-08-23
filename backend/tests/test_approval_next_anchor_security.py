"""PR190 P2-03：审批 next seek 的 anchor 必须真实存在且对当前调用者可见。

真实 MySQL 回归：
- 已办的本人 anchor 仍可定位，返回它之后的本人 PENDING；
- 非数字 / 不存在 anchor 一律 404，绝不退化成队首；
- 他人 anchor 一律 404，即使当前用户自己的队列里有候选任务也不能借此探测。
"""
from __future__ import annotations

TID = 1000000000000000001
UID_A = 95101
UID_B = 95102


def _headers(uid: int):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": f"u_{uid}",
        "loginName": f"next_anchor_{uid}",
        "realName": f"审批员{uid}",
        "userType": "TEACHER",
        "tid": "demo",
        "tenantId": str(TID),
        "activeContextId": f"ctx_{uid}",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        anchor_inst = WorkflowInstance(
            tenant_id=TID,
            workflow_code="ANCHOR_SECURITY_WF",
            source_module="test",
            source_biz_type="COMPANY_CHANGE",  # UNSUPPORTED context，不依赖业务源表
            source_biz_id=91001,
            applicant_id=99001,
            title="本人已办锚点",
            status="RUNNING",
            current_node="NODE_A",
        )
        db.add(anchor_inst)
        db.flush()
        anchor = WorkflowTask(
            tenant_id=TID,
            instance_id=anchor_inst.id,
            node_code="NODE_A",
            assignee_id=UID_A,
            status="APPROVED",
        )
        db.add(anchor)
        db.flush()

        candidate_inst = WorkflowInstance(
            tenant_id=TID,
            workflow_code="ANCHOR_SECURITY_WF",
            source_module="test",
            source_biz_type="COMPANY_CHANGE",
            source_biz_id=91002,
            applicant_id=99002,
            title="本人下一条待办",
            status="RUNNING",
            current_node="NODE_A",
        )
        db.add(candidate_inst)
        db.flush()
        candidate = WorkflowTask(
            tenant_id=TID,
            instance_id=candidate_inst.id,
            node_code="NODE_A",
            assignee_id=UID_A,
            status="PENDING",
        )
        db.add(candidate)
        db.flush()

        foreign_inst = WorkflowInstance(
            tenant_id=TID,
            workflow_code="ANCHOR_SECURITY_WF",
            source_module="test",
            source_biz_type="COMPANY_CHANGE",
            source_biz_id=91003,
            applicant_id=99003,
            title="他人已办锚点",
            status="RUNNING",
            current_node="NODE_A",
        )
        db.add(foreign_inst)
        db.flush()
        foreign = WorkflowTask(
            tenant_id=TID,
            instance_id=foreign_inst.id,
            node_code="NODE_A",
            assignee_id=UID_B,
            status="APPROVED",
        )
        db.add(foreign)
        db.commit()
        return anchor.id, candidate.id, foreign.id
    finally:
        db.close()


def test_next_accepts_authorized_processed_anchor_and_returns_next_pending(client, db_mode):
    anchor_id, candidate_id, _ = _seed(db_mode)
    response = client.get(
        f"/api/v1/approvals/tasks/{anchor_id}/next",
        headers=_headers(UID_A),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    assert body["data"]["taskId"] == str(candidate_id)


def test_next_invalid_or_missing_anchor_never_falls_back_to_queue_head(client, db_mode):
    _seed(db_mode)
    headers = _headers(UID_A)
    invalid = client.get("/api/v1/approvals/tasks/not-a-number/next", headers=headers)
    missing = client.get("/api/v1/approvals/tasks/999999999999/next", headers=headers)
    assert invalid.status_code == 404, invalid.text
    assert missing.status_code == 404, missing.text
    assert invalid.json()["bizCode"] == "DATA_NOT_FOUND"
    assert missing.json()["bizCode"] == "DATA_NOT_FOUND"


def test_next_foreign_anchor_is_hidden_even_when_caller_has_own_pending_queue(client, db_mode):
    _, candidate_id, foreign_id = _seed(db_mode)
    response = client.get(
        f"/api/v1/approvals/tasks/{foreign_id}/next",
        headers=_headers(UID_A),
    )
    assert response.status_code == 404, response.text
    assert response.json()["bizCode"] == "DATA_NOT_FOUND"

    # 证明失败不是“当前用户没有待办”导致：自己的 candidate 确实存在且可见。
    detail = client.get(
        f"/api/v1/approvals/tasks/{candidate_id}", headers=_headers(UID_A)
    )
    assert detail.status_code == 200 and detail.json()["code"] == 0, detail.text

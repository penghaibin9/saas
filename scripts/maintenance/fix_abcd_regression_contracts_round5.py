#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(
    str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts_round4.py"),
    run_name="__main__",
)


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) < count:
        raise SystemExit(f"round5 expected snippet not found: {path}\n---\n{old[:600]}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")
    print(f"round5 patched {path}")


replace(
    "backend/tests/test_mobile_wave10.py",
    '''def _drain_message_delivery_jobs():
    from app.core.context import set_tenant
    from app.services.message_delivery_service import claim_and_process_delivery_jobs
    set_tenant({"tenantId": str(MAIN)})
    try:
        for _ in range(3):
            if claim_and_process_delivery_jobs(limit=20, worker_id="test-notify-drain") == 0:
                break
    finally:
        set_tenant(None)
''',
    '''def _drain_message_delivery_jobs():
    """模拟调度器到达重试时间后的最终一致投递，并返回可诊断状态。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageDeliveryJob, UnifiedMessage
    from app.services.message_delivery_service import claim_and_process_delivery_jobs

    db = get_sessionmaker()()
    try:
        jobs = db.query(MessageDeliveryJob).filter(
            MessageDeliveryJob.tenant_id == MAIN,
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
        ).all()
        for job in jobs:
            job.status = "PENDING"
            job.next_retry_at = None
            job.locked_by = None
            job.locked_at = None
            job.lease_expires_at = None
        db.commit()
    finally:
        db.close()

    set_tenant({"tenantId": str(MAIN)})
    try:
        for _ in range(3):
            claim_and_process_delivery_jobs(limit=20, worker_id="test-notify-drain")
    finally:
        set_tenant(None)

    db = get_sessionmaker()()
    try:
        return {
            "jobs": [{
                "id": row.id, "status": row.status,
                "attemptCount": row.attempt_count,
                "lastError": row.last_error_code,
                "writtenCount": row.written_count,
                "recipients": list(row.recipient_slice_json or []),
            } for row in db.query(MessageDeliveryJob).filter(
                MessageDeliveryJob.tenant_id == MAIN,
                MessageDeliveryJob.is_deleted.is_(False),
            ).order_by(MessageDeliveryJob.id).all()],
            "messages": [{
                "id": row.id, "title": row.title,
                "receiverId": row.receiver_id,
                "receiverUserId": row.receiver_user_id,
                "category": row.category,
            } for row in db.query(UnifiedMessage).filter(
                UnifiedMessage.tenant_id == MAIN,
                UnifiedMessage.is_deleted.is_(False),
            ).order_by(UnifiedMessage.id).all()],
        }
    finally:
        db.close()
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
    msgs = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("期中考试安排" in m["title"] for m in msgs["groups"]["notice"])
''',
    '''    delivery = _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
    msgs = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("期中考试安排" in m["title"] for m in msgs["groups"]["notice"]), {
        "inbox": msgs, "delivery": delivery,
    }
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
    before = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("偏好测试通知" in m["title"] for m in before["groups"]["notice"])
''',
    '''    delivery = _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
    before = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("偏好测试通知" in m["title"] for m in before["groups"]["notice"]), {
        "inbox": before, "delivery": delivery,
    }
''',
)

print("ABCD D-stage eventual delivery contract patch complete")

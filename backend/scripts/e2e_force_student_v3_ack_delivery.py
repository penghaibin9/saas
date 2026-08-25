"""Re-arm the Student V3 acknowledgement campaign for external-worker recovery proof.

The Real Task seed deliberately uses the formal HTTP publish contract. That contract is allowed to
best-effort drain delivery jobs inline, which is correct product behaviour but cannot prove that the
standalone production worker can recover durable asynchronous debt after a process interruption.

This isolated-E2E helper therefore performs *fault injection only*:
1. take the formally published E2E acknowledgement campaign;
2. remove only that campaign's already-materialized personal messages and reset its durable
   MessageDeliveryJob rows to PENDING, modelling a crash after enqueue but before delivery;
3. enqueue one internship MessageEventOutbox probe through the production emit_message_event()
   producer contract;
4. exit without calling any delivery/outbox processor.

The workflow's separately started job_delivery_and_outbox() process is then the only actor allowed to
recover both debts. The paired wait helper proves the jobs/outbox became SUCCEEDED and the student
message API can read both messages before Playwright starts clicking. Production/staging targets are
rejected by the shared fixture safety gate.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from e2e_seed_student_v3_realtask import (
    MARK,
    STATE_PATH,
    assert_safe_target,
    _session,
    _student_facts,
)
from app.core.context import set_tenant
from app.services.message_event_outbox_service import emit_message_event

OUTBOX_PROBE_TITLE = f"{MARK} Worker Outbox 恢复探针"


def _tenant_context(tenant_id: int) -> dict:
    return {"tenantId": str(tenant_id)}


def main() -> int:
    assert_safe_target()
    if not STATE_PATH.exists():
        raise SystemExit("S9-RT state missing — run seed first")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    campaign_id = int((state.get("ackMessage") or {}).get("campaignId") or 0)
    if not campaign_id:
        raise SystemExit("S9-RT acknowledgement campaign missing")

    facts = _student_facts()
    tenant_id = int(facts["tenantId"])

    from app.models import MessageCampaign, MessageDeliveryJob, UnifiedMessage

    db = _session()
    try:
        set_tenant(_tenant_context(tenant_id))
        campaign = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == campaign_id,
            MessageCampaign.tenant_id == tenant_id,
            MessageCampaign.is_deleted.is_(False),
        ))
        if campaign is None:
            raise SystemExit(f"S9-RT acknowledgement campaign {campaign_id} missing")

        jobs = db.scalars(select(MessageDeliveryJob).where(
            MessageDeliveryJob.tenant_id == tenant_id,
            MessageDeliveryJob.campaign_id == campaign_id,
            MessageDeliveryJob.is_deleted.is_(False),
        ).order_by(MessageDeliveryJob.id.asc())).all()
        if not jobs:
            raise SystemExit(
                "S9-RT formal publish produced no durable MessageDeliveryJob; "
                "cannot prove external-worker recovery"
            )

        # Fault injection: emulate a process loss after durable enqueue but before personal-message
        # materialization. Never fabricate the expected final message; the external worker must do it.
        materialized = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.campaign_id == campaign_id,
            UnifiedMessage.is_deleted.is_(False),
        )).all()
        for row in materialized:
            db.delete(row)

        for job in jobs:
            job.status = "PENDING"
            job.attempt_count = 0
            job.next_retry_at = None
            job.locked_by = None
            job.locked_at = None
            job.lease_expires_at = None
            job.last_error_code = None
            job.written_count = 0

        campaign.status = "PUBLISHING"
        campaign.delivered_count = 0
        campaign.failure_count = 0
        campaign.version = int(campaign.version or 0) + 1

        # Separate Outbox recovery probe. This calls the real producer contract and commits a PENDING
        # outbox row, but intentionally never calls process_pending_outbox().
        outbox = emit_message_event(
            db,
            event_code="INTERNSHIP.COUNSELOR_NOTICE",
            source_module="internship",
            source_biz_type="worker_recovery_probe",
            source_biz_id=campaign_id,
            recipient_refs=[{"studentId": int(facts["studentId"])}],
            title=OUTBOX_PROBE_TITLE,
            content="独立消息 Worker/Outbox 恢复链真实投递探针。",
            dedup_key=f"{MARK}:worker-outbox:{campaign_id}",
        )
        db.commit()
        outbox_id = int(outbox.id)
        job_ids = [int(job.id) for job in jobs]
    finally:
        db.close()
        set_tenant(None)

    state["workerRecovery"] = {
        "campaignId": campaign_id,
        "deliveryJobIds": job_ids,
        "outboxId": outbox_id,
        "outboxTitle": OUTBOX_PROBE_TITLE,
        "prepared": True,
        "verified": False,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[s9-rt] external-worker recovery armed campaign={campaign_id} "
        f"deliveryJobs={job_ids} outbox={outbox_id}; no worker drained in helper"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

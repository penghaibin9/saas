"""Wait for the standalone production-style message worker to recover Student V3 debts.

The paired preparation helper has already:
- formally published the acknowledgement campaign through the real HTTP contract;
- fault-injected only that isolated campaign back to durable PENDING delivery jobs;
- emitted one internship MessageEventOutbox row through the real producer contract;
- exited without processing either debt.

This helper is intentionally read/poll only. It MUST NOT import or call
claim_and_process_delivery_jobs(), process_pending_outbox(), or job_delivery_and_outbox(). The
workflow's independently started worker process is the only actor allowed to turn those durable
rows into personal messages. Success requires both durable states to be SUCCEEDED and both messages
to be readable through the real student message API.
"""
from __future__ import annotations

import json
import time
from collections import Counter

from sqlalchemy import select

from app.core.context import set_tenant
from app.models import MessageCampaign, MessageDeliveryJob, MessageEventOutbox, UnifiedMessage

from scripts.e2e_seed_student_v3_realtask import (
    ACK_TITLE,
    STATE_PATH,
    STUDENT_LOGIN,
    _call,
    _login,
    _session,
    _student_facts,
    assert_safe_target,
)

_MAX_ROUNDS = 60
_SLEEP_SECONDS = 1


def _tenant_context(tenant_id: int) -> dict:
    return {"tenantId": str(tenant_id)}


def _student_titles(token: str) -> set[str]:
    data = _call("/student-mini/messages?page=1&pageSize=100", token)
    return {str(row.get("title") or "") for row in (data.get("items") or [])}


def _diagnostics(facts: dict, state: dict) -> dict:
    tenant_id = int(facts["tenantId"])
    recovery = state.get("workerRecovery") or {}
    campaign_id = int(recovery.get("campaignId") or 0)
    outbox_id = int(recovery.get("outboxId") or 0)

    db = _session()
    try:
        set_tenant(_tenant_context(tenant_id))
        campaign = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == campaign_id,
            MessageCampaign.tenant_id == tenant_id,
            MessageCampaign.is_deleted.is_(False),
        )) if campaign_id else None
        jobs = db.scalars(select(MessageDeliveryJob).where(
            MessageDeliveryJob.tenant_id == tenant_id,
            MessageDeliveryJob.campaign_id == campaign_id,
            MessageDeliveryJob.is_deleted.is_(False),
        ).order_by(MessageDeliveryJob.id.asc())).all() if campaign_id else []
        outbox = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.id == outbox_id,
            MessageEventOutbox.tenant_id == tenant_id,
            MessageEventOutbox.is_deleted.is_(False),
        )) if outbox_id else None
        ack_rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.campaign_id == campaign_id,
            UnifiedMessage.is_deleted.is_(False),
        )).all() if campaign_id else []
        outbox_rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.source_module == "internship",
            UnifiedMessage.source_biz_id == campaign_id,
            UnifiedMessage.title == recovery.get("outboxTitle"),
            UnifiedMessage.is_deleted.is_(False),
        )).all() if campaign_id else []

        job_statuses = Counter(str(job.status or "") for job in jobs)
        return {
            "campaignId": campaign_id,
            "campaignStatus": getattr(campaign, "status", None),
            "campaignRecipientCount": int(getattr(campaign, "recipient_count", 0) or 0)
            if campaign else None,
            "campaignDeliveredCount": int(getattr(campaign, "delivered_count", 0) or 0)
            if campaign else None,
            "deliveryJobCount": len(jobs),
            "deliveryJobStatuses": dict(job_statuses),
            "deliveryAttemptCount": sum(int(job.attempt_count or 0) for job in jobs),
            "deliveryWrittenCount": sum(int(job.written_count or 0) for job in jobs),
            "outboxId": outbox_id,
            "outboxStatus": getattr(outbox, "status", None),
            "outboxAttemptCount": int(getattr(outbox, "attempt_count", 0) or 0)
            if outbox else 0,
            "ackUnifiedMessageCount": len(ack_rows),
            "outboxUnifiedMessageCount": len(outbox_rows),
        }
    finally:
        db.close()
        set_tenant(None)


def _durable_recovery_complete(diag: dict) -> bool:
    jobs = int(diag.get("deliveryJobCount") or 0)
    succeeded = int((diag.get("deliveryJobStatuses") or {}).get("SUCCEEDED") or 0)
    return bool(
        jobs > 0
        and succeeded == jobs
        and int(diag.get("deliveryAttemptCount") or 0) >= jobs
        and str(diag.get("outboxStatus") or "").upper() == "SUCCEEDED"
        and int(diag.get("outboxAttemptCount") or 0) >= 1
        and int(diag.get("ackUnifiedMessageCount") or 0) >= 1
        and int(diag.get("outboxUnifiedMessageCount") or 0) >= 1
    )


def main() -> int:
    assert_safe_target()
    if not STATE_PATH.exists():
        raise SystemExit("S9-RT state missing — run seed/recovery preparation first")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    recovery = state.get("workerRecovery") or {}
    if not recovery.get("prepared"):
        raise SystemExit("S9-RT external-worker recovery was not armed")
    outbox_title = str(recovery.get("outboxTitle") or "")
    if not outbox_title:
        raise SystemExit("S9-RT outbox probe title missing")

    facts = _student_facts()
    student_token = _login(*STUDENT_LOGIN)
    last_diag = {}
    last_titles: set[str] = set()

    for round_no in range(1, _MAX_ROUNDS + 1):
        last_titles = _student_titles(student_token)
        last_diag = _diagnostics(facts, state)
        api_ready = ACK_TITLE in last_titles and outbox_title in last_titles
        if api_ready and _durable_recovery_complete(last_diag):
            recovery.update({
                "verified": True,
                "deliveryAttemptCount": int(last_diag["deliveryAttemptCount"]),
                "deliveryWrittenCount": int(last_diag["deliveryWrittenCount"]),
                "outboxAttemptCount": int(last_diag["outboxAttemptCount"]),
                "deliveryJobStatuses": last_diag["deliveryJobStatuses"],
                "campaignStatus": last_diag["campaignStatus"],
            })
            state["workerRecovery"] = recovery
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                "[s9-rt] external worker recovery verified "
                f"round={round_no} diagnostics="
                + json.dumps(last_diag, ensure_ascii=False, sort_keys=True)
            )
            return 0
        time.sleep(_SLEEP_SECONDS)

    raise SystemExit(
        "S9-RT standalone worker did not recover delivery/outbox debt: "
        + json.dumps({
            "diagnostics": last_diag,
            "ackVisible": ACK_TITLE in last_titles,
            "outboxVisible": outbox_title in last_titles,
        }, ensure_ascii=False, sort_keys=True)
    )


if __name__ == "__main__":
    raise SystemExit(main())

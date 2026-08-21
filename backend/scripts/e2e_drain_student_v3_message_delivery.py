"""Drain canonical external message workers for the Student V3 Real Task fixture.

The production publish endpoint is intentionally asynchronous. During 22:00–07:00 quiet hours,
a normal IMMEDIATE message is also intentionally converted to SCHEDULED, so no delivery job exists
until the external scheduled-message worker reaches ``scheduled_at``. Playwright itself runs with
``SCHEDULER_MODE=external`` and does not start that process.

This test-only helper therefore replays the same two production stages in order:
1. if the seeded acknowledgement was quiet-hour scheduled, simulate the scheduler clock reaching
   its persisted ``scheduled_at`` and call the canonical ``process_scheduled_campaigns`` service;
2. drain the canonical delivery-job worker and prove the student can read the message through the
   real student message API.

No campaign status, recipient row, delivery job, or UnifiedMessage is fabricated directly. The
helper refuses non-local/non-test databases via the Real Task fixture safety gate.
"""
from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select

from app.core.context import set_tenant
from app.models import MessageCampaign, MessageDeliveryJob, StudentProfile, UnifiedMessage, User
from app.services import message_campaign_service, message_delivery_service

from scripts.e2e_seed_student_v3_realtask import (
    ACK_TITLE,
    STATE_PATH,
    STUDENT_LOGIN,
    STUDENT_NO,
    _call,
    _login,
    _session,
    _student_facts,
    assert_safe_target,
)

_MAX_ROUNDS = 12
_BATCH_LIMIT = 40


def _tenant_context(facts: dict) -> dict:
    """Match the request runtime tenant context shape expected by current_tenant_id()."""
    return {"tenantId": facts["tenantId"]}


def _campaign_id_from_state() -> int | None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    return int(((state.get("ackMessage") or {}).get("campaignId") or 0)) or None


def _student_inbox_has_ack(token: str) -> bool:
    data = _call("/student-mini/messages?page=1&pageSize=100", token)
    return any(str(row.get("title") or "") == ACK_TITLE for row in (data.get("items") or []))


def _materialize_scheduled_campaign_if_needed(facts: dict) -> int:
    """Replay the production scheduled-message stage without bypassing quiet-hour semantics.

    CI can run at any wall-clock hour. If publish occurred in quiet hours, waiting until 07:00 would
    make the browser gate nondeterministic. Instead, for this isolated local fixture only, advance
    the campaign service's clock to the already-persisted scheduled_at and invoke the exact
    production scheduler service. This changes no database fact by hand.
    """
    campaign_id = _campaign_id_from_state()
    if not campaign_id:
        return 0

    db = _session()
    try:
        set_tenant(_tenant_context(facts))
        campaign = db.get(MessageCampaign, campaign_id)
        if not campaign or str(campaign.status or "").upper() != "SCHEDULED":
            return 0
        scheduled_at = campaign.scheduled_at
        if scheduled_at is None:
            raise SystemExit("S9-RT campaign is SCHEDULED without scheduled_at")
    finally:
        db.close()

    original_now = message_campaign_service._utc_now
    try:
        # ``process_scheduled_campaigns`` itself owns the SCHEDULED -> PUBLISHING transition,
        # audience-fingerprint revalidation, and transactional delivery-job enqueue.
        message_campaign_service._utc_now = lambda: scheduled_at
        set_tenant(_tenant_context(facts))
        materialized = int(message_campaign_service.process_scheduled_campaigns(limit=30) or 0)
    finally:
        message_campaign_service._utc_now = original_now

    print(
        f"[s9-rt] scheduled-message worker replayed campaign={campaign_id} "
        f"scheduledAt={scheduled_at.isoformat()} processed={materialized}"
    )
    return materialized


def _diagnostics(facts: dict) -> dict:
    campaign_id = _campaign_id_from_state()
    db = _session()
    try:
        set_tenant(_tenant_context(facts))
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == facts["tenantId"],
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        account = db.scalars(select(User).where(
            User.tenant_id == facts["tenantId"],
            User.login_name == STUDENT_LOGIN[0],
            User.is_deleted.is_(False),
        )).first()
        campaign = db.get(MessageCampaign, campaign_id) if campaign_id else None
        jobs = db.scalars(select(MessageDeliveryJob).where(
            MessageDeliveryJob.tenant_id == facts["tenantId"],
            MessageDeliveryJob.campaign_id == campaign_id,
            MessageDeliveryJob.is_deleted.is_(False),
        )).all() if campaign_id else []
        rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == facts["tenantId"],
            UnifiedMessage.campaign_id == campaign_id,
            UnifiedMessage.is_deleted.is_(False),
        )).all() if campaign_id else []
        return {
            "campaignId": campaign_id,
            "campaignStatus": getattr(campaign, "status", None),
            "scheduledAt": getattr(campaign, "scheduled_at", None).isoformat()
            if campaign and getattr(campaign, "scheduled_at", None) else None,
            "recipientCount": int(getattr(campaign, "recipient_count", 0) or 0) if campaign else None,
            "deliveredCount": int(getattr(campaign, "delivered_count", 0) or 0) if campaign else None,
            "jobStatuses": dict(Counter(str(job.status or "") for job in jobs)),
            "campaignMessageReceiverUserIds": sorted({int(row.receiver_user_id) for row in rows if row.receiver_user_id}),
            "studentProfileStatus": getattr(student, "status", None),
            "studentLifecycleStatus": getattr(student, "student_status", None),
            "studentAccountUserId": int(account.id) if account else None,
            "studentAccountStatus": getattr(account, "status", None),
        }
    finally:
        db.close()


def main() -> int:
    assert_safe_target()
    facts = _student_facts()
    set_tenant(_tenant_context(facts))
    student_token = _login(*STUDENT_LOGIN)

    if _student_inbox_has_ack(student_token):
        print("[s9-rt] acknowledgement message already materialized")
        return 0

    # In quiet hours the publish API correctly returns SCHEDULED and has no delivery jobs yet.
    # Replaying the external scheduled-message stage makes this browser fixture independent of
    # the CI runner's wall-clock time while preserving the production state machine.
    _materialize_scheduled_campaign_if_needed(facts)

    processed = 0
    for round_no in range(1, _MAX_ROUNDS + 1):
        set_tenant(_tenant_context(facts))
        count = message_delivery_service.claim_and_process_delivery_jobs(
            limit=_BATCH_LIMIT,
            worker_id=f"e2e-student-v3-{round_no}",
        )
        processed += int(count or 0)
        if _student_inbox_has_ack(student_token):
            print(f"[s9-rt] acknowledgement materialized after worker rounds={round_no} processed={processed}")
            return 0
        if not count:
            break

    diag = _diagnostics(facts)
    raise SystemExit(
        "S9-RT acknowledgement was not visible after replaying canonical scheduled/delivery workers: "
        + json.dumps(diag, ensure_ascii=False, sort_keys=True)
    )


if __name__ == "__main__":
    raise SystemExit(main())

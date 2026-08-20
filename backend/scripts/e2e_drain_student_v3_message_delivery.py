"""Drain the external message-delivery worker for the Student V3 Real Task fixture.

The production publish endpoint is intentionally asynchronous: it persists delivery jobs and
only makes a best-effort inline claim. Playwright runs with ``SCHEDULER_MODE=external``, so a
fixture that immediately opens the inbox must explicitly execute the same delivery worker that
production runs out of process. This helper does exactly that and then proves the target student
can read the seeded acknowledgement message through the canonical student message API.

It is test-only and refuses non-local/non-test databases via the Real Task fixture safety gate.
"""
from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select

from app.core.context import set_tenant
from app.models import MessageCampaign, MessageDeliveryJob, StudentProfile, UnifiedMessage, User
from app.services import message_delivery_service

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


def _student_inbox_has_ack(token: str) -> bool:
    data = _call("/student-mini/messages?page=1&pageSize=100", token)
    return any(str(row.get("title") or "") == ACK_TITLE for row in (data.get("items") or []))


def _diagnostics(facts: dict) -> dict:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    campaign_id = int(((state.get("ackMessage") or {}).get("campaignId") or 0)) or None
    db = _session()
    try:
        set_tenant(facts["tenantId"])
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
    set_tenant(facts["tenantId"])
    student_token = _login(*STUDENT_LOGIN)

    if _student_inbox_has_ack(student_token):
        print("[s9-rt] acknowledgement message already materialized")
        return 0

    processed = 0
    for round_no in range(1, _MAX_ROUNDS + 1):
        set_tenant(facts["tenantId"])
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
        "S9-RT acknowledgement was not visible after draining canonical delivery jobs: "
        + json.dumps(diag, ensure_ascii=False, sort_keys=True)
    )


if __name__ == "__main__":
    raise SystemExit(main())

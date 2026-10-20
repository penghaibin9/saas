"""Student360 timeline shadow reader; sections remain untouched domain reads."""
from __future__ import annotations

from sqlalchemy import select

from app.modules.platform.document_lifecycle.models import StudentLifecycleFact
from app.modules.platform.document_lifecycle.student360_shadow import TimelineIdentity, timeline_shadow_metrics


def shadow_fact_timeline(db, *, tenant_id: int, student_id: int, legacy_events: list) -> dict:
    facts = list(db.scalars(select(StudentLifecycleFact).where(
        StudentLifecycleFact.tenant_id == tenant_id,
        StudentLifecycleFact.student_id == student_id,
    ).order_by(StudentLifecycleFact.event_time.desc(), StudentLifecycleFact.id.desc()).limit(10)).all())
    legacy = [TimelineIdentity(
        str(event.source_module or ""), str(event.to_stage or ""), event.occurred_at.isoformat(),
    ) for event in legacy_events]
    projected = [TimelineIdentity(
        str(fact.source_module), str(fact.fact_type), fact.event_time.isoformat(),
    ) for fact in facts]
    return {
        "source": "LEGACY_STUDENT_STAGE_EVENT",
        "candidateSource": "STUDENT_LIFECYCLE_FACT",
        "metrics": timeline_shadow_metrics(legacy, projected),
        "factItems": [{
            "id": str(fact.id), "stage": fact.fact_type,
            "time": fact.event_time.isoformat(), "actionKey": None,
        } for fact in facts],
    }

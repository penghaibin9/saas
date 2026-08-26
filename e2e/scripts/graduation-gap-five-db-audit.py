#!/usr/bin/env python3
"""Direct MySQL seal for the five targeted Graduation gaps.

Browser tests perform every target command. This script only verifies persisted truth,
audit/message/todo projections, and state-machine terminal facts afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models.approval import UnifiedTodo
from app.models.graduation import (
    GraduationAuditTrail,
    GraduationDefenseGroup,
    GraduationPeerReview,
    GraduationRiskCase,
)
from app.models.graduation_extension import GraduationDefenseDelay, GraduationExcellentOutcome
from app.models.message import UnifiedMessage

TENANT_ID = 1000000000000000007


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    fixture = json.loads(Path("../e2e/runtime-logs/gap-five-fixture.json").read_text(encoding="utf-8"))
    batch_id = int(fixture["batchId"])
    a = int(fixture["students"]["A"]["gdStudentId"])
    b = int(fixture["students"]["B"]["gdStudentId"])
    c = int(fixture["students"]["C"]["gdStudentId"])
    final_id = int(fixture["finalId"])
    valid_group = f"GD013-正式组-{fixture['runId']}"

    db = get_sessionmaker()()
    try:
        peer = db.scalars(select(GraduationPeerReview).where(
            GraduationPeerReview.tenant_id == TENANT_ID,
            GraduationPeerReview.gd_student_id == a,
            GraduationPeerReview.reviewer_gd_student_id == b,
            GraduationPeerReview.is_deleted.is_(False),
        ).order_by(GraduationPeerReview.id.desc())).first()
        require(peer is not None, "GD-012 missing peer review row")
        require(peer.status == "RECTIFIED", f"GD-012 expected RECTIFIED, got {peer.status}")
        require(int(peer.gd_final_id or 0) == final_id, f"GD-012 peer task not bound to frozen final {final_id}")
        require(bool(peer.opinion and len(peer.opinion) >= 5), "GD-012 opinion missing")
        require(bool(peer.rectify_note and len(peer.rectify_note) >= 5), "GD-012 rectify note missing")

        excellent = db.scalars(select(GraduationExcellentOutcome).where(
            GraduationExcellentOutcome.tenant_id == TENANT_ID,
            GraduationExcellentOutcome.gd_student_id == a,
            GraduationExcellentOutcome.is_deleted.is_(False),
        )).first()
        require(excellent is not None, "GD-016 missing excellent outcome")
        require(excellent.status == "PUBLISHED", f"GD-016 expected PUBLISHED, got {excellent.status}")
        require(excellent.major_reviewed_at is not None and excellent.college_reviewed_at is not None,
                "GD-016 missing major/college review timestamps")

        risk = db.scalars(select(GraduationRiskCase).where(
            GraduationRiskCase.tenant_id == TENANT_ID,
            GraduationRiskCase.gd_student_id == c,
            GraduationRiskCase.risk_code == "GD-R01",
            GraduationRiskCase.is_deleted.is_(False),
        )).first()
        require(risk is not None, "GD-017 missing GD-R01 risk")
        require(risk.status == "CLOSED", f"GD-017 expected CLOSED, got {risk.status}")
        require(bool(risk.handle_note), "GD-017 handle note missing")
        require(bool(risk.close_reason), "GD-017 close reason missing")
        require(risk.closed_at is not None, "GD-017 closed_at missing")

        group = db.scalars(select(GraduationDefenseGroup).where(
            GraduationDefenseGroup.tenant_id == TENANT_ID,
            GraduationDefenseGroup.batch_id == batch_id,
            GraduationDefenseGroup.group_name == valid_group,
            GraduationDefenseGroup.is_deleted.is_(False),
        )).first()
        require(group is not None, "GD-013 missing canonical defense group")
        require(bool(group.published), "GD-013/GD-019 canonical group must end published")

        delay = db.scalars(select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == TENANT_ID,
            GraduationDefenseDelay.gd_student_id == b,
            GraduationDefenseDelay.is_deleted.is_(False),
        ).order_by(GraduationDefenseDelay.id.desc())).first()
        require(delay is not None, "GD-013 missing defense delay")
        require(delay.status == "SCHEDULED", f"GD-013 delay expected SCHEDULED, got {delay.status}")
        require(int(delay.defense_group_id or 0) == int(group.id), "GD-013 delay scheduled to wrong group")
        require(delay.advisor_reviewed_at and delay.major_reviewed_at and delay.college_reviewed_at and delay.scheduled_at,
                "GD-013 delay evidence chain incomplete")

        audit_count = db.scalar(select(func.count()).select_from(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == TENANT_ID,
            GraduationAuditTrail.batch_id == batch_id,
        )) or 0
        require(audit_count >= 8, f"GD-019 expected >=8 graduation audit rows for gap batch, got {audit_count}")

        messages = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TENANT_ID,
            UnifiedMessage.is_deleted.is_(False),
            UnifiedMessage.title.like("%答辩%"),
        ).order_by(UnifiedMessage.id.desc()).limit(20)).all()
        relevant_messages = [m for m in messages if str(m.source_biz_id or "") == str(group.id) or valid_group in (m.title or "") or valid_group in (m.content or "")]
        require(relevant_messages, "GD-019 no persisted defense notification message found")

        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == TENANT_ID,
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.source_module.in_(["graduation", "gd"]),
        ).order_by(UnifiedTodo.id.desc()).limit(100)).all()
        relevant_todos = [t for t in todos if t.student_id in {a, b, c} or t.source_biz_id in {peer.id, group.id, delay.id, excellent.id, risk.id}]
        require(relevant_todos, "GD-019 no graduation todo projection found for targeted business facts")

        print(json.dumps({
            "GD-012": {"peerId": str(peer.id), "status": peer.status, "finalId": str(peer.gd_final_id)},
            "GD-013": {"groupId": str(group.id), "published": bool(group.published), "delayId": str(delay.id), "delayStatus": delay.status},
            "GD-016": {"excellentId": str(excellent.id), "status": excellent.status},
            "GD-017": {"riskId": str(risk.id), "status": risk.status, "riskCode": risk.risk_code},
            "GD-019": {"auditCount": int(audit_count), "messageCount": len(relevant_messages), "todoCount": len(relevant_todos)},
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

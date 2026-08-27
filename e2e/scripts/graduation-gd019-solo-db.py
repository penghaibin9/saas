#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models.approval import UnifiedTodo
from app.models.graduation import (
    GraduationAuditTrail,
    GraduationDefenseGroup,
    GraduationGrade,
    GraduationPeerReview,
    GraduationStudent,
)
from app.models.message import UnifiedMessage

TENANT_ID = 1000000000000000007


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    fixture = json.loads(Path("../e2e/runtime-logs/gd019-solo-fixture.json").read_text(encoding="utf-8"))
    batch_id = int(fixture["batchId"])
    group_id = int(fixture["groupId"])
    peer_id = int(fixture["peerId"])
    grade_id = int(fixture["gradeId"])
    student_b_id = int(fixture["students"]["B"]["gdStudentId"])

    db = get_sessionmaker()()
    try:
        group = db.get(GraduationDefenseGroup, group_id)
        require(group is not None and not group.is_deleted, "GD019 solo: defense group missing")
        require(int(group.batch_id or 0) == batch_id, "GD019 solo: defense group batch mismatch")
        require(bool(group.published), "GD019 solo: defense group must remain published")
        require(int(group.student_count or 0) == 1, f"GD019 solo: expected group student_count=1, got {group.student_count}")

        student = db.get(GraduationStudent, student_b_id)
        require(student is not None and not student.is_deleted, "GD019 solo: Student B missing")
        require(int(student.defense_group_id or 0) == group_id, "GD019 solo: Student B assignment missing")

        peer = db.get(GraduationPeerReview, peer_id)
        require(peer is not None and not peer.is_deleted, "GD019 solo: peer stats source row missing")
        require(peer.status == "RECTIFIED", f"GD019 solo: expected peer RECTIFIED, got {peer.status}")
        require(bool(peer.opinion), "GD019 solo: peer opinion missing")
        require(bool(peer.rectify_note), "GD019 solo: peer rectify note missing")

        grade = db.get(GraduationGrade, grade_id)
        require(grade is not None and not grade.is_deleted, "GD019 solo: grade stats source row missing")
        require(grade.status == "PUBLISHED", f"GD019 solo: expected grade PUBLISHED, got {grade.status}")
        require(grade.grade_level == "优秀", f"GD019 solo: expected 优秀, got {grade.grade_level}")

        messages = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TENANT_ID,
            UnifiedMessage.is_deleted.is_(False),
            UnifiedMessage.title.like("%答辩%"),
        ).order_by(UnifiedMessage.id.desc()).limit(30)).all()
        relevant_messages = [
            m for m in messages
            if str(m.source_biz_id or "") == str(group_id)
            or fixture["groupName"] in (m.title or "")
            or fixture["groupName"] in (m.content or "")
        ]
        require(len(relevant_messages) >= 1, "GD019 solo: no persisted defense notification message found")

        export_audits = db.scalars(select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == TENANT_ID,
            GraduationAuditTrail.batch_id == batch_id,
            GraduationAuditTrail.biz_type == "DEFENSE",
            GraduationAuditTrail.biz_id == "export",
            GraduationAuditTrail.action == "导出答辩安排台账",
        ).order_by(GraduationAuditTrail.id.desc())).all()
        require(len(export_audits) >= 1, "GD019 solo: XLSX export audit row missing")
        require(any("sha256=" in (a.detail or "") for a in export_audits),
                "GD019 solo: XLSX export audit missing sha256 evidence")

        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == TENANT_ID,
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.source_module.in_(["graduation", "gd"]),
        ).order_by(UnifiedTodo.id.desc()).limit(100)).all()
        relevant_todos = [t for t in todos if int(t.source_biz_id or 0) in {group_id, peer_id, grade_id}]

        evidence = {
            "batchId": str(batch_id),
            "group": {
                "id": str(group.id),
                "name": group.group_name,
                "published": bool(group.published),
                "studentCount": int(group.student_count or 0),
            },
            "peer": {"id": str(peer.id), "status": peer.status},
            "grade": {"id": str(grade.id), "status": grade.status, "gradeLevel": grade.grade_level},
            "notificationMessageCount": len(relevant_messages),
            "exportAuditCount": len(export_audits),
            "exportAuditHasSha256": any("sha256=" in (a.detail or "") for a in export_audits),
            "todoApplicableToTargetFacts": False,
            "targetFactTodoCountDiagnostic": len(relevant_todos),
        }
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

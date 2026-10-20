from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import StudentProfile, StudentStageEvent
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact
from scripts import backfill_platform_c_lifecycle_facts as backfill


def test_backfill_is_keyset_resumable_idempotent_and_excludes_sandbox(monkeypatch, tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    StudentProfile.__table__.create(engine)
    StudentStageEvent.__table__.create(engine)
    StudentLifecycleFact.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(backfill, "get_sessionmaker", lambda: sessions)

    with Session(engine) as db:
        db.add(StudentProfile(
            id=1, tenant_id=101, student_no="S1", real_name="Student 1",
            current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
        ))
        db.add_all([
            StudentStageEvent(
                id=1, tenant_id=101, student_id=1, from_stage=None, to_stage="ENROLLED",
                source_module="student", occurred_at=datetime(2026, 8, 1),
            ),
            StudentStageEvent(
                id=2, tenant_id=101, student_id=1, from_stage=None, to_stage="DEMO",
                source_module="sandbox", occurred_at=datetime(2026, 8, 2),
            ),
            StudentStageEvent(
                id=3, tenant_id=101, student_id=1, from_stage="ENROLLED", to_stage="GRADUATED",
                source_module="academic-affairs", occurred_at=datetime(2026, 8, 3),
            ),
        ])
        db.commit()

    checkpoint = tmp_path / "plat-c-checkpoint.json"
    first = backfill.run(
        tenant_id=101, batch_size=10, dry_run=False,
        checkpoint_path=checkpoint, max_rows=2,
    )
    assert first["written"] == 1
    assert first["excluded"] == 1
    assert first["lastId"] == 2
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["tenantId"] == 101

    second = backfill.run(
        tenant_id=101, batch_size=1, dry_run=False, checkpoint_path=checkpoint,
    )
    assert second["written"] == 1
    assert second["lastId"] == 3
    assert second["sourceEligibleCount"] == 2
    assert second["postFactCount"] == 2
    assert second["missingCount"] == 0

    third = backfill.run(
        tenant_id=101, batch_size=10, dry_run=False, checkpoint_path=checkpoint,
    )
    assert third["written"] == 0
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(StudentLifecycleFact)) == 2
    engine.dispose()

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.lifecycle_fact_writer import (
    LifecycleFactInput,
    record_in_session,
)
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact
from app.modules.platform.document_lifecycle.student360_shadow import (
    TimelineIdentity,
    timeline_shadow_metrics,
)


@pytest.fixture()
def fact_input() -> LifecycleFactInput:
    return LifecycleFactInput(
        student_id=7,
        college_id=8,
        source_module="graduation",
        fact_type="GRADUATION_ARCHIVED",
        source_biz_type="GRADUATION_STUDENT",
        source_biz_id="9",
        source_version="3",
        event_time=datetime(2026, 8, 29, 10, 0, 0),
        title="毕业设计已归档",
        summary="归档里程碑",
        importance="HIGH",
        visibility_code="STUDENT_SELF_AND_SCOPED_STAFF",
        sensitivity_level="PERSONAL",
        target_ref={"type": "GRADUATION_STUDENT", "id": "9", "action": "VIEW"},
    )


@pytest.fixture()
def fact_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    StudentLifecycleFact.__table__.create(engine)
    set_tenant(101)
    try:
        yield engine
    finally:
        set_tenant(None)
        engine.dispose()


def test_fact_rolls_back_with_canonical_business_transaction(fact_db, fact_input) -> None:
    with Session(fact_db) as db:
        record_in_session(db, fact_input)
        assert db.scalar(select(StudentLifecycleFact.id)) is not None
        db.rollback()
    with Session(fact_db) as db:
        assert db.scalar(select(StudentLifecycleFact.id)) is None


def test_fact_is_idempotent_in_same_session(fact_db, fact_input) -> None:
    with Session(fact_db) as db, db.begin():
        first = record_in_session(db, fact_input)
        second = record_in_session(db, fact_input)
        assert first.id == second.id
    with Session(fact_db) as db:
        assert len(db.scalars(select(StudentLifecycleFact)).all()) == 1


@pytest.mark.parametrize("target", [{"url": "/admin/x"}, {"type": "X", "value": "https://bad.invalid"}])
def test_fact_rejects_raw_navigation(fact_db, fact_input, target) -> None:
    value = LifecycleFactInput(**{**fact_input.__dict__, "target_ref": target}) if hasattr(fact_input, "__dict__") else LifecycleFactInput(
        **{field: getattr(fact_input, field) for field in fact_input.__dataclass_fields__ if field != "target_ref"},
        target_ref=target,
    )
    with Session(fact_db) as db, pytest.raises(AppException):
        record_in_session(db, value)


def test_shadow_metrics_are_anonymous_counts_only() -> None:
    legacy = [TimelineIdentity("graduation", "ARCHIVED", "2026-08-29T10:00:00")]
    facts = [TimelineIdentity("graduation", "COMPLETED", "2026-08-29T10:00:00")]
    metrics = timeline_shadow_metrics(legacy, facts)
    assert metrics["factTypeMismatch"] == 1
    assert set(metrics) == {
        "legacyCount", "factCount", "missingCount", "extraCount", "orderMismatch", "factTypeMismatch",
    }


def test_fact_writer_never_opens_or_commits_a_second_session() -> None:
    source = Path("app/modules/platform/document_lifecycle/lifecycle_fact_writer.py").read_text(encoding="utf-8")
    assert "get_sessionmaker" not in source
    assert ".commit(" not in source

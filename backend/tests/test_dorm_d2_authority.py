"""D2 DormStay and allocation-batch schema authority."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

TID = 1000000000000000001


def test_d2_models_are_stable_id_authorities():
    from app.models import DormAllocationBatch, DormAllocationItem, DormStay

    assert DormStay.__tablename__ == "t_affairs_dorm_stay"
    assert DormAllocationBatch.__tablename__ == "t_affairs_dorm_allocation_batch"
    assert DormAllocationItem.__tablename__ == "t_affairs_dorm_allocation_item"
    assert {column.name for column in DormStay.__table__.columns} >= {
        "student_id", "bed_id", "building_id", "room_id", "source_type", "source_biz_id",
        "checkin_at", "checkout_at", "status", "checkin_operator_id", "checkout_operator_id",
    }
    assert {column.name for column in DormAllocationBatch.__table__.columns} >= {
        "batch_no", "academic_year", "source_type", "orientation_batch_id", "mode",
        "open_at", "close_at", "rules_json", "resource_scope_json", "student_scope_json",
    }
    assert {column.name for column in DormAllocationItem.__table__.columns} >= {
        "allocation_batch_id", "student_id", "bed_id", "status", "source",
        "conflict_code", "confirmed_at",
    }


def test_d2_mysql_constraints_keep_window_and_one_student_item(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormAllocationItem

    db = get_sessionmaker()()
    now = datetime.utcnow()
    batch = DormAllocationBatch(
        tenant_id=TID,
        batch_no="D2-ALLOC-2026-01",
        name="D2 住宿分配",
        academic_year="2026-2027",
        source_type="ORIENTATION",
        orientation_batch_id=None,
        mode="STUDENT_SELECT",
        open_at=now,
        close_at=now + timedelta(days=2),
        status="DRAFT",
    )
    db.add(batch); db.flush()
    db.add(DormAllocationItem(
        tenant_id=TID,
        allocation_batch_id=batch.id,
        student_id=db_mode["student"],
        bed_id=None,
        status="PENDING",
        source="STUDENT_SELECT",
    ))
    db.commit()

    db.add(DormAllocationItem(
        tenant_id=TID,
        allocation_batch_id=batch.id,
        student_id=db_mode["student"],
        bed_id=None,
        status="PENDING",
        source="STUDENT_SELECT",
    ))
    with pytest.raises((IntegrityError, OperationalError)):
        db.commit()
    db.rollback(); db.close()

    db = get_sessionmaker()()
    db.add(DormAllocationBatch(
        tenant_id=TID,
        batch_no="D2-BAD-WINDOW",
        name="非法时间窗",
        academic_year="2026-2027",
        source_type="GENERAL",
        mode="ADMIN_MANUAL",
        open_at=now + timedelta(days=1),
        close_at=now,
        status="DRAFT",
    ))
    with pytest.raises((IntegrityError, OperationalError)):
        db.commit()
    db.rollback(); db.close()


def test_d2_migration_is_single_parent_and_refuses_string_guessing():
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260901_dorm_stay_alloc_d2.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260901_orientation_batch_o1"' in migration
    assert "t_cs_dorm_record" not in migration.split("from __future__", 1)[1]
    assert "JOIN t_student_profile" not in migration  # constants keep SQL table naming explicit
    assert "JOIN {STUDENT}" in migration
    assert "duplicate_occupied_student" in migration
    assert "duplicate_active_student" in migration and "duplicate_active_bed" in migration
    upgrade = migration.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]
    assert upgrade.index("_preflight_legacy_occupancy()") < upgrade.index("_expand()")
    assert "D2 downgrade blocked" in migration

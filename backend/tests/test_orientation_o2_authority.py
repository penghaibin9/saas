"""O2 versioned orientation flow and canonical student-step authority."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

TID = 1000000000000000001


def test_o2_models_define_versioned_flow_and_student_step_authority():
    from app.models import (OrientationBatch, OrientationFlowStep, OrientationFlowVersion,
                            OrientationStudentStep)

    assert OrientationFlowVersion.__tablename__ == "t_orientation_flow_version"
    assert OrientationFlowStep.__tablename__ == "t_orientation_flow_step"
    assert OrientationStudentStep.__tablename__ == "t_orientation_student_step"
    assert "flow_version_id" in OrientationBatch.__table__.columns
    assert {column.name for column in OrientationFlowVersion.__table__.columns} >= {
        "version_no", "version_name", "status", "source_type", "published_at", "published_by",
    }
    assert {column.name for column in OrientationFlowStep.__table__.columns} >= {
        "flow_version_id", "step_key", "step_name", "enabled", "required", "sort_order",
    }
    assert {column.name for column in OrientationStudentStep.__table__.columns} >= {
        "orientation_student_id", "flow_version_id", "flow_step_id", "step_key", "status",
        "status_source", "blocked_reason", "status_changed_at", "waived_at", "waived_by",
        "waive_reason", "waive_evidence_ref",
    }


def test_o2_mysql_rejects_unproven_waiver_and_duplicate_student_step(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (OrientationBatch, OrientationFlowStep, OrientationFlowVersion,
                            OrientationStudent, OrientationStudentStep)

    db = get_sessionmaker()()
    now = datetime.utcnow()
    version = OrientationFlowVersion(
        tenant_id=TID,
        version_no=2002,
        version_name="O2 测试发布版",
        status="PUBLISHED",
        source_type="MANUAL",
        published_at=now,
    )
    db.add(version); db.flush()
    step = OrientationFlowStep(
        tenant_id=TID,
        flow_version_id=version.id,
        step_key="INFO",
        step_name="信息核对",
        enabled=True,
        required=True,
        sort_order=0,
    )
    db.add(step); db.flush()
    batch = OrientationBatch(
        tenant_id=TID,
        batch_name="O2 约束测试批次",
        batch_no="O2-AUTHORITY-2026",
        year="2026",
        status="ACTIVE",
        planned_count=1,
        flow_version_id=version.id,
    )
    db.add(batch); db.flush()
    student = OrientationStudent(
        tenant_id=TID,
        batch_id=batch.id,
        student_id=db_mode["student"],
        name="O2约束学生",
        admission_no="O2-AUTHORITY-0001",
        source_type="MANUAL",
        source_record_id="O2-AUTHORITY-0001",
        identity_status="LINKED",
    )
    db.add(student); db.flush()
    canonical = OrientationStudentStep(
        tenant_id=TID,
        orientation_student_id=student.id,
        flow_version_id=version.id,
        flow_step_id=step.id,
        step_key="INFO",
        status="NOT_STARTED",
        status_source="PROCESS_FACT",
        status_changed_at=now,
    )
    db.add(canonical)
    db.commit()

    db.add(OrientationStudentStep(
        tenant_id=TID,
        orientation_student_id=student.id,
        flow_version_id=version.id,
        flow_step_id=step.id,
        step_key="INFO",
        status="DONE",
        status_source="PROCESS_FACT",
        status_changed_at=now,
    ))
    with pytest.raises((IntegrityError, OperationalError)):
        db.commit()
    db.rollback()

    canonical = db.get(OrientationStudentStep, canonical.id)
    canonical.status = "WAIVED"
    canonical.status_source = "MANUAL_WAIVER"
    canonical.waived_at = now
    canonical.waived_by = 9001
    canonical.waive_reason = "缺少证据引用"
    canonical.waive_evidence_ref = None
    with pytest.raises((IntegrityError, OperationalError)):
        db.commit()
    db.rollback(); db.close()


def test_o2_migration_is_serial_explicit_and_safe():
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260901_orientation_flow_o2.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260901_dorm_stay_alloc_d2"' in migration
    assert '"TODO": "NOT_STARTED"' in migration
    assert '"DOING": "IN_PROGRESS"' in migration
    assert "waived_without_evidence" in migration
    upgrade = migration.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]
    assert upgrade.index("_preflight_legacy_steps()") < upgrade.index("_expand()")
    assert "O2 downgrade blocked" in migration
    assert "college_name" not in migration and "class_name" not in migration

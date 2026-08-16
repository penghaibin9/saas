"""A-W2 canonical Program Activation resolver RED/GREEN contracts.

The resolver is the single read authority for Opening Projection, TeachingTask generation,
graduation and student academic progress.  It must not let each consumer reinterpret
PUBLISHED/ENABLED/FROZEN or binding precedence independently.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

import pytest

TID = 1000000000000000001


def _seed_scope(*, override_status="FROZEN"):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramBinding, Major, SchoolClass

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    major = Major(
        tenant_id=TID,
        college_id=961001,
        major_name=f"A-W2激活专业-{suffix}",
        code=f"AW2A-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    db.add(major)
    db.flush()
    override_class = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"A-W2特例班-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    fallback_class = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"A-W2通用班-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    db.add_all([override_class, fallback_class])
    generic = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2通用执行方案-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=3,
        status="ENABLED",
    )
    override = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2班级执行方案-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=4,
        status=override_status,
    )
    db.add_all([generic, override])
    db.flush()
    generic_binding = AaProgramBinding(
        tenant_id=TID,
        program_id=generic.id,
        major_id=major.id,
        grade_year="2026",
        class_id=None,
        bound_at=datetime(2026, 7, 1),
        status="ACTIVE",
    )
    override_binding = AaProgramBinding(
        tenant_id=TID,
        program_id=override.id,
        major_id=major.id,
        grade_year="2026",
        class_id=override_class.id,
        bound_at=datetime(2026, 7, 2),
        status="ACTIVE",
    )
    db.add_all([generic_binding, override_binding])
    db.commit()
    result = {
        "major_id": major.id,
        "override_class_id": override_class.id,
        "fallback_class_id": fallback_class.id,
        "generic_program_id": generic.id,
        "override_program_id": override.id,
        "generic_binding_id": generic_binding.id,
        "override_binding_id": override_binding.id,
    }
    db.close()
    return result


@pytest.mark.usefixtures("db_mode")
def test_w2_current_activation_prefers_class_override_and_keeps_frozen_bound_program_effective():
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services.academic_affairs_program_activation_service import (
        resolve_program_for_scope,
    )

    seeded = _seed_scope(override_status="FROZEN")
    db = get_sessionmaker()()
    override = resolve_program_for_scope(
        db,
        tenant_id=TID,
        major_id=seeded["major_id"],
        grade_year="2026",
        class_id=seeded["override_class_id"],
    )
    fallback = resolve_program_for_scope(
        db,
        tenant_id=TID,
        major_id=seeded["major_id"],
        grade_year="2026",
        class_id=seeded["fallback_class_id"],
    )
    db.close()

    assert override.status == "RESOLVED"
    assert override.rule == "CLASS_BINDING"
    assert override.program.id == seeded["override_program_id"]
    assert override.binding.id == seeded["override_binding_id"]
    assert override.program.status == "FROZEN"

    assert fallback.status == "RESOLVED"
    assert fallback.rule == "MAJOR_GRADE_BINDING"
    assert fallback.program.id == seeded["generic_program_id"]
    assert fallback.binding.id == seeded["generic_binding_id"]


@pytest.mark.usefixtures("db_mode")
def test_w2_current_activation_fails_closed_on_two_active_bindings_in_same_scope():
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramBinding, Major
    from app.modules.academic_affairs.services.academic_affairs_program_activation_service import (
        resolve_program_for_scope,
    )

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    major = Major(
        tenant_id=TID,
        college_id=962001,
        major_name=f"A-W2冲突专业-{suffix}",
        code=f"AW2X-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    db.add(major)
    db.flush()
    programs = [
        AaProgram(
            tenant_id=TID,
            program_name=f"A-W2冲突方案{label}-{suffix}",
            major_id=major.id,
            grade_year="2026",
            version=index,
            status=status,
        )
        for index, (label, status) in enumerate((("A", "PUBLISHED"), ("B", "ENABLED")), start=1)
    ]
    db.add_all(programs)
    db.flush()
    db.add_all([
        AaProgramBinding(
            tenant_id=TID,
            program_id=program.id,
            major_id=major.id,
            grade_year="2026",
            class_id=None,
            bound_at=datetime(2026, 7, 1),
            status="ACTIVE",
        )
        for program in programs
    ])
    db.commit()

    result = resolve_program_for_scope(
        db,
        tenant_id=TID,
        major_id=major.id,
        grade_year="2026",
        class_id=None,
    )
    db.close()

    assert result.status == "AMBIGUOUS"
    assert result.rule == "MAJOR_GRADE_CONFLICT"
    assert result.program is None


@pytest.mark.usefixtures("db_mode")
def test_w2_historical_activation_ignores_future_active_and_replays_disabled_formal_version():
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramBinding, Major
    from app.modules.academic_affairs.services.academic_affairs_program_activation_service import (
        resolve_program_for_scope,
    )

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    major = Major(
        tenant_id=TID,
        college_id=963001,
        major_name=f"A-W2历史专业-{suffix}",
        code=f"AW2H-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    db.add(major)
    db.flush()
    old = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2历史方案-{suffix}",
        major_id=major.id,
        grade_year="2024",
        version=1,
        status="DISABLED",
    )
    current = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2未来方案-{suffix}",
        major_id=major.id,
        grade_year="2024",
        version=2,
        status="ENABLED",
    )
    db.add_all([old, current])
    db.flush()
    db.add_all([
        AaProgramBinding(
            tenant_id=TID,
            program_id=old.id,
            major_id=major.id,
            grade_year="2024",
            class_id=None,
            bound_at=datetime(2024, 9, 1),
            status="SUPERSEDED",
        ),
        AaProgramBinding(
            tenant_id=TID,
            program_id=current.id,
            major_id=major.id,
            grade_year="2024",
            class_id=None,
            bound_at=datetime(2027, 9, 1),
            status="ACTIVE",
        ),
    ])
    db.commit()

    historical = resolve_program_for_scope(
        db,
        tenant_id=TID,
        major_id=major.id,
        grade_year="2024",
        class_id=None,
        as_of=datetime(2026, 7, 1),
    )
    future = resolve_program_for_scope(
        db,
        tenant_id=TID,
        major_id=major.id,
        grade_year="2024",
        class_id=None,
        as_of=datetime(2028, 7, 1),
    )
    db.close()

    assert historical.status == "RESOLVED"
    assert historical.rule == "MAJOR_GRADE_HISTORICAL_EFFECTIVE"
    assert historical.program.id == old.id
    assert historical.program.status == "DISABLED"

    assert future.status == "RESOLVED"
    assert future.program.id == current.id


def test_w2_opening_task_and_student_resolution_share_canonical_activation_service():
    service_root = Path(__file__).parents[1] / "app" / "modules" / "academic_affairs" / "services"
    router_root = Path(__file__).parents[1] / "app" / "modules" / "academic_affairs" / "routers"
    task_source = (service_root / "academic_affairs_task_generation_service.py").read_text(encoding="utf-8")
    opening_source = (service_root / "academic_affairs_program_opening_projection_service.py").read_text(encoding="utf-8")
    student_source = (service_root / "student_program_resolution_service.py").read_text(encoding="utf-8")
    router_source = (router_root / "program_quality_router.py").read_text(encoding="utf-8")

    token = "academic_affairs_program_activation_service"
    resolver = "resolve_program_for_scope"
    for source in (task_source, opening_source, student_source):
        assert token in source
        assert resolver in source

    assert "academic_affairs_program_opening_projection_service" in router_source
    assert 'AaProgram.status == "ENABLED"' not in task_source

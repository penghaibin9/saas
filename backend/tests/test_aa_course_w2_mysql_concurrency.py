"""A-W2 Course Identity: MySQL version-linearity RED contracts.

AaCourse already has the canonical (tenant_id, course_code, version) unique key.
The service layer must serialize ENABLED -> v+1 creation so concurrent editors receive
one successor plus a stable business conflict, never a raw IntegrityError/500.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def _body(name: str):
    return SimpleNamespace(
        courseCode="",
        courseName=name,
        courseNameEn=None,
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=3,
        hoursTotal=48,
        hoursTheory=32,
        hoursPractice=16,
        hoursExperiment=0,
        hoursComputer=0,
        examMode="EXAM",
        ownerCollegeId=None,
        ownerTeacherId=None,
        isCore=True,
        description="A-W2 concurrent version contract",
        isAllMajor=True,
        applicableMajors=[],
        prerequisiteCodes=[],
    )


def _seed_enabled_course():
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8].upper()
    course = AaCourse(
        tenant_id=TID,
        course_code=f"AW{suffix[:6]}",
        course_name=f"A-W2课程-{suffix}",
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=3,
        hours_total=48,
        hours_theory=32,
        hours_practice=16,
        hours_experiment=0,
        hours_computer=0,
        exam_mode="EXAM",
        is_core=True,
        is_all_major=True,
        applicable_majors_json="[]",
        prerequisite_codes_json="[]",
        version=1,
        status="ENABLED",
    )
    db.add(course)
    db.commit()
    result = course.id, course.course_code
    db.close()
    return result


@pytest.mark.usefixtures("db_mode")
def test_w2_concurrent_enabled_course_edits_create_one_successor_and_one_business_conflict(monkeypatch):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaCourse
    from app.modules.academic_affairs.services import academic_affairs_course_service as service

    monkeypatch.setattr(service, "_tid", lambda: TID)
    source_id, code = _seed_enabled_course()
    barrier = Barrier(2)

    def edit(index: int):
        barrier.wait()
        try:
            result = service.update_course(source_id, None, _body(f"A-W2并发课程版本-{index}"))
            return "ok", result["courseId"]
        except AppException as exc:
            return "conflict", getattr(exc, "code", "")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, [1, 2]))

    kinds = [kind for kind, _value in results]
    assert kinds.count("ok") == 1
    assert kinds.count("conflict") == 1

    db = get_sessionmaker()()
    successors = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == TID,
        AaCourse.course_code == code,
        AaCourse.version == 2,
        AaCourse.prev_version_id == source_id,
        AaCourse.is_deleted.is_(False),
    )).all()
    db.close()

    assert len(successors) == 1
    assert successors[0].status == "DRAFT"


@pytest.mark.usefixtures("db_mode")
def test_w2_old_course_version_cannot_create_a_second_direct_successor(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_course_service as service

    monkeypatch.setattr(service, "_tid", lambda: TID)
    source_id, _code = _seed_enabled_course()

    first = service.update_course(source_id, None, _body("A-W2课程新版本-第一次"))
    assert first["version"] == 2

    with pytest.raises(AppException) as exc_info:
        service.update_course(source_id, None, _body("A-W2课程新版本-第二次"))
    assert getattr(exc_info.value, "code", "") in {"DATA_CONFLICT", "APPROVAL_VERSION_CONFLICT"}

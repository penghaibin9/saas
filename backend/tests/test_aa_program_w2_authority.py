"""A-W2 Course/Program authority RED contracts.

Scope is intentionally narrow:
- generic major+grade binding and class override are distinct active scopes;
- class override must belong to the same tenant/major/grade and a NORMAL class;
- a new program version must deep-copy the whole program-definition snapshot, including practice segments;
- one source version may have only one direct successor, and dirty historical forks fail closed on read.

These contracts exercise the real FastAPI/service/MySQL path through the normal ``db_mode`` fixture.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_binding_scope():
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, Major, SchoolClass

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    major = Major(
        tenant_id=TID,
        college_id=910001,
        major_name=f"A-W2专业-{suffix}",
        code=f"AW2-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    other_major = Major(
        tenant_id=TID,
        college_id=910001,
        major_name=f"A-W2其他专业-{suffix}",
        code=f"AW2-O-{suffix}",
        status="ACTIVE",
        enroll_status="ENROLLING",
    )
    db.add_all([major, other_major])
    db.flush()

    normal = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"A-W2正常班-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    wrong_major = SchoolClass(
        tenant_id=TID,
        major_id=other_major.id,
        class_name=f"A-W2跨专业班-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    wrong_grade = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"A-W2跨年级班-{suffix}",
        grade="2025",
        status="ACTIVE",
        class_status="NORMAL",
    )
    graduated = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"A-W2毕业班-{suffix}",
        grade="2026",
        status="ACTIVE",
        class_status="GRADUATED",
    )
    db.add_all([normal, wrong_major, wrong_grade, graduated])

    generic_program = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2通用方案-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=1,
        status="PUBLISHED",
    )
    class_program = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2班级特例方案-{suffix}",
        major_id=major.id,
        grade_year="2026",
        version=1,
        status="PUBLISHED",
    )
    db.add_all([generic_program, class_program])
    db.commit()
    result = {
        "major_id": major.id,
        "generic_program_id": generic_program.id,
        "class_program_id": class_program.id,
        "normal_class_id": normal.id,
        "wrong_major_class_id": wrong_major.id,
        "wrong_grade_class_id": wrong_grade.id,
        "graduated_class_id": graduated.id,
    }
    db.close()
    return result


@pytest.mark.usefixtures("db_mode")
def test_w2_generic_binding_and_class_override_coexist(client):
    from app.db.session import get_sessionmaker
    from app.models import AaProgramBinding

    seeded = _seed_binding_scope()
    hdr = _hdr(client)

    generic = client.post(
        f"{BASE}/programs/{seeded['generic_program_id']}/bind",
        headers=hdr,
        json={"gradeYear": "2026"},
    )
    assert generic.status_code == 200, generic.text

    override = client.post(
        f"{BASE}/programs/{seeded['class_program_id']}/bind",
        headers=hdr,
        json={"gradeYear": "2026", "classId": str(seeded["normal_class_id"])},
    )
    assert override.status_code == 200, override.text

    db = get_sessionmaker()()
    rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == TID,
        AaProgramBinding.major_id == seeded["major_id"],
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.status == "ACTIVE",
        AaProgramBinding.is_deleted.is_(False),
    )).all()
    db.close()

    generic_rows = [row for row in rows if row.class_id is None]
    class_rows = [row for row in rows if str(row.class_id or "") == str(seeded["normal_class_id"])]
    assert len(generic_rows) == 1, "class override must not supersede the major+grade fallback"
    assert len(class_rows) == 1, "class override must remain independently ACTIVE"
    assert generic_rows[0].program_id == seeded["generic_program_id"]
    assert class_rows[0].program_id == seeded["class_program_id"]


@pytest.mark.usefixtures("db_mode")
def test_w2_class_binding_rejects_cross_major_wrong_grade_and_non_normal_class(client):
    seeded = _seed_binding_scope()
    hdr = _hdr(client)

    for class_id in (
        seeded["wrong_major_class_id"],
        seeded["wrong_grade_class_id"],
        seeded["graduated_class_id"],
    ):
        response = client.post(
            f"{BASE}/programs/{seeded['class_program_id']}/bind",
            headers=hdr,
            json={"gradeYear": "2026", "classId": str(class_id)},
        )
        assert response.status_code == 409, response.text


def _seed_version_snapshot():
    from app.db.session import get_sessionmaker
    from app.models import (
        AaProgram,
        AaProgramCourse,
        AaProgramGraduationRequirement,
        AaProgramPracticeSegment,
    )

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    program = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2版本快照-{suffix}",
        major_id=920001,
        grade_year="2026",
        total_credits=10,
        requirement_json='{"creditStructure":[{"module":"专业核心","creditTarget":10}]}',
        version=3,
        status="PUBLISHED",
    )
    db.add(program)
    db.flush()
    db.add(AaProgramCourse(
        tenant_id=TID,
        program_id=program.id,
        course_id=930001,
        course_name="A-W2版本课程",
        open_term_no=2,
        module="专业核心",
        credit_snapshot=3,
    ))
    db.add(AaProgramGraduationRequirement(
        tenant_id=TID,
        program_id=program.id,
        category="ABILITY",
        content="完成A-W2毕业要求",
        sort_order=1,
        status="ACTIVE",
    ))
    db.add(AaProgramPracticeSegment(
        tenant_id=TID,
        program_id=program.id,
        segment_name="A-W2顶岗实习",
        segment_type="POST_INTERNSHIP",
        open_term_no=6,
        weeks=16,
        credit=7,
        org_mode="DISTRIBUTED",
        location="合作企业",
        assessment_mode="CHECK",
        sort_order=3,
        status="ACTIVE",
    ))
    db.commit()
    program_id = program.id
    db.close()
    return program_id


@pytest.mark.usefixtures("db_mode")
def test_w2_new_version_deep_copies_practice_definition_and_rejects_second_successor(client):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramPracticeSegment

    old_id = _seed_version_snapshot()
    hdr = _hdr(client)

    first = client.post(f"{BASE}/programs/{old_id}/new-version", headers=hdr)
    assert first.status_code == 200, first.text
    new_id = int(first.json()["data"]["programId"])

    db = get_sessionmaker()()
    new_program = db.get(AaProgram, new_id)
    segments = db.scalars(select(AaProgramPracticeSegment).where(
        AaProgramPracticeSegment.tenant_id == TID,
        AaProgramPracticeSegment.program_id == new_id,
        AaProgramPracticeSegment.is_deleted.is_(False),
        AaProgramPracticeSegment.status == "ACTIVE",
    )).all()
    db.close()

    assert new_program.prev_version_id == old_id
    assert new_program.version == 4
    assert len(segments) == 1, "new version must preserve formal practice-segment definition"
    assert segments[0].segment_name == "A-W2顶岗实习"
    assert float(segments[0].weeks) == 16
    assert float(segments[0].credit) == 7
    assert segments[0].org_mode == "DISTRIBUTED"

    second = client.post(f"{BASE}/programs/{old_id}/new-version", headers=hdr)
    assert second.status_code == 409, second.text


@pytest.mark.usefixtures("db_mode")
def test_w2_version_reader_fails_closed_on_historical_fork(client):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    root = AaProgram(
        tenant_id=TID,
        program_name=f"A-W2脏版本链-{suffix}",
        major_id=940001,
        grade_year="2026",
        version=1,
        status="PUBLISHED",
    )
    db.add(root)
    db.flush()
    db.add_all([
        AaProgram(
            tenant_id=TID,
            program_name=root.program_name,
            major_id=root.major_id,
            grade_year=root.grade_year,
            version=2,
            prev_version_id=root.id,
            status="DRAFT",
        ),
        AaProgram(
            tenant_id=TID,
            program_name=root.program_name,
            major_id=root.major_id,
            grade_year=root.grade_year,
            version=2,
            prev_version_id=root.id,
            status="DRAFT",
        ),
    ])
    db.commit()
    root_id = root.id
    db.close()

    response = client.get(f"{BASE}/programs/{root_id}/versions", headers=_hdr(client))
    assert response.status_code == 409, response.text

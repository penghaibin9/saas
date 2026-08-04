"""P0-1 先修课程必须通过真实选课 API 按稳定 courseCode 校验。"""
from __future__ import annotations

import itertools
import json

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001
_SEQ = itertools.count(1)


def _hdr(client, login_name="school_admin01"):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(student_no):
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}",
        "realName": "先修测试学生",
        "studentNo": student_no,
        "userType": "STUDENT",
        "tenantId": str(TID),
        "activeContextId": "ctx",
        "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })}


def _seed(db_mode, prerequisites_json, passed_codes=()):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AcademicGrade,
        AcademicStudent,
        College,
        Major,
        SchoolClass,
        StudentProfile,
    )

    try:
        parsed = json.loads(prerequisites_json)
        prerequisite_codes = parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        prerequisite_codes = []

    n = next(_SEQ)
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name=f"先修学院{n}", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name=f"先修专业{n}",
        status="ACTIVE",
    )
    db.add(major); db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"先修班{n}",
        grade="2031",
        status="ACTIVE",
    )
    db.add(klass); db.flush()
    student_no = f"PREREQ{n:04d}"
    student = StudentProfile(
        tenant_id=TID,
        student_no=student_no,
        real_name="先修测试学生",
        college_id=college.id,
        major_id=major.id,
        class_id=klass.id,
        grade="2031",
        student_status="NORMAL",
        status="ACTIVE",
    )
    db.add(student); db.flush()

    # 同一课程代码保留两个历史版本，确保校验不依赖具体版本行。
    prereq_rows = []
    for code in sorted(set(prerequisite_codes) | set(passed_codes)):
        old = AaCourse(
            tenant_id=TID,
            course_code=code,
            course_name=f"{code}旧版本",
            credit=2,
            version=1,
            status="DISABLED",
        )
        current = AaCourse(
            tenant_id=TID,
            course_code=code,
            course_name=f"{code}新版本",
            credit=2,
            version=2,
            status="ENABLED",
        )
        db.add_all([old, current]); db.flush()
        prereq_rows.append(current)

    target = AaCourse(
        tenant_id=TID,
        course_code=f"TARGET{n:04d}",
        course_name="目标课程",
        credit=3,
        version=1,
        status="ENABLED",
        prerequisite_codes_json=prerequisites_json,
    )
    db.add(target); db.flush()

    if passed_codes:
        acad = AcademicStudent(
            tenant_id=TID,
            student_id=student.id,
            student_no=student_no,
            name="先修测试学生",
            class_name=klass.class_name,
            college_name=college.college_name,
        )
        db.add(acad); db.flush()
        by_code = {row.course_code: row for row in prereq_rows}
        for code in passed_codes:
            course = by_code[code]
            db.add(AcademicGrade(
                tenant_id=TID,
                acad_student_id=acad.id,
                course_id=course.id,
                course_code=code,
                course_version=course.version,
                course_name=course.course_name,
                credit_value=2,
                attempt_no=1,
                score=80,
                pass_status="PASSED",
                source="PUBLISH",
                record_status="ACTIVE",
                effective_policy_code="LEGACY_LATEST_ATTEMPT_V1",
                effective_policy_version=1,
                effective_attempt_strategy="LATEST_ATTEMPT",
                pass_line_snapshot=60,
            ))

    db.commit()
    result = {"studentNo": student_no, "targetId": target.id, "n": n}
    db.close()
    return result


def _open_course(client, admin, target_id, n):
    term = client.post(f"{BASE}/terms", headers=admin, json={
        "yearCode": "2031-2032",
        "termNo": 1,
        "termName": f"先修测试学期{n}",
    })
    assert term.status_code == 200, term.text
    term_id = term.json()["data"]["termId"]

    batch = client.post(f"{BASE}/selection/batches", headers=admin, json={
        "batchName": f"先修真实API批次{n}",
        "termId": str(term_id),
    })
    assert batch.status_code == 200, batch.text
    batch_id = batch.json()["data"]["batchId"]

    course = client.post(
        f"{BASE}/selection/batches/{batch_id}/courses",
        headers=admin,
        json={"courseId": str(target_id), "capacity": 20, "minCapacity": 1},
    )
    assert course.status_code == 200, course.text
    selection_course_id = course.json()["data"]["selectionCourseId"]
    assert client.post(f"{BASE}/selection/batches/{batch_id}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{batch_id}/open", headers=admin).status_code == 200
    return selection_course_id


def _enroll(client, seeded):
    admin = _hdr(client)
    selection_course_id = _open_course(client, admin, seeded["targetId"], seeded["n"])
    return client.post(
        f"{BASE}/selection/student/enroll",
        headers=_stu_token(seeded["studentNo"]),
        json={"selectionCourseId": str(selection_course_id)},
    )


def test_no_prerequisite_allows_enrollment(client, db_mode):
    response = _enroll(client, _seed(db_mode, "[]"))
    assert response.status_code == 200, response.text


def test_partial_prerequisite_rejects_and_names_missing_code(client, db_mode):
    response = _enroll(client, _seed(db_mode, '["PRE_A", "PRE_B"]', ["PRE_A"]))
    assert response.status_code in {400, 409}, response.text
    assert "PRE_B" in response.text


def test_passed_old_course_version_with_same_code_is_accepted(client, db_mode):
    response = _enroll(client, _seed(db_mode, '["PRE_A"]', ["PRE_A"]))
    assert response.status_code == 200, response.text


def test_corrupt_prerequisite_json_fails_closed(client, db_mode):
    response = _enroll(client, _seed(db_mode, "{broken"))
    assert response.status_code == 409, response.text
    assert "先修" in response.text and "JSON" in response.text

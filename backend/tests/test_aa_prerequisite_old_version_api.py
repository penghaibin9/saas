"""P0-1 补充证据：通过成绩来自课程库旧版本时仍按稳定 courseCode 满足先修。"""
from tests.test_aa_prerequisite_api_real import TID, _enroll, _seed


def test_old_course_version_passes_same_code_prerequisite_via_api(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AcademicGrade

    seeded = _seed(db_mode, '["PRE_A"]', ["PRE_A"])
    db = get_sessionmaker()()
    try:
        old_course = db.query(AaCourse).filter(
            AaCourse.tenant_id == TID,
            AaCourse.course_code == "PRE_A",
            AaCourse.version == 1,
            AaCourse.is_deleted.is_(False),
        ).one()
        grade = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.course_code == "PRE_A",
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).one()
        grade.course_id = old_course.id
        grade.course_version = 1
        db.commit()
    finally:
        db.close()

    response = _enroll(client, seeded)
    assert response.status_code == 200, response.text

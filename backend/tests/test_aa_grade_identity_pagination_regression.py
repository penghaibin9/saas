"""按正式启动后的课程代码优先规则核验分页、跨学期和成绩统计。"""
import pytest

TID = 1000000000000000001


def test_fail_list_pages_ordinary_rows_and_preserves_attempt_arbitration(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services import academic_affairs_grade_service as service
    user = {'tenantId': str(TID), 'userId': '81003', 'userType': 'TEACHER', 'currentRoleCode': 'ACADEMIC_ADMIN'}
    set_tenant({'tenantId': str(TID)}); set_current_user(user)
    with get_sessionmaker()() as db:
        student = AcademicStudent(tenant_id=TID, student_id=db_mode['student'], name='虚构分页学生')
        db.add(student); db.flush()
        student_id = student.id
        def grade(code, attempt, score):
            return AcademicGrade(tenant_id=TID, acad_student_id=student_id, course_code=code, course_id=500+int(code[-2:]), course_version=1, attempt_no=attempt,
                                 course_name=code, credit_value=2, score=score, pass_status='PASSED' if score>=60 else 'FAILED', record_status='ACTIVE', source='PUBLISH', term='2026-1',
                                 effective_attempt_strategy='LATEST_ATTEMPT', gpa_point=0, gpa_policy_code='FROZEN_TEST', gpa_policy_version=1)
        db.add_all([grade(f'COURSE{i:02}', 1, 50) for i in range(6)])
        db.commit()
        rows,total=service.fail_list(user,term='2026-1',page=2,page_size=2)
        assert total==6 and len(rows)==2
        assert [r['courseCode'] for r in rows]==['COURSE03','COURSE02']
        db.add(grade('RENAMED05',2,80));db.commit()
        rows,total=service.fail_list(user,term='2026-1',page=1,page_size=20)
        assert total==6 and 'COURSE05' in {r['courseCode'] for r in rows}
        analysis = service.grade_analysis(user, term='2026-1')
        assert analysis['total'] == 7 and analysis['passRate'] == round(1 / 7, 3)
        db.add(grade('COURSE05',3,80));db.commit()
        rows,total=service.fail_list(user,term='2026-1',page=1,page_size=20)
        assert total==5 and 'COURSE05' not in {r['courseCode'] for r in rows}



@pytest.mark.parametrize('first_id,second_id,first_code,second_code,first_version,second_version,last_score,expected_fails', [
    (901, 901, 'ORIGINAL', 'RENAMED', 1, 2, 80, 1),
    (901, 901, None, 'RENAMED', 1, 2, 80, 1),
    (901, 901, 'ORIGINAL', None, 1, 2, 80, 1),
    (901, 902, 'SHARED', 'SHARED', 1, 1, 80, 0),
    (None, None, 'LEGACY', 'LEGACY', 1, 1, 80, 0),
    (None, None, 'LEGACY', 'LEGACY', 1, 2, 80, 0),
    (None, None, None, None, 1, 1, 80, 1),
    (901, 901, 'ORIGINAL', 'RENAMED', 1, 2, None, 1),
    (901, 902, 'SHARED', 'SHARED', 1, 2, None, 0),
    (901, 901, None, None, 1, 2, 80, 0),
])
def test_fail_list_uses_canonical_course_identity(db_mode, first_id, second_id, first_code, second_code,
                                                  first_version, second_version, last_score, expected_fails):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services import academic_affairs_grade_service as service
    user = {'tenantId': str(TID), 'userId': '81003', 'userType': 'TEACHER', 'currentRoleCode': 'ACADEMIC_ADMIN'}
    set_tenant({'tenantId': str(TID)}); set_current_user(user)
    try:
        with get_sessionmaker()() as db:
            student = AcademicStudent(tenant_id=TID, student_id=db_mode['student'], name='课程身份回归学生')
            db.add(student); db.flush()
            for attempt, (course_id, code, version, score) in enumerate((
                (first_id, first_code, first_version, 50), (second_id, second_code, second_version, last_score),
            ), 1):
                db.add(AcademicGrade(tenant_id=TID, acad_student_id=student.id, course_id=course_id,
                    course_code=code, course_version=version, attempt_no=attempt, course_name='同名回归课程',
                    credit_value=2, score=score, pass_status='PENDING' if score is None else 'PASSED' if score >= 60 else 'FAILED',
                    record_status='ACTIVE', source='PUBLISH', term='2026-1',
                    effective_attempt_strategy='LATEST_ATTEMPT', gpa_point=0, gpa_policy_code='FROZEN_TEST', gpa_policy_version=1))
            db.commit()
        rows, total = service.fail_list(user, term='2026-1', page=1, page_size=1)
        assert total == expected_fails and len(rows) == expected_fails
        if rows:
            assert rows[0]['score'] == 50
    finally:
        set_current_user(None); set_tenant(None)

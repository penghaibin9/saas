"""本人候选在有效成绩判定后分页，搜索和深链不能改变归属。"""
from sqlalchemy import select


def test_candidate_pages_keep_effective_policy_search_and_student_scope(db_mode, client):
    from tests.test_aa_student_submit_concurrency import _seed_recheck_target, _session, TID
    from tests.test_aa_mobile import _stu_token
    from app.models import AcademicGrade, AcademicStudent, StudentProfile

    student_id, student_no, original_id = _seed_recheck_target()
    with _session() as db:
        acad = db.scalar(select(AcademicStudent).where(AcademicStudent.student_id == student_id))
        original = db.get(AcademicGrade, original_id)
        original.effective_attempt_strategy = 'LATEST_ATTEMPT'
        original.course_version = 1
        original.attempt_no = 1
        # 同一课程后一次已经通过，旧挂科不应重返候选。
        db.add(AcademicGrade(tenant_id=TID, acad_student_id=acad.id, course_id=original.course_id,
            course_code=original.course_code, course_name=original.course_name, course_version=1,
            attempt_no=2, term='2026-2027-1', credit_value=2, score=80, pass_status='PASSED',
            source='PUBLISH', record_status='ACTIVE', effective_attempt_strategy='LATEST_ATTEMPT'))
        rows = []
        for i in range(25):
            row = AcademicGrade(tenant_id=TID, acad_student_id=acad.id, course_id=992000+i,
                course_code=f'PAGING{i:03}', course_name=f'候选课程{i:03}', course_version=1,
                attempt_no=1, term='2026-2027-1', credit_value=2, score=40,
                pass_status='FAILED', source='PUBLISH', record_status='ACTIVE',
                effective_attempt_strategy='LATEST_ATTEMPT')
            db.add(row); rows.append(row)
        other = StudentProfile(tenant_id=TID, student_no='PAGING_OTHER', real_name='其他测试学生', status='ACTIVE')
        db.add(other); db.flush()
        other_id = other.id
        target = str(rows[-1].id)
        db.commit()
    headers = _stu_token('复查并发学生', student_no, student_id)
    path = '/api/v1/mobile/academic/makeup/options'
    def read(params, auth=headers):
        response = client.get(path, params=params, headers=auth)
        assert response.status_code == 200, response.text
        return response.json()['data']
    first = read({'page': 1, 'pageSize': 20})
    second = read({'page': 2, 'pageSize': 20})
    assert len(first['retakeOptions']) == 20
    assert len(second['retakeOptions']) == 5
    assert first['retakeTotal'] == 25
    assert first['retakePagination']['hasMore'] is True
    assert second['retakePagination']['hasMore'] is False
    assert not ({r['gradeId'] for r in first['retakeOptions']} & {r['gradeId'] for r in second['retakeOptions']})
    assert len(read({'keyword': 'PAGING024'})['retakeOptions']) == 1
    assert [r['gradeId'] for r in read({'gradeId': target})['retakeOptions']] == [target]
    assert read({'gradeId': original_id})['retakeOptions'] == []
    other_headers = _stu_token('其他测试学生', 'PAGING_OTHER', other_id)
    assert read({'gradeId': target, 'studentId': student_id}, other_headers)['retakeOptions'] == []

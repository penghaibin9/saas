from datetime import datetime, timedelta
from sqlalchemy import event

TID = 1000000000000000001
BASE = '/api/v1/academic-affairs'


def admin_headers(client):
    from app.core.security import create_access_token
    from app.db.session import get_engine, get_sessionmaker
    from app.services.auth_service_db import _claims, _role_contexts
    from tests.support_academic_review_identity import _ensure_review_account
    assert 'test' in (get_engine().url.database or '').lower()
    with get_sessionmaker()() as db:
        user = _ensure_review_account(db, login_name='flow_read_review', real_name='读取回归教务员',
            role_code='ACADEMIC_ADMIN', permissions=('academicAffairs.registration.view',
                'academicAffairs.quality.rectification.view', 'academicAffairs.schedule.view', 'academicAffairs.textbook.view'))
        db.commit()
        contexts = _role_contexts(db, user)
        context = next(item for item in contexts if item['roleCode'] == 'ACADEMIC_ADMIN')
        token = create_access_token(_claims(db, user, context, contexts, 'PC'))
    return {'Authorization': f'Bearer {token}'}


def test_rectification_filter_precedes_pagination_and_keeps_tenant(client, db_mode):
    from app.models import AaQualityRectification
    from app.db.session import get_sessionmaker, get_engine
    with get_sessionmaker()() as db:
        for index, status in enumerate(['PENDING', 'CLOSED', 'IN_PROGRESS', 'CLOSED', 'SUBMITTED']):
            db.add(AaQualityRectification(tenant_id=TID, title=f'整改{index}', requirement='测试整改要求', status=status, deadline=datetime.utcnow()-timedelta(days=1)))
        db.add(AaQualityRectification(tenant_id=TID+1, title='外校整改', requirement='范围拒绝', status='PENDING'))
        db.commit()
    statements = []
    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith('SELECT') and 't_aa_quality_rectification' in statement:
            statements.append(statement.upper())
    engine = get_engine()
    headers = admin_headers(client)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        pages = [client.get(f'{BASE}/quality/rectifications', headers=headers, params={'status': 'NOT_CLOSED', 'page': n, 'pageSize': 2}).json()['data'] for n in (1, 2)]
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert [p['total'] for p in pages] == [3, 3]
    rows = [r for p in pages for r in p['items']]
    assert len(rows) == 3 and all(r['status'] != 'CLOSED' for r in rows)
    assert all(r['title'] != '外校整改' for r in rows)
    assert any('LIMIT' in s for s in statements)
    assert all('LIMIT' in s for s in statements if 'COUNT(' not in s)


def test_registration_batch_counts_are_real_records_not_candidates(client, db_mode):
    from app.models import AaRegistrationBatch, AaRegistration, StudentProfile
    from app.db.session import get_sessionmaker
    with get_sessionmaker()() as db:
        batch = AaRegistrationBatch(tenant_id=TID, batch_name='流程整改汇总', register_type='ENROLL', status='OPEN')
        db.add(batch); db.flush()
        batch_id = str(batch.id)
        for index, status in enumerate(['REGISTERED', 'PENDING_REGISTER', 'REGISTERED']):
            student = StudentProfile(tenant_id=TID, student_no=f'FLOW12-{index}', real_name=f'虚构学生{index}', status='ACTIVE')
            db.add(student); db.flush()
            db.add(AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=student.id, status=status, is_deleted=index==2))
        db.add(AaRegistration(tenant_id=TID+1, batch_id=batch.id, student_id=123, status='REGISTERED'))
        db.commit()
    result = client.get(f'{BASE}/registration-batches', headers=admin_headers(client), params={'keyword': batch_id}).json()['data']
    assert result['total'] == 1
    row = result['items'][0]
    assert row['registrationCount'] == 2 and row['registeredCount'] == 1
    assert row['termId'] is None and row['termName'] is None


def test_registration_batch_counts_match_ledger_with_invalid_student_links(client, db_mode):
    from sqlalchemy import func, select
    from app.models import AaRegistrationBatch, AaRegistration, StudentProfile
    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        batch = AaRegistrationBatch(tenant_id=TID, batch_name='注册名单同口径验收', register_type='ENROLL', status='OPEN')
        students = [
            StudentProfile(tenant_id=TID, student_no='FLOW12-LINK-OK', real_name='虚构已注册学生', status='ACTIVE'),
            StudentProfile(tenant_id=TID, student_no='FLOW12-LINK-PENDING', real_name='虚构待注册学生', status='ACTIVE'),
            StudentProfile(tenant_id=TID, student_no='FLOW12-LINK-DELETED', real_name='虚构已删除学生', status='ACTIVE', is_deleted=True),
            StudentProfile(tenant_id=TID + 1, student_no='FLOW12-LINK-FOREIGN', real_name='虚构其他学校学生', status='ACTIVE'),
        ]
        db.add_all([batch, *students]); db.flush()
        batch_id = str(batch.id)
        missing_id = int(db.scalar(select(func.max(StudentProfile.id))) or 0) + 10000
        expected_ids = {str(student.id) for student in students[:2]}
        db.add_all([
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=students[0].id, status='REGISTERED'),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=students[1].id, status='PENDING_REGISTER'),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=students[2].id, status='REGISTERED'),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=students[3].id, status='REGISTERED'),
            AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=missing_id, status='REGISTERED'),
            AaRegistration(tenant_id=TID + 1, batch_id=batch.id, student_id=students[0].id, status='REGISTERED'),
        ])
        db.commit()
    headers = admin_headers(client)
    summary_response = client.get(f'{BASE}/registration-batches', headers=headers, params={'pageSize': 100})
    ledger_response = client.get(f'{BASE}/registration-batches/{batch_id}/registrations', headers=headers)
    assert summary_response.status_code == ledger_response.status_code == 200
    summary = next(row for row in summary_response.json()['data']['items'] if row['batchId'] == batch_id)
    ledger = ledger_response.json()['data']
    assert summary['registrationCount'] == ledger['total'] == 2
    assert summary['registeredCount'] == sum(row['status'] == 'REGISTERED' for row in ledger['items']) == 1
    assert {row['studentId'] for row in ledger['items']} == expected_ids


def test_fail_list_pages_ordinary_rows_and_preserves_attempt_arbitration(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker, get_engine
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
        statements=[]
        def capture(_c,_cu,statement,_p,_co,_m): statements.append(statement.upper())
        engine=get_engine();event.listen(engine,'before_cursor_execute',capture)
        try:
            rows,total=service.fail_list(user,term='2026-1',page=2,page_size=2)
        finally: event.remove(engine,'before_cursor_execute',capture)
        assert total==6 and len(rows)==2
        assert [r['courseCode'] for r in rows]==['COURSE03','COURSE02']
        assert any('LIMIT' in s and 'T_ACAD_GRADE' in s for s in statements)
        db.add(grade('RENAMED05',2,80));db.commit()
        rows,total=service.fail_list(user,term='2026-1',page=1,page_size=20)
        assert total==6 and 'COURSE05' in {r['courseCode'] for r in rows}
        db.add(grade('COURSE05',3,80));db.commit()
        rows,total=service.fail_list(user,term='2026-1',page=1,page_size=20)
        assert total==5 and 'COURSE05' not in {r['courseCode'] for r in rows}


def test_schedule_list_version_belongs_only_to_current_matching_scope(client, db_mode):
    from app.models import AaScheduleBatch, AaScheduleScopeHead
    from app.db.session import get_sessionmaker
    with get_sessionmaker()() as db:
        batches = [AaScheduleBatch(tenant_id=TID, term_id=101, batch_name=f'版本核对{i}', status=status) for i,status in enumerate(['PUBLISHED','DRAFT','SUPERSEDED'])]
        db.add_all(batches);db.flush()
        current_id = str(batches[0].id)
        db.add(AaScheduleScopeHead(tenant_id=TID,term_id=101,scope_type='SCHOOL',scope_id=0,active_batch_id=batches[0].id,version=3))
        db.commit()
    response=client.get(f'{BASE}/schedule-batches',headers=admin_headers(client),params={'termId':101}).json()
    assert response['code']==0,response
    rows=response['data']['items']
    assert len(rows)==3
    assert next(r for r in rows if r['batchId']==current_id)['publishedVersion']==3
    assert all(r['publishedVersion'] is None for r in rows if r['batchId']!=current_id)


def test_fail_remedies_require_exact_same_student_and_tenant_source(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent, AcademicMakeup, AaRetakeApply
    from app.modules.academic_affairs.services.academic_affairs_grade_service import _fail_remedies

    set_tenant({'tenantId': str(TID)})
    with get_sessionmaker()() as db:
        student = AcademicStudent(tenant_id=TID, student_id=db_mode['student'], name='虚构补救学生')
        db.add(student); db.flush()
        grade = AcademicGrade(tenant_id=TID, acad_student_id=student.id, course_name='补救核对课程', score=40, pass_status='FAILED')
        db.add(grade); db.flush()
        common = dict(tenant_id=TID, acad_student_id=student.id, origin_grade_id=grade.id, course_name=grade.course_name)
        makeup = AcademicMakeup(**common, status='PENDING_EXAM', record_status='ACTIVE')
        retake = AaRetakeApply(**common, student_id=db_mode['student'], status='APPROVED')
        db.add_all([makeup, retake]); db.flush()
        # Larger ids must not let a foreign, deleted, void or mismatched record win.
        db.add_all([
            AcademicMakeup(**{**common, 'tenant_id': TID+1}, status='FINISHED'),
            AcademicMakeup(**{**common, 'acad_student_id': student.id+1}, status='FINISHED'),
            AcademicMakeup(**common, status='FINISHED', is_deleted=True),
            AcademicMakeup(**common, status='FINISHED', record_status='VOID'),
            AcademicMakeup(**{**common, 'origin_grade_id': None}, status='FINISHED'),
            AaRetakeApply(**{**common, 'tenant_id': TID+1}, student_id=db_mode['student'], status='FINISHED'),
            AaRetakeApply(**common, student_id=db_mode['student'], status='FINISHED', is_deleted=True),
        ]); db.flush()
        result = _fail_remedies(db, [grade.id])
        assert [(r['kind'], r['id'], r['status']) for r in result[grade.id]] == [
            ('MAKEUP', str(makeup.id), 'PENDING_EXAM'), ('RETAKE', str(retake.id), 'APPROVED'),
        ]
        assert _fail_remedies(db, []) == {}
        assert _fail_remedies(db, [grade.id+100000]) == {}


def test_textbook_officer_name_never_comes_from_other_tenant_or_deleted_account(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTextbookSelection, User
    with get_sessionmaker()() as db:
        db.add_all([
            User(tenant_id=TID, login_name='flow_officer', real_name='本校教材负责人', user_type='TEACHER', password_hash='disabled-test-account', status='DISABLED'),
            User(tenant_id=TID+1, login_name='flow_officer', real_name='外校同账号', user_type='TEACHER', password_hash='disabled-test-account', status='DISABLED'),
            User(tenant_id=TID, login_name='flow_deleted', real_name='已删除账号', user_type='TEACHER', password_hash='disabled-test-account', status='DISABLED', is_deleted=True),
        ])
        db.add_all([AaTextbookSelection(tenant_id=TID, task_id=1, textbook_id=1, officer_key=key) for key in ['flow_officer', 'flow_deleted', 'flow_missing']])
        db.add(AaTextbookSelection(tenant_id=TID+1, task_id=1, textbook_id=1, officer_key='flow_officer'))
        db.commit()
    response = client.get(f'{BASE}/textbooks/selections', headers=admin_headers(client)).json()
    assert response['code'] == 0, response
    result = response['data']
    assert result['total'] == 3
    names = {row['officerKey']: row['officerName'] for row in result['items']}
    assert names == {'flow_officer': '本校教材负责人', 'flow_deleted': None, 'flow_missing': None}


def test_textbook_officer_db_id_alias_is_unique_and_tenant_scoped(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTextbookSelection, User

    with get_sessionmaker()() as db:
        own = User(tenant_id=TID, login_name='flow_db_officer', real_name='本校别名负责人', user_type='TEACHER', password_hash='disabled-test-account')
        foreign = User(tenant_id=TID + 1, login_name='flow_foreign_db_officer', real_name='外校负责人不可读取', user_type='TEACHER', password_hash='disabled-test-account')
        db.add_all([own, foreign]); db.flush()
        own_key, foreign_key = f'db-{own.id}', f'db-{foreign.id}'
        db.add(User(tenant_id=TID + 1, login_name=own_key, real_name='外校同别名不可干扰', user_type='TEACHER', password_hash='disabled-test-account'))
        db.add_all([AaTextbookSelection(tenant_id=TID, task_id=1, textbook_id=1, officer_key=key) for key in (own_key, foreign_key)])
        db.commit()
    headers = admin_headers(client)
    def read():
        response = client.get(f'{BASE}/textbooks/selections', headers=headers)
        assert response.status_code == 200, response.text
        return {row['officerKey']: row for row in response.json()['data']['items']}
    rows = read()
    assert rows[own_key]['officerName'] == '本校别名负责人'
    assert rows[own_key]['officerLoginName'] == 'flow_db_officer'
    assert rows[foreign_key]['officerName'] is None
    with get_sessionmaker()() as db:
        collision = User(tenant_id=TID, login_name=own_key, real_name='本校另一账号', user_type='TEACHER', password_hash='disabled-test-account')
        db.add(collision); db.commit(); collision_id = collision.id
    ambiguous = read()[own_key]
    assert ambiguous['officerName'] is None and ambiguous['officerLoginName'] is None
    with get_sessionmaker()() as db:
        db.get(User, collision_id).is_deleted = True
        db.commit()
    assert read()[own_key]['officerName'] == '本校别名负责人'

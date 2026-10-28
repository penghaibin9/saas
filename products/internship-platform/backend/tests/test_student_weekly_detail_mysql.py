"""本人周报详情：真实身份、历史附件、版本评分和扫描拒绝。"""
from uuid import uuid4
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.main import app
from app.models import InternshipBatch, InternshipRecord, Role, StudentAccountLink, TeacherStudentScope, User, UserRole, WeeklyReport
from test_yiyang_write_flows_mysql import flow, context, login, png_bytes, seed_flow, upload, PASSWORD

MOBILE = '/api/v1/mobile/internship'
PORTAL = '/api/v1/portal/internship'
STAFF = '/api/v1/internship'
TEACHER_MOBILE = '/api/v1/mobile/teacher/internship/context'


@pytest.mark.parametrize('kind', ['DAILY', 'WEEKLY', 'MONTHLY', 'SUMMARY'])
def test_report_missing_type_scope_reminder_conflict_and_original_count(flow, kind):
    from app.models import InternshipAuditTrail
    with get_sessionmaker()() as db:
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {'weeklyReport': {'requiredCount': 1}, 'processReport': {
            'dailyRequiredCount': 1, 'monthlyRequiredCount': 1, 'summaryRequiredCount': 1}}
        db.commit()
    foreign = seed_flow()
    path = STAFF + '/report-obligations'
    params = {'batchId': flow['batchId'], 'reportType': kind, 'missingOnly': True, 'pageSize': 1}
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school, login(foreign, 'INTERN_MENTOR') as outsider:
        assert student.get(path, params=params).status_code == 403
        assert outsider.get(path, params=params).status_code in (403, 404)
        before = teacher.get(path, params=params)
        assert before.status_code == 200 and before.json()['data']['total'] == 1, before.text
        assert before.json()['data']['items'][0][kind.lower()]['missing'] == 1
        assert teacher.get(path, params={**params, 'missingOnly': False, 'submittedOnly': True}).json()['data']['total'] == 0
        reminder = path + '/' + flow['recordId'] + '/remind'
        assert student.post(reminder, params=params, json={'reportType': kind}).status_code == 403
        assert outsider.post(reminder, params=params, json={'reportType': kind}).status_code in (403, 404)
        first = teacher.post(reminder, params=params, json={'reportType': kind})
        assert first.status_code == 200 and first.json()['data']['queued'], first.text
        duplicate = teacher.post(reminder, params=params, json={'reportType': kind})
        assert duplicate.status_code == 400 and duplicate.json()['bizCode'] == 'DATA_CONFLICT', duplicate.text
        route = '/context/weekly-reports' if kind == 'WEEKLY' else '/context/reports'
        payload = body(flow) if kind == 'WEEKLY' else process_body(flow, kind)
        created = student.post(PORTAL + route, json=payload)
        assert created.status_code == 200, created.text
        row = created.json()['data']
        submitted = teacher.get(path, params={**params, 'missingOnly': False, 'submittedOnly': True}).json()['data']
        assert submitted['total'] == 1 and submitted['items'][0]['recordId'] == flow['recordId']
        review = STAFF + ('/reports/' if kind == 'WEEKLY' else '/process-reports/') + row['id'] + '/review'
        returned = teacher.post(review, json={'batchId': flow['batchId'], 'expectedVersion': row['version'], 'action': 'RETURN', 'comment': '请补充岗位工作成果说明'})
        assert returned.status_code == 200, returned.text
        for actor in (teacher, school):
            after = actor.get(path, params=params)
            assert after.status_code == 200 and after.json()['data']['total'] == 0, after.text
            all_rows = actor.get(path, params={**params, 'missingOnly': False}).json()['data']
            assert all_rows['items'][0][kind.lower()] == {'required': 1, 'submitted': 1, 'approved': 0, 'missing': 0, 'configured': True}
        detail = student.get(PORTAL + route + '/' + row['id'], params=context(flow)).json()['data']
        payload['expectedVersion'] = detail['version']
        again = student.post(PORTAL + route, json=payload)
        assert again.status_code == 200 and again.json()['data']['id'] == row['id'], again.text
        metric = teacher.get(path, params={**params, 'missingOnly': False}).json()['data']['items'][0][kind.lower()]
        assert metric['submitted'] == 1 and metric['missing'] == 0
        complete = teacher.post(reminder, params=params, json={'reportType': kind})
        assert complete.status_code == 400 and complete.json()['bizCode'] == 'DATA_CONFLICT', complete.text
        assert teacher.get(path, params={**params, 'reportType': 'INVALID'}).status_code == 400
        with get_sessionmaker()() as db:
            audits = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(flow['tenantId']), InternshipAuditTrail.target_type == 'REPORT_OBLIGATION')).all()
            assert len(audits) == 1 and audits[0].action == 'REMIND_' + kind


def test_report_obligation_readonly_and_other_mentor_do_not_gain_review_or_student_scope(flow):
    with get_sessionmaker()() as db:
        tid = int(flow['tenantId'])
        for code, name in [('COUNSELOR', 'counselor'), ('INTERN_MENTOR', 'other_mentor')]:
            role = db.scalar(select(Role).where(Role.tenant_id == tid, Role.role_code == code))
            account = User(tenant_id=tid, login_name=name, real_name='报告合成范围检查', password_hash=hash_password(PASSWORD),
                           user_type='TEACHER', status='ACTIVE', credential_version=0, must_change_password=False)
            db.add(account); db.flush()
            db.add(UserRole(tenant_id=tid, user_id=account.id, role_id=role.id, status='ACTIVE'))
            if code == 'COUNSELOR':
                db.add(TeacherStudentScope(tenant_id=tid, teacher_key='db-' + str(account.id), user_id=account.id, role_code=code,
                                          scope_type='STUDENT', ref_id=int(flow['studentId']), ref_value='S0', status='ACTIVE'))
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {'processReport': {'dailyRequiredCount': 1}}
        db.commit()
    path = STAFF + '/report-obligations'
    params = {'batchId': flow['batchId'], 'reportType': 'DAILY', 'missingOnly': True}
    with login(flow, 'COUNSELOR') as reader, login(flow, 'OTHER_MENTOR') as other:
        visible = reader.get(path, params=params)
        assert visible.status_code == 200 and visible.json()['data']['total'] == 1, visible.text
        assert reader.post(path + '/' + flow['recordId'] + '/remind', params=params, json={'reportType': 'DAILY'}).status_code == 403
        denied = other.get(path, params=params)
        assert denied.status_code == 404 or (denied.status_code == 200 and denied.json()['data']['total'] == 0), denied.text
        assert other.post(path + '/' + flow['recordId'] + '/remind', params=params, json={'reportType': 'DAILY'}).status_code in (403, 404)


def test_report_obligation_missing_account_refuses_only_that_student_and_creates_no_event(flow):
    from app.models import InternshipAuditTrail, StudentProfile
    with get_sessionmaker()() as db:
        tid = int(flow['tenantId'])
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {'processReport': {'dailyRequiredCount': 1}}
        student = StudentProfile(tenant_id=tid, student_no='UNBOUND_REPORT', real_name='报告未绑定合成学生', current_stage='ENROLLED', student_status='NORMAL', status='ACTIVE')
        db.add(student); db.flush()
        record = InternshipRecord(tenant_id=tid, student_id=student.id, batch_id=batch.id, status='READY', advisor_user_id=flow['users']['INTERN_MENTOR'])
        db.add(record); db.flush(); missing_id = str(record.id); db.commit()
    path = STAFF + '/report-obligations'
    params = {'batchId': flow['batchId'], 'reportType': 'DAILY', 'missingOnly': True}
    with login(flow, 'INTERN_MENTOR') as teacher:
        data = teacher.get(path, params=params).json()['data']
        assert data['total'] == 2 and {row['recordId'] for row in data['items']} == {flow['recordId'], missing_id}
        denied = teacher.post(path + '/' + missing_id + '/remind', params=params, json={'reportType': 'DAILY'})
        assert denied.status_code == 400 and denied.json()['bizCode'] == 'DATA_NOT_FOUND', denied.text
        accepted = teacher.post(path + '/' + flow['recordId'] + '/remind', params=params, json={'reportType': 'DAILY'})
        assert accepted.status_code == 200 and accepted.json()['data']['queued'], accepted.text
        with get_sessionmaker()() as db:
            audits = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == tid, InternshipAuditTrail.target_type == 'REPORT_OBLIGATION')).all()
            assert len(audits) == 1 and str(audits[0].target_id) == flow['recordId']


def body(data, **extra):
    return {**context(data), 'expectedVersion': 0, 'weekNo': 1,
            'workContent': '岗位工作与安全操作记录。' * 5, 'harvestContent': '岗位学习成果。' * 5, **extra}


def test_teacher_queue_resolves_exact_todo_report_and_keeps_scope_and_batch(flow):
    foreign = seed_flow()
    queue = '/api/v1/mobile/teacher/internship'
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher, login(foreign, 'INTERN_MENTOR') as outsider:
        row = student.post(PORTAL+'/context/weekly-reports', json=body(flow)).json()['data']
        response = teacher.get(queue, params={'recordId':row['id'],'pageSize':1})
        assert response.status_code==200 and response.json()['code']==0, response.text
        selected = response.json()['data']
        assert selected['batchId']==flow['batchId'] and selected['focusReportId']==row['id']
        assert selected['weeklyReports'][0]['id']==row['id'] and selected['pagination']['weeklyPendingTotal']==1
        assert selected['available'] and selected['errors']==[]
        assert student.get(queue,params={'batchId':flow['batchId']}).status_code==403
        assert outsider.get(queue,params={'recordId':row['id']}).status_code in (403,404)
        wrong = teacher.get(queue,params={'recordId':row['id'],'batchId':flow['batches'][1]['id']})
        assert wrong.status_code==409 and not wrong.json().get('data'), wrong.text
        todos = teacher.get('/api/v1/teacher-mobile/internship/workbench/todos').json()['data']['items']
        own = next(item for item in todos if item['sourceBizId']==row['id'] and item['todoType']=='INTERN_WEEKLY_REVIEW')
        assert own['actionPath'].endswith('?tab=weekly&recordId='+row['id'])


@pytest.mark.parametrize('field',['workContent','harvestContent','planContent'])
def test_weekly_field_limit_rejects_before_database_write_and_accepts_boundary(flow,field):
    with login(flow,'STUDENT') as student:
        payload = body(flow,**{field:'合'*2001})
        denied = student.post(PORTAL+'/context/weekly-reports',json=payload)
        assert denied.status_code==400 and denied.json()['bizCode']=='VALIDATION_ERROR',denied.text
        assert '2000' in denied.json()['message']
        assert student.get(PORTAL+'/context/weekly-reports',params=context(flow)).json()['data']['items']==[]
        payload[field]='合'*2000
        accepted = student.post(PORTAL+'/context/weekly-reports',json=payload)
        assert accepted.status_code==200 and accepted.json()['code']==0,accepted.text


def test_teacher_queue_paginates_without_losing_the_focused_old_report(flow):
    queue = '/api/v1/mobile/teacher/internship'
    with login(flow,'STUDENT') as student, login(flow,'INTERN_MENTOR') as teacher:
        ids = [student.post(PORTAL+'/context/weekly-reports',json=body(flow,weekNo=week)).json()['data']['id'] for week in (1,2,3)]
        pages = [teacher.get(queue,params={'batchId':flow['batchId'],'pageSize':1,'weeklyPage':page}).json()['data'] for page in (1,2,3)]
        assert {row['id'] for page in pages for row in page['weeklyReports']}==set(ids)
        assert [page['pagination']['weeklyHasMore'] for page in pages]==[True,True,False]
        focused = teacher.get(queue,params={'recordId':ids[0],'pageSize':1}).json()['data']
        assert [row['id'] for row in focused['weeklyReports']]==[ids[0],ids[-1]]
        assert focused['pagination']['weeklyTotal']==focused['pagination']['weeklyPendingTotal']==3
        assert teacher.get(queue,params={'batchId':flow['batchId'],'pageSize':51}).status_code==422
        assert teacher.get(queue,params={'batchId':flow['batchId'],'weeklyPage':0}).status_code==422


def test_teacher_queue_preserves_reports_when_attendance_source_is_forbidden(flow):
    with get_sessionmaker()() as db:
        tenant = int(flow['tenantId'])
        role = db.scalar(select(Role).where(Role.tenant_id == tenant, Role.role_code == 'PROFESSIONAL_LEADER'))
        assert role is not None
        user = User(tenant_id=tenant,login_name='professional_leader',real_name='合成专业负责人',password_hash=hash_password(PASSWORD),
                    user_type='PROFESSIONAL_LEADER',status='ACTIVE',credential_version=0,must_change_password=False)
        db.add(user);db.flush()
        db.add_all([UserRole(tenant_id=tenant,user_id=user.id,role_id=role.id,status='ACTIVE'),
                    TeacherStudentScope(tenant_id=tenant,teacher_key='db-'+str(user.id),user_id=user.id,role_code='PROFESSIONAL_LEADER',
                                        scope_type='STUDENT',ref_id=int(flow['studentId']),ref_value='S0',status='ACTIVE')]);db.commit()
    with login(flow,'STUDENT') as student, login(flow,'PROFESSIONAL_LEADER') as teacher:
        row = student.post(PORTAL+'/context/weekly-reports',json=body(flow)).json()['data']
        response = teacher.get('/api/v1/mobile/teacher/internship',params={'recordId':row['id']})
        assert response.status_code==200 and response.json()['code']==0,response.text
        data=response.json()['data']
        assert data['weeklyReports'][0]['id']==row['id'] and data['pagination']['weeklyPendingTotal']==1
        assert not data['available'] and data['abnormalCheckins']==[]
        assert len(data['errors'])==1 and data['errors'][0]['source']=='attendanceException'
        assert data['errors'][0]['errorCode']=='NO_PERMISSION' and '无查看权限' in data['errors'][0]['message']


@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_own_detail_reads_two_immutable_versions_attachments_and_rating(flow, surface):
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        first = upload(student, biz='INTERNSHIP_REPORT')
        payload = body(flow, attachmentFileIds=[first['fileId']])
        created = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert created.status_code == 200 and created.json()['code'] == 0, created.text
        row = created.json()['data']
        review_url = STAFF+'/reports/'+row['id']+'/review'
        returned = teacher.post(review_url, json={'batchId': flow['batchId'], 'expectedVersion': row['version'],
                                                 'action': 'RETURN', 'comment': '请补充岗位工作成果与图片说明'})
        assert returned.json()['code'] == 0, returned.text
        selected = student.get(surface+'/context/weekly-reports/'+row['id'], params=context(flow))
        assert selected.json()['code'] == 0, selected.text
        detail = selected.json()['data']
        second = upload(student, name='corrected.png', biz='INTERNSHIP_REPORT')
        payload.update(expectedVersion=detail['version'], attachmentFileIds=[second['fileId']], workContent=payload['workContent']+'已按指导意见完善工作成果。')
        updated = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert updated.json()['code'] == 0, updated.text
        current = updated.json()['data']
        approved = teacher.post(review_url, json={'batchId': flow['batchId'], 'expectedVersion': current['version'],
                                                'action': 'APPROVE', 'comment': '修改后符合岗位要求', 'ratingLevel': 4})
        assert approved.json()['code'] == 0, approved.text
        final = student.get(surface+'/context/weekly-reports/'+row['id'], params=context(flow)).json()['data']
        assert final['status'] == 'APPROVED' and final['review']['ratingLevel'] == 4
        assert final['batchId'] == flow['batchId'] and final['internshipId'] == flow['recordId']
        versions = final['immutableVersions']
        assert [version['versionNo'] for version in versions] == [2, 1]
        assert versions[0]['content']['workContent'] == payload['workContent']
        assert versions[1]['content']['workContent'] != payload['workContent']
        assert versions[0]['review']['action'] == 'APPROVE' and versions[1]['review']['action'] == 'RETURN'
        assert [version['attachments'][0]['fileId'] for version in versions] == [second['fileId'], first['fileId']]
        assert all(version['submittedAt'].endswith('Z') for version in versions)
        staff_detail = teacher.get(STAFF+'/reports/'+row['id']).json()['data']
        assert all(version['submittedAt'].endswith('Z') and version['review']['reviewedAt'].endswith('Z')
                   for version in staff_detail['immutableVersions'])
        for file in [first, second]:
            assert student.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()
            assert teacher.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()


def teammate(flow):
    with get_sessionmaker()() as db:
        record = db.scalar(select(InternshipRecord).where(InternshipRecord.batch_id == int(flow['batches'][1]['id'])))
        role = db.scalar(select(Role).where(Role.tenant_id == int(flow['tenantId']), Role.role_code == 'STUDENT'))
        user = User(tenant_id=int(flow['tenantId']), login_name='other_student', real_name='另一个合成学生',
                    password_hash=hash_password(PASSWORD), user_type='STUDENT', status='ACTIVE', credential_version=0, must_change_password=False)
        db.add(user); db.flush()
        db.add_all([UserRole(tenant_id=int(flow['tenantId']), user_id=user.id, role_id=role.id, status='ACTIVE'),
                    StudentAccountLink(tenant_id=int(flow['tenantId']), user_id=user.id, student_id=record.student_id,
                                       link_status='ACTIVE', source='IDENTITY_IMPORT', bound_student_no='S1', bound_login_name='other_student')])
        db.commit()
        own_context = {'batchId': str(record.batch_id), 'internshipId': str(record.id)}
    client = TestClient(app)
    response = client.post('/api/v1/auth/browser-login', json={'tenantCode': flow['tenantCode'], 'loginName': 'other_student',
                           'password': PASSWORD, 'clientType': 'STUDENT_PC'}, headers={'X-Browser-Session-Id': 'weekly-'+uuid4().hex})
    assert response.status_code == 200, response.text
    client.headers.update({'Authorization': 'Bearer '+response.json()['data']['accessToken']})
    return client, own_context


@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_detail_denies_other_student_school_staff_wrong_batch_and_foreign_school(flow, surface):
    foreign = seed_flow()
    with login(flow, 'STUDENT') as student, login(flow) as staff, login(foreign, 'STUDENT') as outsider:
        created = student.post(MOBILE+'/context/weekly-reports', json=body(flow))
        row = created.json()['data']
        url = surface+'/context/weekly-reports/'+row['id']
        other, other_context = teammate(flow)
        with other:
            response = other.get(url, params=other_context)
            assert response.status_code == 404 and not response.json().get('data'), response.text
            assert other.get(url, params=context(flow)).json()['code'] != 0
        response = outsider.get(url, params=context(foreign))
        assert response.status_code == 404 and not response.json().get('data'), response.text
        assert staff.get(url, params=context(flow)).json()['code'] != 0
        assert student.get(url, params={**context(flow), 'batchId': flow['batches'][1]['id']}).json()['code'] != 0
        assert student.get(url).status_code == 422


def test_old_session_loses_weekly_detail_after_account_binding_revoked(flow):
    with login(flow, 'STUDENT') as student:
        row = student.post(MOBILE+'/context/weekly-reports', json=body(flow)).json()['data']
        with get_sessionmaker()() as db:
            link = db.scalar(select(StudentAccountLink).where(StudentAccountLink.user_id == flow['users']['STUDENT']))
            link.link_status = 'REVOKED'; db.commit()
        denied = student.get(MOBILE+'/context/weekly-reports/'+row['id'], params=context(flow))
        assert denied.status_code == 403 and not denied.json().get('data'), denied.text


def test_mobile_weekly_plan_minimum_and_scan_are_real_submission_gates(flow, monkeypatch):
    with get_sessionmaker()() as db:
        batch = db.get(InternshipBatch, int(flow['batchId']))
        batch.rules_config = {'weeklyReport': {'minWordCount': 120}}
        db.commit()
    monkeypatch.setenv('FILE_SCAN_REQUIRED', 'true')
    with login(flow, 'STUDENT') as student:
        short = student.post(MOBILE+'/context/weekly-reports', json=body(flow, workContent='工作', harvestContent='学习'))
        assert short.json()['code'] != 0
        pdf = BytesIO()
        Image.new('RGB', (160, 100), (235, 242, 250)).save(pdf, format='PDF')
        accepted = student.post('/api/v1/files', files={'file': ('report.pdf', pdf.getvalue(), 'application/pdf')})
        pending = accepted.json()['data']
        assert pending['readyForBusiness'] is False
        payload = body(flow, workContent='岗位工作。'*30, attachmentFileIds=[pending['fileId']])
        denied = student.post(MOBILE+'/context/weekly-reports', json=payload)
        assert denied.json()['code'] != 0 and not denied.json().get('data')
        assert student.get('/api/v1/files/download/'+pending['fileId']).status_code == 404
    with get_sessionmaker()() as db:
        assert db.scalar(select(WeeklyReport).where(WeeklyReport.internship_id == int(flow['recordId']))) is None


def process_body(data, kind='SUMMARY', **extra):
    return {**context(data), 'expectedVersion': 0, 'reportType': kind,
            'periodKey': '2026-10-06' if kind == 'DAILY' else '2026-10',
            'content': '合成岗位工作与成果记录。' * 35, **extra}


@pytest.mark.parametrize('kind', ['DAILY', 'MONTHLY', 'SUMMARY'])
@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_process_mobile_review_and_own_two_versions_keep_exact_score_and_files(flow, kind, surface):
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        first = upload(student, biz='INTERNSHIP_REPORT')
        payload = process_body(flow, kind, attachmentFileIds=[first['fileId']])
        created = student.post(MOBILE+'/context/reports', json=payload)
        assert created.status_code == 200 and created.json()['code'] == 0, created.text
        row = created.json()['data']
        review_url = TEACHER_MOBILE+'/process-reports/'+row['id']+'/review'
        returned = teacher.post(review_url, params={'batchId': flow['batchId']}, json={
            'action': 'RETURN', 'comment': '请补充岗位成果与图片说明', 'expectedVersion': row['version']})
        assert returned.status_code == 200 and returned.json()['code'] == 0, returned.text
        detail_url = surface+'/context/reports/'+row['id']
        selected = student.get(detail_url, params=context(flow))
        assert selected.status_code == 200 and selected.json()['code'] == 0, selected.text
        detail = selected.json()['data']
        second = upload(student, name='corrected.png', biz='INTERNSHIP_REPORT')
        payload.update(expectedVersion=detail['version'], attachmentFileIds=[second['fileId']],
                       content=payload['content']+'已按指导意见完善工作成果。')
        updated = student.post(PORTAL+'/context/reports', json=payload)
        assert updated.status_code == 200 and updated.json()['code'] == 0, updated.text
        current = updated.json()['data']
        score = {'summaryScore': 0} if kind == 'SUMMARY' else {'ratingLevel': 4}
        approved = teacher.post(review_url, params={'batchId': flow['batchId']}, json={
            'action': 'APPROVE', 'comment': '合成批阅评分', 'expectedVersion': current['version'], **score})
        assert approved.status_code == 200 and approved.json()['code'] == 0, approved.text
        final = student.get(detail_url, params=context(flow)).json()['data']
        assert final['status'] == 'APPROVED' and final['id'] == row['id']
        assert final['batchId'] == flow['batchId'] and final['internshipId'] == flow['recordId']
        if kind == 'SUMMARY':
            assert final['review']['summaryScore'] == 0
        else:
            assert final['review']['ratingLevel'] == 4
        if kind == 'SUMMARY':
            assert final['review']['ratingLevel'] is None
        versions = final['immutableVersions']
        assert [version['versionNo'] for version in versions] == [2, 1]
        assert versions[0]['content'] == payload['content'] and versions[1]['content'] != payload['content']
        assert versions[0]['review']['action'] == 'APPROVE' and versions[1]['review']['action'] == 'RETURN'
        assert [version['attachments'][0]['fileId'] for version in versions] == [second['fileId'], first['fileId']]
        assert all(version['submittedAt'].endswith('Z') and version['review']['reviewedAt'].endswith('Z') for version in versions)
        for file in (first, second):
            assert student.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()
            assert teacher.get('/api/v1/files/download/'+file['fileId']).content == png_bytes()


@pytest.mark.parametrize('surface', [MOBILE, PORTAL])
def test_own_process_detail_denies_wrong_owner_school_batch_and_revoked_binding(flow, surface):
    foreign = seed_flow()
    with login(flow, 'STUDENT') as student, login(flow) as school, login(foreign, 'STUDENT') as outsider:
        row = student.post(MOBILE+'/context/reports', json=process_body(flow)).json()['data']
        url = surface+'/context/reports/'+row['id']
        other, other_context = teammate(flow)
        with other:
            assert other.get(url, params=other_context).status_code == 404
        assert outsider.get(url, params=context(foreign)).status_code == 404
        assert school.get(url, params=context(flow)).status_code == 403
        assert student.get(url, params={**context(flow), 'batchId': flow['batches'][1]['id']}).status_code == 404
        assert student.get(url).status_code == 422
        with get_sessionmaker()() as db:
            link = db.scalar(select(StudentAccountLink).where(StudentAccountLink.user_id == flow['users']['STUDENT']))
            link.link_status = 'REVOKED'; db.commit()
        assert student.get(url, params=context(flow)).status_code == 403


@pytest.mark.parametrize('score', [None, '', ' ', True, 'NaN', 'Infinity', -1, 101])
def test_summary_mobile_invalid_score_does_not_create_review_or_change_version(flow, score):
    from app.models import InternshipReportReview
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher:
        row = student.post(MOBILE+'/context/reports', json=process_body(flow)).json()['data']
        rejected = teacher.post(TEACHER_MOBILE+'/process-reports/'+row['id']+'/review', params={'batchId': flow['batchId']},
            json={'action': 'APPROVE', 'summaryScore': score, 'expectedVersion': row['version']})
        assert rejected.status_code == 400 and rejected.json()['bizCode'] == 'VALIDATION_ERROR', rejected.text
        with get_sessionmaker()() as db:
            assert db.scalar(select(InternshipReportReview).where(InternshipReportReview.tenant_id == int(flow['tenantId']),
                InternshipReportReview.report_kind == 'PROCESS', InternshipReportReview.report_id == int(row['id']))) is None
        detail = student.get(MOBILE+'/context/reports/'+row['id'], params=context(flow)).json()['data']
        assert detail['status'] == 'PENDING_REVIEW' and detail['version'] == row['version'] and detail['review'] is None


def test_process_sql_pages_and_mentor_full_export_keep_scope_and_committed_audit(flow):
    import base64
    from openpyxl import load_workbook
    from app.models import InternshipAuditTrail
    foreign = seed_flow()
    with login(flow, 'STUDENT') as student, login(flow, 'INTERN_MENTOR') as teacher, login(foreign, 'INTERN_MENTOR') as outsider:
        ids = set()
        for day in range(1, 27):
            response = student.post(MOBILE+'/context/reports', json=process_body(flow, 'DAILY', periodKey=f'2026-09-{day:02}'))
            assert response.status_code == 200 and response.json()['code'] == 0, response.text
            ids.add(response.json()['data']['id'])
        params = {'batchId': flow['batchId'], 'reportType': 'DAILY', 'keyword': 'S0'}
        pages = [teacher.get(STAFF+'/process-reports', params={**params, 'page': page, 'pageSize': 20}).json()['data'] for page in (1, 2)]
        assert [len(page['items']) for page in pages] == [20, 6]
        assert all(page['total'] == 26 for page in pages)
        assert {row['id'] for page in pages for row in page['items']} == ids
        assert teacher.get(STAFF+'/process-reports', params={**params, 'keyword': '%'}).json()['data']['total'] == 0
        denied = outsider.get(STAFF+'/process-reports', params=params)
        assert denied.status_code == 404 and not denied.json().get('data'), denied.text
        assert student.post(STAFF+'/process-reports/export', params=params).status_code == 403
        exported = teacher.post(STAFF+'/process-reports/export', params=params)
        assert exported.status_code == 200 and exported.json()['code'] == 0, exported.text
        workbook = load_workbook(BytesIO(base64.b64decode(exported.json()['data']['contentBase64'])), data_only=False)
        rows = list(workbook.active.values)
        header = next(index for index, row in enumerate(rows) if row[0] == '学号')
        data_rows = rows[header+1:]
        assert len(data_rows) == 26 and len(rows[header]) == 13
        assert {row[4] for row in data_rows} == {f'2026-09-{day:02}' for day in range(1, 27)}
        with get_sessionmaker()() as db:
            audits = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(flow['tenantId']),
                InternshipAuditTrail.target_type == 'EXPORT', InternshipAuditTrail.action == 'EXPORT')).all()
            assert len(audits) == 1 and audits[0].detail_json['totalRows'] == 26
            record = db.get(InternshipRecord, int(flow['recordId']))
            record.advisor_user_id = None; db.commit()
        assert teacher.get(STAFF+'/process-reports', params=params).json()['data']['total'] == 0

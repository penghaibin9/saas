"""正常导师指导单、批量回执和附件；只连接隔离自动测试库。"""
from uuid import uuid4
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from io import BytesIO
import base64

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_sessionmaker
from app.models import InternshipAuditTrail, InternshipGuidance, InternshipRecord, StudentProfile, User, RiskRecord, SecurityAuditLog
from app.models.file import FileBinding, FileObject
from test_yiyang_write_flows_mysql import flow, login, upload, png_bytes, seed_flow

GUIDANCES = '/api/v1/internship/guidances'


def ok(response):
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


def payload(data, **fields):
    return {'internshipId': data['recordId'], 'batchId': data['batchId'],
            'guidanceDate': '2026-10-05', 'method': 'PHONE', 'topic': '合成岗位适应指导',
            'content': '合成指导事实，仅用于本地正常角色联调，不构成学校指导证明。',
            'requestKey': uuid4().hex, **fields}


def test_guidance_actual_date_and_bound_photo_read_back(flow):
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school:
        file = upload(teacher, name='guidance-proof.png', biz='ATTACHMENT')
        body = payload(flow, fileId=file['fileId'])
        saved = ok(teacher.post(GUIDANCES, json=body))
        detail = ok(school.get(GUIDANCES + '/' + saved['id']))
        assert detail['guidanceDate'] == body['guidanceDate']
        assert detail['batchId'] == flow['batchId']
        assert detail['content'] == body['content'] and detail['methodLabel'] == '电话'
        assert detail['attachment']['fileId'] == file['fileId']
        assert teacher.get('/api/v1/files/download/' + file['fileId']).content == png_bytes()
        assert school.get('/api/v1/files/download/' + file['fileId']).content == png_bytes()
    with get_sessionmaker()() as db:
        guide = db.get(InternshipGuidance, int(saved['id']))
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == int(flow['tenantId']), FileBinding.file_id == int(file['fileId']),
            FileBinding.status == 'ACTIVE', FileBinding.is_current.is_(True)))
        assert str(guide.guidance_date) == body['guidanceDate']
        assert binding.biz_type == 'INTERNSHIP_GUIDANCE' and binding.biz_id == saved['id']
        assert binding.student_id == int(flow['studentId']) and binding.batch_id == flow['batchId']
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == int(flow['tenantId']),
            InternshipAuditTrail.target_type == 'GUIDANCE', InternshipAuditTrail.target_id == guide.id,
            InternshipAuditTrail.action == 'CREATE')) == 1


def test_guidance_retry_is_same_record_and_changed_request_is_conflict(flow):
    with login(flow, 'INTERN_MENTOR') as teacher:
        body = payload(flow)
        first = ok(teacher.post(GUIDANCES, json=body))
        second = ok(teacher.post(GUIDANCES, json=body))
        assert first['id'] == second['id'] and second['replayed'] is True
        changed = teacher.post(GUIDANCES, json={**body, 'content': '修改内容不能覆盖已成功的原单'})
        assert changed.status_code == 409
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipGuidance).where(
            InternshipGuidance.tenant_id == int(flow['tenantId']))) == 1


@pytest.mark.parametrize('field,value', [('guidanceDate', '2026-02-30'), ('guidanceDate', True),
    ('method', 'INTERNAL_RAW_ENUM'), ('content', ' '), ('toRisk', 'false'), ('requestKey', 'short')])
def test_guidance_invalid_contract_is_rejected_without_writes(flow, field, value):
    with login(flow, 'INTERN_MENTOR') as teacher:
        response = teacher.post(GUIDANCES, json=payload(flow, **{field: value}))
        assert response.status_code in (400, 422), response.text
    with get_sessionmaker()() as db:
        assert not db.scalar(select(InternshipGuidance.id).where(
            InternshipGuidance.tenant_id == int(flow['tenantId'])))


def test_guidance_batch_context_relationship_and_student_denied(flow):
    foreign = seed_flow()
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow, 'STUDENT') as student:
        assert student.post(GUIDANCES, json=payload(flow)).status_code == 403
        assert teacher.post(GUIDANCES, json=payload(flow, batchId=flow['batches'][1]['id'])).status_code == 400
        assert teacher.post(GUIDANCES, json=payload(foreign)).status_code == 404
        with get_sessionmaker()() as db:
            record = db.get(InternshipRecord, int(flow['recordId']))
            record.advisor_user_id = flow['users']['SCHOOL_ADMIN']; db.commit()
        assert teacher.post(GUIDANCES, json=payload(flow)).status_code == 403


def second_student(data):
    with get_sessionmaker()() as db:
        original = db.get(InternshipRecord, int(data['recordId']))
        student = StudentProfile(tenant_id=original.tenant_id, student_no='GUIDE-' + uuid4().hex[:10],
            real_name='合成第二指导学生', current_stage='INTERNSHIP', student_status='NORMAL', status='ACTIVE')
        db.add(student); db.flush()
        record = InternshipRecord(tenant_id=original.tenant_id, student_id=student.id,
            batch_id=original.batch_id, advisor_user_id=original.advisor_user_id,
            advisor_name=original.advisor_name, enterprise_name=original.enterprise_name, status='ONBOARD')
        db.add(record); db.commit()
        return str(record.id)


def test_guidance_bulk_independent_results_files_and_retry(flow):
    other = second_student(flow)
    with login(flow, 'INTERN_MENTOR') as teacher:
        one = upload(teacher, name='guide-one.png', biz='ATTACHMENT')
        two = upload(teacher, name='guide-two.png', biz='ATTACHMENT')
        body = payload(flow); body.pop('internshipId'); body.pop('requestKey')
        body['items'] = [
            {'internshipId': flow['recordId'], 'requestKey': uuid4().hex, 'fileId': one['fileId']},
            {'internshipId': other, 'requestKey': uuid4().hex, 'fileId': two['fileId']},
            {'internshipId': '9223372036854775806', 'requestKey': uuid4().hex}]
        result = ok(teacher.post(GUIDANCES + '/batch', json=body))
        assert result['successCount'] == 2 and result['failedCount'] == 1
        assert [item['success'] for item in result['items']] == [True, True, False]
        retry = ok(teacher.post(GUIDANCES + '/batch', json=body))
        assert [item.get('id') for item in retry['items']] == [item.get('id') for item in result['items']]
        assert all(item['replayed'] for item in retry['items'][:2])
        assert teacher.get('/api/v1/files/download/' + one['fileId']).content == png_bytes()
        assert teacher.get('/api/v1/files/download/' + two['fileId']).content == png_bytes()
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipGuidance).where(
            InternshipGuidance.tenant_id == int(flow['tenantId']))) == 2
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == int(flow['tenantId']), FileBinding.biz_type == 'INTERNSHIP_GUIDANCE')).all()
        assert len(bindings) == 2 and len({binding.biz_id for binding in bindings}) == 2


def test_guidance_unready_or_borrowed_file_is_not_bound(flow):
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow, 'STUDENT') as student:
        borrowed = upload(student, name='student-private.png', biz='ATTACHMENT')
        assert teacher.post(GUIDANCES, json=payload(flow, fileId=borrowed['fileId'])).status_code in (403, 404)
        pending = upload(teacher, name='guide-pending.png', biz='ATTACHMENT')
        with get_sessionmaker()() as db:
            row = db.get(FileObject, int(pending['fileId']))
            row.status = 'QUARANTINED'; row.scan_status = 'PENDING'; db.commit()
        assert teacher.post(GUIDANCES, json=payload(flow, fileId=pending['fileId'])).status_code in (400, 404)
    with get_sessionmaker()() as db:
        assert not db.scalar(select(InternshipGuidance.id).where(InternshipGuidance.tenant_id == int(flow['tenantId'])))


def test_guidance_photo_revoked_relationship_and_voided_binding_denied(flow):
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school:
        file = upload(teacher, name='guide-revocation.png', biz='ATTACHMENT')
        saved = ok(teacher.post(GUIDANCES, json=payload(flow, fileId=file['fileId'])))
        with get_sessionmaker()() as db:
            rec = db.get(InternshipRecord, int(flow['recordId']))
            rec.advisor_user_id = flow['users']['SCHOOL_ADMIN']; db.commit()
        assert teacher.get('/api/v1/files/download/' + file['fileId']).status_code == 404
        assert school.get('/api/v1/files/download/' + file['fileId']).content == png_bytes()
        detail = ok(school.get(GUIDANCES + '/' + saved['id']))
        ok(school.post(GUIDANCES + '/' + saved['id'] + '/void', json={
            'batchId': flow['batchId'], 'expectedVersion': detail['version'], 'reason': '合成误填记录撤销'}))
        assert school.get('/api/v1/files/download/' + file['fileId']).status_code == 404


def test_guidance_required_audit_failure_rolls_back_business_and_binding(flow, monkeypatch):
    from app.modules.internship.services import internship_guidance_service as service
    with login(flow, 'INTERN_MENTOR') as teacher:
        file = upload(teacher, name='guide-rollback.png', biz='ATTACHMENT')
        original = service._trail
        def fail(db, *args, **kwargs):
            original(db, *args, **kwargs); db.flush()
            raise SQLAlchemyError('synthetic guidance required audit failure')
        monkeypatch.setattr(service, '_trail', fail)
        with pytest.raises(SQLAlchemyError):
            teacher.post(GUIDANCES, json=payload(flow, fileId=file['fileId']))
    with get_sessionmaker()() as db:
        assert not db.scalar(select(InternshipGuidance.id).where(InternshipGuidance.tenant_id == int(flow['tenantId'])))
        assert not db.scalar(select(FileBinding.id).where(FileBinding.tenant_id == int(flow['tenantId']),
            FileBinding.file_id == int(file['fileId'])))
        assert db.get(FileObject, int(file['fileId'])).biz_type == 'TEMP_PRIVATE'


def test_guidance_normal_mentor_export_permission(flow):
    with login(flow, 'INTERN_MENTOR') as teacher:
        ok(teacher.post(GUIDANCES, json=payload(flow)))
        ok(teacher.post(GUIDANCES + '/export', params={'batchId': flow['batchId']}))


def test_guidance_same_key_concurrent_is_one_guidance_binding_risk_and_audit(flow):
    with login(flow, 'INTERN_MENTOR') as first, login(flow, 'INTERN_MENTOR') as second:
        file = upload(first, name='guide-concurrent.png', biz='ATTACHMENT')
        body = payload(flow, fileId=file['fileId'], toRisk=True)
        barrier = Barrier(2)
        def send(client):
            barrier.wait(timeout=10)
            return ok(client.post(GUIDANCES, json=body))
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(send, first); b = pool.submit(send, second)
            rows = [a.result(timeout=30), b.result(timeout=30)]
        assert rows[0]['id'] == rows[1]['id'] and sorted(row['replayed'] for row in rows) == [False, True]
        assert rows[0]['riskId'] == rows[1]['riskId'] and rows[0]['riskId']
    with get_sessionmaker()() as db:
        tid = int(flow['tenantId'])
        assert db.scalar(select(func.count()).select_from(InternshipGuidance).where(InternshipGuidance.tenant_id == tid)) == 1
        assert db.scalar(select(func.count()).select_from(FileBinding).where(FileBinding.tenant_id == tid, FileBinding.biz_type == 'INTERNSHIP_GUIDANCE')) == 1
        assert db.scalar(select(func.count()).select_from(RiskRecord).where(RiskRecord.tenant_id == tid)) == 1
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == tid, InternshipAuditTrail.target_type == 'GUIDANCE', InternshipAuditTrail.action == 'CREATE')) == 1


def test_guidance_original_key_reauthorizes_author_relationship_and_revoked_session(flow):
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school:
        body = payload(flow); saved = ok(teacher.post(GUIDANCES, json=body))
        assert school.post(GUIDANCES, json=body).status_code == 409
        with get_sessionmaker()() as db:
            rec = db.get(InternshipRecord, int(flow['recordId'])); rec.advisor_user_id = flow['users']['SCHOOL_ADMIN']; db.commit()
        assert teacher.post(GUIDANCES, json=body).status_code == 403
        with get_sessionmaker()() as db:
            rec = db.get(InternshipRecord, int(flow['recordId'])); rec.advisor_user_id = flow['users']['INTERN_MENTOR']; db.commit()
        ok(school.post(GUIDANCES + '/' + saved['id'] + '/void', json={'batchId': flow['batchId'], 'expectedVersion': 0, 'reason': '合成错误指导作废'}))
        assert teacher.post(GUIDANCES, json=body).status_code == 409
        with get_sessionmaker()() as db:
            user = db.get(User, flow['users']['INTERN_MENTOR']); user.credential_version = int(user.credential_version or 0) + 1; db.commit()
        assert teacher.post(GUIDANCES, json=body).status_code == 401
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(InternshipGuidance).where(InternshipGuidance.tenant_id == int(flow['tenantId']))) == 1


def test_guidance_bulk_late_risk_failure_preserves_first_and_retries_original_key(flow, monkeypatch):
    from app.modules.internship.services import internship_guidance_service as service
    other = second_student(flow)
    with login(flow, 'INTERN_MENTOR') as teacher:
        files = [upload(teacher, name='guide-bulk-' + str(i) + '.png', biz='ATTACHMENT') for i in range(2)]
        body = payload(flow, toRisk=True); body.pop('internshipId'); body.pop('requestKey')
        body['items'] = [{'internshipId': record, 'requestKey': uuid4().hex, 'fileId': file['fileId']}
                         for record, file in zip((flow['recordId'], other), files)]
        original = service._trail
        def fail(db, gid, action, *args, **kwargs):
            original(db, gid, action, *args, **kwargs)
            if action == 'SPAWN_RISK' and str(db.get(InternshipGuidance, gid).internship_id) == other:
                db.flush(); raise SQLAlchemyError('synthetic second-item late risk failure')
        monkeypatch.setattr(service, '_trail', fail)
        result = ok(teacher.post(GUIDANCES + '/batch', json=body))
        assert [item['success'] for item in result['items']] == [True, False]
        assert result['items'][1]['code'] == 'SAVE_FAILED'
        with get_sessionmaker()() as db:
            tid = int(flow['tenantId'])
            assert db.scalar(select(func.count()).select_from(InternshipGuidance).where(InternshipGuidance.tenant_id == tid)) == 1
            assert db.scalar(select(func.count()).select_from(RiskRecord).where(RiskRecord.tenant_id == tid)) == 1
            assert not db.scalar(select(FileBinding.id).where(FileBinding.tenant_id == tid, FileBinding.file_id == int(files[1]['fileId'])))
            assert db.get(FileObject, int(files[1]['fileId'])).biz_type == 'TEMP_PRIVATE'
        monkeypatch.setattr(service, '_trail', original)
        again = ok(teacher.post(GUIDANCES + '/batch', json=body))
        assert again['successCount'] == 2 and again['items'][0]['id'] == result['items'][0]['id']
        assert again['items'][0]['replayed'] and not again['items'][1]['replayed']


@pytest.mark.parametrize('reason', ['student', 'foreign', 'relationship', 'binding', 'void', 'permission'])
def test_guidance_all_file_entries_enforce_current_business_access(flow, monkeypatch, reason):
    from test_teacher_visit_story_mysql import file_paths, denied_file
    with login(flow, 'INTERN_MENTOR') as teacher, login(flow) as school:
        file = upload(teacher, name='guide-access.png', biz='ATTACHMENT')
        saved = ok(teacher.post(GUIDANCES, json=payload(flow, fileId=file['fileId'])))
        for client in (teacher, school):
            for path in file_paths(file['fileId']):
                assert client.get(path).status_code == 200
        if reason in ('student', 'foreign'):
            data = flow if reason == 'student' else seed_flow()
            with login(data, 'STUDENT' if reason == 'student' else 'SCHOOL_ADMIN') as denied:
                denied_file(denied, file['fileId'])
        else:
            if reason == 'relationship':
                with get_sessionmaker()() as db:
                    rec = db.get(InternshipRecord, int(flow['recordId'])); rec.advisor_user_id = flow['users']['SCHOOL_ADMIN']; db.commit()
            elif reason == 'binding':
                with get_sessionmaker()() as db:
                    binding = db.scalar(select(FileBinding).where(FileBinding.file_id == int(file['fileId']), FileBinding.tenant_id == int(flow['tenantId'])))
                    binding.status = 'REVOKED'; binding.is_current = False; db.commit()
            elif reason == 'void':
                ok(school.post(GUIDANCES + '/' + saved['id'] + '/void', json={'batchId': flow['batchId'], 'expectedVersion': 0, 'reason': '合成指导作废'}))
            else:
                from app.models import Role, RolePermission, Permission
                from app.core.permissions import _matches
                with get_sessionmaker()() as db:
                    links=db.execute(select(RolePermission,Permission.permission_code).join(Permission,
                        Permission.id==RolePermission.permission_id).join(Role,Role.id==RolePermission.role_id).where(
                        RolePermission.tenant_id==int(flow['tenantId']),Role.tenant_id==int(flow['tenantId']),Role.role_code=='INTERN_MENTOR')).all()
                    for grant,code in links:
                        if _matches(code,'internship.guidance.view'):grant.status='DISABLED'
                    db.commit()
            denied_file(teacher, file['fileId'])


def test_guidance_month_uses_actual_date_and_reports_unknown_history(flow, monkeypatch):
    from app.modules.internship.services import internship_guidance_service as service
    monkeypatch.setattr(service, 'local_now', lambda: datetime(2026, 10, 6))
    with login(flow, 'INTERN_MENTOR') as teacher:
        saved = [ok(teacher.post(GUIDANCES, json=payload(flow, guidanceDate=day))) for day in ('2026-10-01', '2026-09-30', '2026-10-02')]
        # 明确迁移前历史日期前置；不作为真实办理证据。
        with get_sessionmaker()() as db:
            db.get(InternshipGuidance, int(saved[0]['id'])).created_at = datetime(2026, 9, 1)
            db.get(InternshipGuidance, int(saved[1]['id'])).created_at = datetime(2026, 10, 1)
            db.get(InternshipGuidance, int(saved[2]['id'])).guidance_date = None
            db.commit()
        plans = ok(teacher.get('/api/v1/internship/guidance-plans', params={'batchId': flow['batchId']}))
        row = next(item for item in plans['items'] if item['internId'] == flow['recordId'])
        assert (row['monthCount'], row['termCount'], row['unknownDateCount']) == (1, 3, 1)
        detail = ok(teacher.get(GUIDANCES + '/' + saved[2]['id']))
        assert detail['guidanceDate'] == '' and detail['guidanceDateLabel'] == '未登记指导日期'


def test_guidance_full_paged_export_has_actual_date_body_scope_and_database_audit(flow, monkeypatch):
    from openpyxl import load_workbook
    foreign = seed_flow()
    with login(foreign, 'INTERN_MENTOR') as other:
        ok(other.post(GUIDANCES, json=payload(foreign)))
    with login(flow, 'INTERN_MENTOR') as teacher:
        body = '合成正文换行\n' + '完整指导内容' * 70
        ids = [ok(teacher.post(GUIDANCES, json=payload(flow, content=body, topic='合成完整导出')))['id'] for _ in range(25)]
        query = {'batchId': flow['batchId'], 'keyword': '合成完整导出'}
        second_page = ok(teacher.get(GUIDANCES, params={**query, 'page': 2, 'pageSize': 20}))
        assert second_page['total'] == 25 and len(second_page['items']) == 5
        result = ok(teacher.post(GUIDANCES + '/export', params=query))
        book = load_workbook(BytesIO(base64.b64decode(result['contentBase64'])))
        rows = list(book.active.values); header_index = next(i for i, row in enumerate(rows) if '指导编号' in row)
        headers = rows[header_index]
        records = [dict(zip(headers, row)) for row in rows[header_index + 1:header_index + 26]]
        assert len(records) == 25 and {str(row['指导编号']) for row in records} == set(ids)
        assert all(row['指导日期'] == '2026-10-05' and row['指导正文'] == body and row['指导方式'] == '电话' for row in records)
        with get_sessionmaker()() as db:
            audit = db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == int(flow['tenantId']),
                SecurityAuditLog.resource == 'internship-guidance:export').order_by(SecurityAuditLog.id.desc()))
            assert audit and audit.detail_json['rowCount'] == 25 and audit.detail_json['keyword'] == query['keyword']
        from app.services import db_service
        def fail(*args, **kwargs):
            raise SQLAlchemyError('synthetic export audit unavailable')
        monkeypatch.setattr(db_service, 'audit_insert_in_session', fail)
        with pytest.raises(SQLAlchemyError):
            teacher.post(GUIDANCES + '/export', params=query)

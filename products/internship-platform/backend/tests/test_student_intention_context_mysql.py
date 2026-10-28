"""Only new synthetic schools in the exact opted-in local MySQL test database."""
import os
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from app.config import settings
from app.db.session import get_engine, get_sessionmaker
from app.models import InternshipRecord, InternshipIntention, InternshipAuditTrail, StudentProfile
from test_yiyang_write_flows_mysql import seed_flow, login

MOBILE = '/api/v1/mobile/internship/context/intention'
STAFF = '/api/v1/internship/match/intentions'


@pytest.fixture
def workspace():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('requires explicit MySQL opt-in')
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test'
    assert (url.get_backend_name(), url.host, url.port, url.database) == ('mysql', '127.0.0.1', 3318, 'internship_pr275_test_20261003')
    with get_engine().connect() as connection:
        assert connection.scalar(text('select database()')) == url.database
    ws = seed_flow()
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, int(ws['recordId']))
        record.status = 'READY'; record.destination_type = 'NONE'
        ws['studentNo'] = db.get(StudentProfile, int(ws['studentId'])).student_no
        ws['otherRecordId'] = str(db.scalar(select(InternshipRecord.id).where(InternshipRecord.tenant_id == int(ws['tenantId']), InternshipRecord.id != record.id)))
        db.commit()
    return ws


def ctx(ws):
    return {'batchId': ws['batchId'], 'internshipId': ws['recordId']}


def ok(response):
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


def body(ws, row=None, **fields):
    return {**ctx(ws), 'preferredCity': '合成意向城市', 'preferredIndustry': '软件服务', 'intentionNote': '只用于独立合成学校验收',
            **({'id': row['id'], 'expectedVersion': row['version']} if row else {}), **fields}


def test_student_reads_saves_submits_withdraws_same_intention_with_atomic_versions(workspace):
    with login(workspace, 'STUDENT') as student:
        initial = ok(student.get(MOBILE, params=ctx(workspace)))
        assert initial['intention'] is None and initial['canEdit'] is True
        saved = ok(student.put(MOBILE, json=body(workspace)))['intention']
        revised = ok(student.put(MOBILE, json=body(workspace, saved, intentionNote='第二次合成输入')))['intention']
        assert revised['id'] == saved['id'] and revised['version'] == saved['version'] + 1
        stale = student.put(MOBILE, json=body(workspace, saved, intentionNote='旧页面不能覆盖'))
        assert stale.json()['bizCode'] == 'DATA_CONFLICT'
        submitted = ok(student.post(MOBILE+'/submit', json=body(workspace, revised)))['intention']
        withdrawn = ok(student.post(MOBILE+'/withdraw', json=body(workspace, submitted)))
        assert withdrawn['intention']['status'] == 'WITHDRAWN' and withdrawn['canEdit'] is False and withdrawn['canCreateNew'] is True
        assert student.put(MOBILE, json=body(workspace, withdrawn['intention'])).json()['code'] != 0
        restored = ok(student.post(MOBILE+'/submit', json=body(workspace, withdrawn['intention'])))['intention']
        assert restored['id'] == saved['id'] and restored['status'] == 'SUBMITTED'
        assert ok(student.get(MOBILE, params=ctx(workspace)))['intention']['version'] == restored['version']
    with get_sessionmaker()() as db:
        rows = db.scalars(select(InternshipIntention).where(InternshipIntention.tenant_id == int(workspace['tenantId']))).all()
        assert len(rows) == 1 and rows[0].intention_note == '第二次合成输入'
        actions = db.scalars(select(InternshipAuditTrail.action).where(InternshipAuditTrail.tenant_id == int(workspace['tenantId']), InternshipAuditTrail.target_type == 'MATCH', InternshipAuditTrail.target_id == rows[0].id)).all()
        assert actions.count('INTENTION_CREATE') == 1 and actions.count('INTENTION_SUBMIT') == 2 and 'INTENTION_WITHDRAW' in actions


def test_school_edit_and_import_advance_version_and_reject_stale_mobile_input(workspace):
    with login(workspace, 'STUDENT') as student, login(workspace) as school:
        row = ok(student.put(MOBILE, json=body(workspace)))['intention']
        changed = ok(school.put(STAFF+'/'+row['id'], json={'intentionNote': '学校更正合成说明'}))
        assert changed['version'] == row['version'] + 1
        assert student.put(MOBILE, json=body(workspace, row)).json()['bizCode'] == 'DATA_CONFLICT'
        imported = ok(school.post(STAFF+'/import/confirm', json={'batchId': workspace['batchId'], 'rows': [{'studentNo': workspace['studentNo'], 'city': '导入更新城市', 'note': '学校导入后的合成说明'}]}))
        assert imported == {'created': 0, 'total': 1}
        latest = ok(student.get(MOBILE, params=ctx(workspace)))['intention']
        assert latest['version'] == changed['version'] + 1 and latest['preferredCity'] == '导入更新城市'
        assert student.put(MOBILE, json=body(workspace, changed)).json()['bizCode'] == 'DATA_CONFLICT'
        assert ok(student.get(MOBILE, params=ctx(workspace)))['intention']['intentionNote'] == '学校导入后的合成说明'
        staff_row = ok(school.post(STAFF, json={'recordId': workspace['otherRecordId'], 'preferredCity': '学校创建城市'}))
        staff_submitted = ok(school.post(STAFF+'/'+staff_row['id']+'/submit'))
        staff_withdrawn = ok(school.post(STAFF+'/'+staff_row['id']+'/withdraw'))
        assert staff_submitted['version'] == staff_row['version'] + 1 and staff_withdrawn['version'] == staff_row['version'] + 2
        assert staff_withdrawn['status'] == 'WITHDRAWN'


def test_intention_context_denies_staff_foreign_wrong_record_and_placed_student_writes(workspace):
    foreign = seed_flow()
    with login(workspace, 'STUDENT') as student, login(workspace) as school, login(foreign, 'STUDENT') as outsider:
        for client, params in [(school, ctx(workspace)), (outsider, ctx(workspace)), (student, {**ctx(workspace), 'internshipId': workspace['otherRecordId']})]:
            assert client.get(MOBILE, params=params).status_code in (400, 403, 404, 409)
        assert student.get(MOBILE).status_code == 422
        row = ok(student.put(MOBILE, json=body(workspace)))['intention']
        for position_id in ['999999999999', 'not-a-position']:
            assert student.put(MOBILE, json=body(workspace, row, preferredPositionId=position_id)).json()['code'] != 0
        with get_sessionmaker()() as db:
            record = db.get(InternshipRecord, int(workspace['recordId']))
            record.destination_type = 'SELF_ARRANGED'; record.enterprise_name = '新合成已落实企业'; record.position_name = '新合成已落实岗位'
            db.commit()
        readonly = ok(student.get(MOBILE, params=ctx(workspace)))
        assert not any(readonly[key] for key in ['canEdit', 'canSubmit', 'canWithdraw', 'canCreateNew'])
        for suffix in ['', '/submit', '/withdraw']:
            response = student.put(MOBILE, json=body(workspace, row)) if not suffix else student.post(MOBILE+suffix, json=body(workspace, row))
            assert response.json()['code'] != 0


def test_withdrawn_intention_can_only_start_new_after_explicit_versioned_choice(workspace):
    with login(workspace, 'STUDENT') as student:
        saved = ok(student.put(MOBILE, json=body(workspace)))['intention']
        submitted = ok(student.post(MOBILE+'/submit', json=body(workspace, saved)))['intention']
        withdrawn = ok(student.post(MOBILE+'/withdraw', json=body(workspace, submitted)))['intention']
        assert student.put(MOBILE, json=body(workspace)).json()['code'] != 0
        next_body = body(workspace, newAfterWithdraw=True, previousIntentionId=withdrawn['id'], previousExpectedVersion=withdrawn['version'], intentionNote='撤回后明确重新填写')
        created = ok(student.put(MOBILE, json=next_body))['intention']
        assert created['id'] != withdrawn['id'] and created['status'] == 'DRAFT'
        assert student.put(MOBILE, json=next_body).json()['code'] != 0
    with get_sessionmaker()() as db:
        original = db.get(InternshipIntention, int(withdrawn['id']))
        assert original.status == 'WITHDRAWN' and original.version == withdrawn['version']

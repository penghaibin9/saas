"""正常账号咨询：只写严格指定本地测试库中新建的 SUPPORT-FLOW 学校。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.exceptions import AppException
from app.core.security import hash_password
from app.db.session import get_engine, get_sessionmaker
from app.models import Tenant, Role, User, UserRole, StudentProfile, StudentAccountLink, InternshipBatch, InternshipRecord, InternshipAuditTrail, RiskRecord
from app.models.internship import InternshipSupportSession
from app.models import MessageEventOutbox
from app.modules.internship.services import internship_student_support_service as support
from app.modules.internship.services import internship_risk_service as risks
from app.services.system_authorization import bootstrap_school
from test_yiyang_plan_export_options_mysql import login, PASSWORD

ROOT = '/api/v1/mobile/internship/context/support'
HELP = '/api/v1/mobile/internship/context/help'


def require_support_test_target():
    url = make_url(settings.DATABASE_URL)
    allowed_targets = {
        ('127.0.0.1', 3318, 'internship_pr275_test_20261003'),
        ('127.0.0.1', 3306, 'internship_employment_test_ci'),
    }
    if settings.APP_ENV != 'test' or url.get_backend_name() != 'mysql' or (url.host, url.port, url.database) not in allowed_targets:
        raise RuntimeError('support tests require an explicitly authorized isolated MySQL target')
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        raise RuntimeError('support tests require explicit isolated MySQL opt-in')
    with get_engine().connect() as db:
        assert db.scalar(text('SELECT DATABASE()')) == url.database


def seed_support():
    require_support_test_target()
    code = 'SUPPORT-FLOW-' + uuid4().hex[:12]
    with get_sessionmaker()() as db:
        tenant = Tenant(tenant_code=code, school_name='咨询原轮防重合成学校', deploy_mode='SAAS', db_mode='SHARED', status='ACTIVE')
        db.add(tenant); db.flush(); bootstrap_school(db, tenant.id)
        users = {}
        for role_code, user_type in [('SCHOOL_ADMIN', 'SCHOOL_ADMIN'), ('INTERN_MENTOR', 'TEACHER'), ('STUDENT', 'STUDENT')]:
            role = db.scalar(select(Role).where(Role.tenant_id == tenant.id, Role.role_code == role_code))
            user = User(tenant_id=tenant.id, login_name=role_code.lower(), real_name='咨询合成'+role_code,
                        password_hash=hash_password(PASSWORD), user_type=user_type, status='ACTIVE', credential_version=0, must_change_password=False)
            db.add(user); db.flush(); db.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=role.id, status='ACTIVE')); users[role_code] = user.id
        batch = InternshipBatch(tenant_id=tenant.id, batch_no=code, batch_name='咨询同一会话验收批次', status='RUNNING',
            start_date=datetime(2026, 9, 1), end_date=datetime(2026, 12, 31), rules_version=1)
        student = StudentProfile(tenant_id=tenant.id, student_no='SUP001', real_name='咨询合成学生', current_stage='ENROLLED', student_status='NORMAL', status='ACTIVE')
        db.add_all([batch, student]); db.flush()
        db.add(StudentAccountLink(tenant_id=tenant.id, student_id=student.id, user_id=users['STUDENT'], link_status='ACTIVE', source='IDENTITY_IMPORT', bound_student_no=student.student_no, bound_login_name='student'))
        record = InternshipRecord(tenant_id=tenant.id, student_id=student.id, batch_id=batch.id, status='ONBOARD', eligibility_status='QUALIFIED',
            advisor_user_id=users['INTERN_MENTOR'], advisor_name='咨询合成INTERN_MENTOR', intern_start_date=datetime(2026, 9, 1), intern_end_date=datetime(2026, 12, 31))
        db.add(record); db.commit()
        return {'tenantCode':code, 'tenantId':str(tenant.id), 'users':users, 'batchId':str(batch.id), 'recordId':str(record.id), 'studentId':str(student.id)}


@pytest.fixture
def story(record_property):
    data = seed_support()
    for key in ['tenantId', 'tenantCode', 'batchId', 'recordId']:
        record_property(key, data[key])
    return data


def context(data):
    return {'batchId':data['batchId'], 'internshipId':data['recordId']}


def result(response):
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


def ask(client, data, question='周报怎么提交'):
    return result(client.post(ROOT+'/ask', json={**context(data), 'message':question}))


def feedback(client, data, answer, action='unresolved'):
    return client.post(ROOT+'/'+answer['sessionId']+'/'+action, json={**context(data), 'answerVersion':answer['answerVersion']})


def third_answer(client, data):
    for question in ['周报怎么提交', '请假证明怎么交']:
        result(feedback(client, data, ask(client, data, question)))
    return ask(client, data, '定位还是异常，需老师现场核对')


def test_answer_refresh_same_feedback_idempotent_and_old_answer_rejected(story):
    with login(story, 'STUDENT') as student:
        first = ask(student, story)
        refreshed = result(student.get(ROOT, params=context(story)))
        assert refreshed['awaitingFeedback'] is True and refreshed['answerVersion'] == first['answerVersion']
        assert student.post(ROOT+'/ask', json={**context(story), 'message':'不能覆盖待评价回答'}).status_code == 409
        one = result(feedback(student, story, first)); again = result(feedback(student, story, first))
        assert one['unresolvedCount'] == again['unresolvedCount'] == 1
        assert feedback(student, story, first, 'solved').status_code == 409
        second = ask(student, story, '请假需要证明吗')
        assert second['answerVersion'] > first['answerVersion']
        assert feedback(student, story, first).status_code == 409
        solved = result(feedback(student, story, second, 'solved'))
        assert solved['status'] == 'SOLVED' and not solved['awaitingFeedback']
        assert result(feedback(student, story, second, 'solved'))['status'] == 'SOLVED'
    with get_sessionmaker()() as db:
        audits = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == int(story['tenantId']), InternshipAuditTrail.target_type == 'SUPPORT_SESSION')).all()
        assert len(audits) == 4


def test_legacy_original_answer_restores_from_audit_without_read_write(story):
    with login(story, 'STUDENT') as student:
        answer = ask(student, story)
        with get_sessionmaker()() as db:
            row = db.get(InternshipSupportSession, int(answer['sessionId']))
            history = [dict(item) for item in row.context_json]; history[-1].pop('answerVersion'); row.context_json = history; db.commit()
        refreshed = result(student.get(ROOT, params=context(story)))
        assert refreshed['awaitingFeedback'] and refreshed['answerVersion'] == answer['answerVersion']
        with get_sessionmaker()() as db:
            assert 'answerVersion' not in db.get(InternshipSupportSession, int(answer['sessionId'])).context_json[-1]
        assert result(feedback(student, story, refreshed))['unresolvedCount'] == 1


def test_three_answers_reuse_manual_help_and_keep_full_context_once(story):
    original = '原有人工求助说明必须完整保留，不能被客服覆盖。'
    with login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher:
        manual = result(student.post(HELP, json={**context(story), 'content':original, 'title':'已有人工求助'}))
        third = third_answer(student, story)
        transferred = result(feedback(student, story, third)); repeated = result(feedback(student, story, third))
        assert transferred['transferredRiskId'] == repeated['transferredRiskId'] == manual['id']
        detail = result(teacher.get('/api/v1/internship/risks/'+manual['id']))
        assert detail['lastFollowNote'] == original
        attached = [item for item in detail['auditTrail'] if item['action'] == 'SUPPORT_CONTEXT_ATTACHED']
        assert len(attached) == 1 and '周报怎么提交' in attached[0]['detail']['note'] and '需老师现场核对' in attached[0]['detail']['note']
        assert len(result(student.get(HELP, params=context(story)))['items']) == 1
    with get_sessionmaker()() as db:
        events = db.scalars(select(MessageEventOutbox).where(MessageEventOutbox.tenant_id == int(story['tenantId']))).all()
        assert len(events) == 2 and all(e.status == 'SUCCEEDED' for e in events)


def test_concurrent_third_feedback_uses_two_connections_one_risk_and_audit(story, monkeypatch, record_property):
    with login(story, 'STUDENT') as first, login(story, 'STUDENT') as second:
        answer = third_answer(first, story)
        barrier = Barrier(2); connections = []; original_session = support.session
        @contextmanager
        def simultaneous():
            with original_session() as db:
                connections.append(db.scalar(text('SELECT CONNECTION_ID()'))); barrier.wait(timeout=10)
                yield db
        monkeypatch.setattr(support, 'session', simultaneous)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(feedback, client, story, answer) for client in [first, second]]
            values = [result(future.result(timeout=20)) for future in futures]
        assert len(set(connections)) == 2
        assert values[0]['transferredRiskId'] == values[1]['transferredRiskId']
    with get_sessionmaker()() as db:
        tid = int(story['tenantId'])
        assert db.scalar(select(func.count()).select_from(RiskRecord).where(RiskRecord.tenant_id == tid)) == 1
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == tid, InternshipAuditTrail.action == 'SUPPORT_TRANSFER_TO_HUMAN')) == 1
        assert db.scalar(select(func.count()).select_from(MessageEventOutbox).where(MessageEventOutbox.tenant_id == tid)) == 1
        assert db.get(InternshipSupportSession, int(answer['sessionId'])).unresolved_count == 3
    record_property('independentMysqlConnections', str(len(set(connections))))


@pytest.mark.parametrize('stage', ['risk', 'audit', 'notification'])
def test_transfer_failure_rolls_back_every_fact_then_retry_succeeds(story, monkeypatch, stage):
    from app.services import message_event_outbox_service as messages
    with login(story, 'STUDENT') as student:
        answer = third_answer(student, story)
        with monkeypatch.context() as patch:
            original_risk, original_audit = risks.student_help_in_session, support.add_audit
            def fail():
                raise AppException('SUPPORT_TEST_FAILURE', '合成失败测试', http_status=503)
            def broken_risk(*args, **kwargs):
                original_risk(*args, **kwargs); fail()
            def broken_audit(*args, **kwargs):
                if kwargs.get('action') == 'SUPPORT_TRANSFER_TO_HUMAN': fail()
                return original_audit(*args, **kwargs)
            if stage == 'risk': patch.setattr(risks, 'student_help_in_session', broken_risk)
            elif stage == 'audit': patch.setattr(support, 'add_audit', broken_audit)
            else: patch.setattr(messages, 'emit_message_event', lambda *a, **k: fail())
            assert feedback(student, story, answer).status_code == 503
        with get_sessionmaker()() as db:
            tid = int(story['tenantId']); row = db.get(InternshipSupportSession, int(answer['sessionId']))
            assert row.status == 'ACTIVE' and row.unresolved_count == 2 and not row.transferred_risk_id
            assert row.context_json[-1].get('feedback') is None
            assert db.scalar(select(func.count()).select_from(RiskRecord).where(RiskRecord.tenant_id == tid)) == 0
            assert db.scalar(select(func.count()).select_from(MessageEventOutbox).where(MessageEventOutbox.tenant_id == tid)) == 0
            assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == tid, InternshipAuditTrail.action == 'SUPPORT_TRANSFER_TO_HUMAN')) == 0
        assert result(feedback(student, story, answer))['status'] == 'TRANSFERRED'


def test_foreign_school_cannot_read_or_feedback_original_session(story):
    foreign = seed_support()
    with login(story, 'STUDENT') as owner, login(foreign, 'STUDENT') as outsider:
        answer = ask(owner, story)
        response = outsider.post(ROOT+'/'+answer['sessionId']+'/unresolved', json={**context(foreign), 'answerVersion':answer['answerVersion']})
        assert response.status_code in (403, 404)
        assert result(owner.get(ROOT, params=context(story)))['unresolvedCount'] == 0


def test_post_commit_delivery_failure_keeps_one_persisted_handoff(story, monkeypatch):
    from app.services import message_event_outbox_service as messages
    with login(story, 'STUDENT') as student:
        answer = third_answer(student, story)
        def fail_delivery(*args, **kwargs):
            raise RuntimeError('isolated support delivery failure')
        with monkeypatch.context() as patch:
            patch.setattr(messages, '_deliver', fail_delivery)
            transferred = result(feedback(student, story, answer))
        repeated = result(feedback(student, story, answer))
        assert transferred['transferredRiskId'] == repeated['transferredRiskId']
    with get_sessionmaker()() as db:
        tid = int(story['tenantId'])
        events = db.scalars(select(MessageEventOutbox).where(MessageEventOutbox.tenant_id == tid)).all()
        assert len(events) == 1 and events[0].status == 'RETRY_WAIT' and events[0].attempt_count == 1
        assert db.scalar(select(func.count()).select_from(RiskRecord).where(RiskRecord.tenant_id == tid)) == 1
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id == tid, InternshipAuditTrail.action == 'SUPPORT_TRANSFER_TO_HUMAN')) == 1

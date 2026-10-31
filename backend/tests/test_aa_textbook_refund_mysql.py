"""教材真实数据库回归：签收、收款、退款、退领与学生回读。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import secrets
import uuid
import pytest
from sqlalchemy.engine import make_url

from test_aa_textbook import BASE, TID
from test_aa_textbook_student import _stu_token


@pytest.fixture
def db_mode():
    """仅允许本任务新建的独立库；不重建、不清理任何已有表。"""
    from app.core.config import settings
    from app.db.session import reset_state
    url = make_url(os.environ['TEST_DATABASE_URL'])
    assert url.host == '127.0.0.1' and url.port == 3307 and url.database.startswith(('textbook_test_', 'textbook_migrate_test_'))
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, os.environ['TEST_DATABASE_URL']
    reset_state()
    yield
    settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
    reset_state()


def _scene(client):
    from app.core.security_legacy import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (Tenant, User, Role, RolePermission, UserRole, RoleAssignmentScope,
        AaTerm, AaTextbook, AaTextbookOrderBatch, AaTextbookOrderItem,
        AaTextbookDistributionBatch, AaTextbookDistributionRecord, StudentProfile)
    from tests.support_grade_review_identity import _ensure_permission

    suffix = uuid.uuid4().hex[:10]
    account, password = 'tb_audit_' + suffix, secrets.token_urlsafe(20)
    student_no = 'TB' + suffix
    with get_sessionmaker()() as db:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code='demo', school_name='教材独立测试学校', status='ACTIVE'))
        user = User(tenant_id=TID, login_name=account, real_name='教材测试员', user_type='TEACHER', password_hash=hash_password(password), status='ACTIVE')
        role = Role(tenant_id=TID, role_code='TBTEST_' + suffix.upper(), role_name='教材测试岗', role_type='CUSTOM', status='ACTIVE')
        db.add_all([user, role]); db.flush()
        link = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status='ACTIVE'); db.add(link); db.flush()
        for code in ['academicAffairs.textbook.view', 'academicAffairs.textbook.fee.manage', 'academicAffairs.textbook.distribution.manage', 'academicAffairs.textbook.order.manage']:
            permission = _ensure_permission(db, code)
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status='ACTIVE'))
        db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id, role_code=role.role_code, scope_type='SCHOOL', scope_id=0, effective_at=datetime(2020, 1, 1), status='ACTIVE'))
        term = db.query(AaTerm).filter_by(tenant_id=TID, year_code='2098-2099', term_no=1, is_deleted=False).first()
        if not term:
            term = AaTerm(tenant_id=TID, year_code='2098-2099', term_no=1, status='PUBLISHED', is_current=False)
            db.add(term)
        student = StudentProfile(tenant_id=TID, student_no=student_no, real_name='退款测试学生', current_stage='ON_CAMPUS', student_status='NORMAL', status='ACTIVE')
        book = AaTextbook(tenant_id=TID, name='退款测试教材', isbn='TB' + suffix, unit_price=50, status='ENABLED')
        db.add_all([student, book]); db.flush()
        order = AaTextbookOrderBatch(tenant_id=TID, batch_name='退款测试征订', term_id=term.id, status='ARRIVED'); db.add(order); db.flush()
        db.add(AaTextbookOrderItem(tenant_id=TID, order_batch_id=order.id, textbook_id=book.id, textbook_name=book.name, order_qty=1, arrived_qty=1, unit_price_snapshot=50))
        batch = AaTextbookDistributionBatch(tenant_id=TID, order_batch_id=order.id, status='DISTRIBUTING'); db.add(batch); db.flush()
        record = AaTextbookDistributionRecord(tenant_id=TID, batch_id=batch.id, student_id=student.id, textbook_id=book.id, textbook_name=book.name, qty=1, status='PENDING'); db.add(record); db.flush()
        record_id = record.id
        db.commit()
    response = client.post('/api/v1/auth/login', json={'loginName': account, 'password': password, 'tenantCode': 'demo'})
    assert response.status_code == 200 and response.json().get('data'), '独立测试角色的真实登录未成功'
    return record_id, student_no, {'Authorization': 'Bearer ' + response.json()['data']['accessToken']}


def _limited_distribution_actor(client, *, college=False):
    from app.core.security_legacy import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User, Role, RolePermission, UserRole, RoleAssignmentScope, College
    from tests.support_grade_review_identity import _ensure_permission
    suffix = uuid.uuid4().hex[:10]
    account, password = 'tb_dist_' + suffix, secrets.token_urlsafe(20)
    with get_sessionmaker()() as db:
        user = User(tenant_id=TID, login_name=account, real_name='教材发放测试员', user_type='TEACHER', password_hash=hash_password(password), status='ACTIVE')
        role = Role(tenant_id=TID, role_code='TBDIST_' + suffix.upper(), role_name='教材发放测试岗', role_type='CUSTOM', status='ACTIVE')
        db.add_all([user, role]); db.flush()
        link = UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status='ACTIVE'); db.add(link); db.flush()
        codes = ['academicAffairs.textbook.view', 'academicAffairs.textbook.distribution.manage']
        if college:
            codes.append('academicAffairs.textbook.fee.manage')
        for code in codes:
            permission = _ensure_permission(db, code)
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status='ACTIVE'))
        scope_id = 0
        if college:
            owner = College(tenant_id=TID, college_name='教材权限测试学院' + suffix, status='ACTIVE'); db.add(owner); db.flush(); scope_id = owner.id
        db.add(RoleAssignmentScope(tenant_id=TID, user_role_id=link.id, user_id=user.id, role_code=role.role_code, scope_type='COLLEGE' if college else 'SCHOOL', scope_id=scope_id, effective_at=datetime(2020, 1, 1), status='ACTIVE'))
        db.commit()
    response = client.post('/api/v1/auth/login', json={'loginName': account, 'password': password, 'tenantCode': 'demo'})
    assert response.status_code == 200 and response.json().get('data'), '发放岗位的真实登录未成功'
    return {'Authorization': 'Bearer ' + response.json()['data']['accessToken']}


def test_refund_and_return_preserve_payment_and_student_totals(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTextbookFeeLedger, AaTextbookRefund

    record_id, student_no, school = _scene(client)
    distribution = _limited_distribution_actor(client)
    college = _limited_distribution_actor(client, college=True)
    student = _stu_token('退款测试学生', student_no)
    assert client.post(f'/api/v1/mobile/academic/textbook/{record_id}/sign', headers=student).status_code == 200
    fees = client.get(f'{BASE}/textbooks/fee-ledger', headers=school).json()['data']['items']
    fee_id = fees[0]['feeId']
    mark = f'{BASE}/textbooks/fee-ledger/{fee_id}/mark'
    assert client.post(mark, headers=school, json={'action': 'PARTIAL', 'amount': 10, 'expectedPaidAmount': 0}).status_code == 200
    ret = f'{BASE}/textbooks/distribution-records/{record_id}/return'
    reason = {'reason': '测试实际退款后退领'}
    assert client.post(ret, headers=school, json=reason).status_code == 409
    refund_url = f'{BASE}/textbooks/fee-ledger/{fee_id}/refund'
    payload = {'reason': '测试已实际退还全部实收', 'expectedPaidAmount': 10}
    assert client.post(refund_url, headers=student, json=payload).status_code == 403
    assert client.post(refund_url, headers=distribution, json=payload).status_code == 403
    assert client.post(refund_url, headers=college, json=payload).status_code == 403
    assert client.post(refund_url, headers=school, json={**payload, 'expectedPaidAmount': 9}).status_code == 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(refund_url, headers=school, json=payload), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()['data']['idempotent'] for response in responses) == [False, True]
    with get_sessionmaker()() as db:
        fee = db.get(AaTextbookFeeLedger, int(fee_id))
        assert float(fee.paid_amount) == 10 and fee.status == 'REFUNDED'
        assert db.query(AaTextbookRefund).filter_by(fee_id=int(fee_id)).count() == 1
        batch_id = fee.distribution_record_id
        from app.models import AaTextbookDistributionRecord
        distribution_record = db.get(AaTextbookDistributionRecord, batch_id)
        batch_id, textbook_id = distribution_record.batch_id, distribution_record.textbook_id
    detail = client.get(f'{BASE}/textbooks/distribution-workbench/{batch_id}/records', headers=distribution)
    assert detail.status_code == 200
    visible = next(row for row in detail.json()['data']['items'] if row['recordId'] == str(record_id))
    assert visible['feeStatus'] == 'REFUNDED' and visible['amount'] is None and visible['paidAmount'] is None and visible['refundAmount'] is None
    interim = client.get('/api/v1/mobile/academic/textbook/my', headers=student, params={'feePage': 1}).json()['data']['fees']
    assert interim['totalPaid'] == 0 and interim['totalRefunded'] == 10 and interim['unpaid'] == 0
    assert client.post(ret, headers=distribution, json=reason).status_code == 200
    assert client.post(ret, headers=school, json=reason).json()['data']['idempotent'] is True
    final = client.get('/api/v1/mobile/academic/textbook/my', headers=student, params={'feePage': 1}).json()['data']
    assert final['distributions'][0]['status'] == 'RETURNED'
    assert final['fees']['totalPaid'] == 0 and final['fees']['totalRefunded'] == 10 and final['fees']['unpaid'] == 0
    stock = client.get(f'{BASE}/textbooks/stock', headers=school).json()['data']['items']
    assert next(row for row in stock if row['textbookId'] == str(textbook_id))['stockQty'] == 1

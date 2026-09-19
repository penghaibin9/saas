"""实收前值作为原子前置条件：重试与并发不能重复累计教材费用。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from test_aa_textbook import BASE, TID, _hdr
from test_aa_textbook_student import _seed_dist, _stu_token


def test_partial_fee_retries_and_concurrency_never_double_collect(client, db_mode, monkeypatch):
    from sqlalchemy import text
    from app.db.session import get_sessionmaker
    from app.models import AaTextbookFeeLedger, AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_textbook_final_facade as service

    _profile, record = _seed_dist('FEE-CAS-1', '并发费用学生', price=50)
    admin = _hdr(client, 'school_admin01')
    student = _stu_token('并发费用学生', 'FEE-CAS-1')
    assert client.post(f'{BASE}/textbooks/distribution-records/{record}/sign', headers=admin).status_code == 200
    session = get_sessionmaker()
    with session() as db:
        fee_id = db.query(AaTextbookFeeLedger).filter_by(distribution_record_id=record).one().id
    endpoint = f'{BASE}/textbooks/fee-ledger/{fee_id}/mark'
    payload = dict(action='PARTIAL', amount=10, expectedPaidAmount=0)
    assert client.post(endpoint, headers=student, json=payload).status_code == 403
    assert client.post(endpoint, headers=admin, json=dict(action='PARTIAL', amount=10)).status_code == 400
    for amount in [0, -1, 0.001, 1e100]:
        result = client.post(endpoint, headers=admin, json={**payload, 'amount': amount})
        assert result.status_code in (400, 422), result.text

    barrier = Barrier(2)
    connections = set()
    get_order = service._get_order_batch

    def synchronized(db, value, *, lock=False):
        if lock:
            connections.add(db.execute(text('SELECT CONNECTION_ID()')).scalar())
            assert db.execute(text('SELECT @@transaction_isolation')).scalar() == 'REPEATABLE-READ'
            # _fee_chain 在父锁前已预览 ORM fee。锁后必须刷新同一 ORM 实例。
            barrier.wait(timeout=20)
        return get_order(db, value, lock=lock)

    with monkeypatch.context() as patch:
        patch.setattr(service, '_get_order_batch', synchronized)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(client.post, endpoint, headers=admin, json=payload) for _ in range(2)]
            results = [future.result(timeout=30) for future in pending]
    assert len(connections) == 2
    assert sorted(result.status_code for result in results) == [200, 409], [r.text for r in results]
    repeated = client.post(endpoint, headers=admin, json=payload)
    assert repeated.status_code == 409 and '未再次入账' in repeated.json()['message']
    assert client.post(endpoint, headers=admin, json={'action': 'PAID', 'expectedPaidAmount': 0}).status_code == 409

    def student_totals(expected_paid, expected_unpaid):
        for path in ['/api/v1/mobile/academic/textbook/my', '/api/v1/portal/academic/textbook']:
            response = client.get(path, headers=student)
            assert response.status_code == 200, response.text
            fees = response.json()['data']['fees']
            assert fees['totalDue'] == 50 and fees['totalPaid'] == expected_paid and fees['unpaid'] == expected_unpaid

    student_totals(10, 40)
    stats = client.get(f'{BASE}/textbooks/stats', headers=admin)
    assert stats.status_code == 200 and stats.json()['data']['unpaidAmount'] == 40
    with session() as db:
        fee = db.get(AaTextbookFeeLedger, fee_id)
        assert fee.status == 'PARTIAL' and float(fee.paid_amount) == 10
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type='AA_TEXTBOOK_FEE', biz_id=fee_id, action='TEXTBOOK_FEE_MARK').count() == 1
    # 实收不能被减免/退领擦掉；按最新已收金额确认下一笔，才可结清。
    assert client.post(endpoint, headers=admin, json={'action':'WAIVE', 'waiveReason':'不能减免已实收款项'}).status_code == 409
    assert client.post(f'{BASE}/textbooks/distribution-records/{record}/return', headers=admin, json={'reason':'测试已有实收应阻断'}).status_code == 409
    final = client.post(endpoint, headers=admin, json={'action':'PARTIAL', 'amount':40, 'expectedPaidAmount':10})
    assert final.status_code == 200 and final.json()['data']['status'] == 'PAID'
    assert client.post(endpoint, headers=admin, json={'action':'PARTIAL', 'amount':40, 'expectedPaidAmount':10}).status_code == 409
    student_totals(50, 0)
    assert client.get(f'{BASE}/textbooks/stats', headers=admin).json()['data']['unpaidAmount'] == 0

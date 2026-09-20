"""MySQL 并发：原批次追加不覆盖历史、不重复分配、不超卖。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from test_aa_textbook import BASE, TID, _hdr, _seed, _stu_token


def test_append_is_explicit_idempotent_and_serializes_with_receipts(client, db_mode, monkeypatch):
    from sqlalchemy import text
    from app.db.session import get_sessionmaker
    from app.models import (AaTextbook, AaTextbookSelection, AaTextbookOrderBatch,
        AaTextbookOrderItem, AaTextbookDistributionRecord, AaTextbookDistributionBatch,
        AaTextbookFeeLedger, AffairsAuditTrail, StudentProfile)
    from app.modules.academic_affairs.services import academic_affairs_textbook_final_facade as service

    ids = _seed(db_mode)
    session = get_sessionmaker()
    with session() as db:
        original = db.get(StudentProfile, ids['student'])
        students = [StudentProfile(tenant_id=TID, student_no=f'APPEND{i}', real_name=f'追加{i}',
            college_id=original.college_id, major_id=original.major_id, class_id=original.class_id,
            student_status='NORMAL', status='ACTIVE') for i in range(5)]
        book = AaTextbook(tenant_id=TID, name='追加并发教材', unit_price=31)
        order = AaTextbookOrderBatch(tenant_id=TID, term_id=ids['term'], batch_name='追加并发', status='PARTIALLY_ARRIVED')
        db.add_all([book, order, *students]); db.flush()
        selection = AaTextbookSelection(tenant_id=TID, task_id=ids['task'], textbook_id=book.id,
            textbook_name=book.name, expected_qty=6, status='ORDERED')
        item = AaTextbookOrderItem(tenant_id=TID, order_batch_id=order.id, textbook_id=book.id,
            textbook_name=book.name, order_qty=6, arrived_qty=3, unit_price_snapshot=31)
        db.add_all([selection, item]); db.flush()
        db.add(AffairsAuditTrail(tenant_id=TID, biz_type='AA_TEXTBOOK_ORDER', biz_id=order.id,
            action='TEXTBOOK_ORDER_SOURCE', detail=f'selectionId={selection.id}'))
        order_id, item_id = order.id, item.id
        student_ids = [student.id for student in students]
        db.commit()

    admin = _hdr(client, 'school_admin01')
    endpoint = f'{BASE}/textbooks/distribution-batches'
    base = dict(orderBatchId=str(order_id), classId=str(ids['class']))
    first = client.post(endpoint, headers=admin, json={**base, 'studentIds': [str(ids['student'])]})
    assert first.status_code == 200, first.text
    batch_id = int(first.json()['data']['distributionBatchId'])
    with session() as db:
        initial = db.query(AaTextbookDistributionRecord).filter_by(batch_id=batch_id).one()
        initial_id = initial.id
    assert client.post(f'{BASE}/textbooks/distribution-records/{initial_id}/sign', headers=admin).status_code == 200
    with session() as db:
        assert db.get(AaTextbookDistributionBatch, batch_id).status == 'COMPLETED'
        assert db.get(AaTextbookDistributionBatch, batch_id).completed_at is not None

    def append(student_id, target=batch_id, headers=admin):
        return client.post(endpoint, headers=headers, json={**base, 'appendToBatchId': str(target), 'studentIds': [str(student_id)]})

    assert client.post(endpoint, headers=admin, json={**base, 'studentIds': [str(student_ids[0])]}).status_code == 409
    assert append(student_ids[0], target=batch_id + 1000).status_code == 409
    assert append(student_ids[0], headers=_stu_token('书甲', 'TB2401')).status_code == 403

    # 在获得父锁之前让两个真实 MySQL 连接都建立 RR 快照，再同时提交。
    # 这会暴露使用普通快照读计算库存/已有记录导致的重复插入或超卖。
    def race(*commands):
        barrier = Barrier(2)
        connections = set()
        get_order = service._get_order_batch

        def synchronized(db, value, *, lock=False):
            if lock:
                connections.add(db.execute(text('SELECT CONNECTION_ID()')).scalar())
                assert db.execute(text('SELECT @@transaction_isolation')).scalar() == 'REPEATABLE-READ'
                db.query(AaTextbookDistributionRecord.id).first()
                barrier.wait(timeout=20)
            return get_order(db, value, lock=lock)

        with monkeypatch.context() as patch:
            patch.setattr(service, '_get_order_batch', synchronized)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(command) for command in commands]
                results = [future.result(timeout=30) for future in futures]
        assert len(connections) == 2
        return results

    duplicate = race(lambda: append(student_ids[0]), lambda: append(student_ids[0]))
    assert [response.status_code for response in duplicate] == [200, 200], [r.text for r in duplicate]
    assert sorted(r.json()['data']['addedRecordCount'] for r in duplicate) == [0, 1]
    assert all(r.json()['data']['recordCount'] == 2 for r in duplicate)

    # 只余一本库存，两个不同学生竞争，必须只有一人新增成功。
    competing = race(lambda: append(student_ids[1]), lambda: append(student_ids[2]))
    assert sorted(r.status_code for r in competing) == [200, 409], [r.text for r in competing]
    with session() as db:
        rows = db.query(AaTextbookDistributionRecord).filter_by(batch_id=batch_id).all()
        assert len(rows) == 3 and len({r.student_id for r in rows}) == 3
        original = db.get(AaTextbookDistributionRecord, initial_id)
        fee = db.query(AaTextbookFeeLedger).filter_by(distribution_record_id=initial_id).one()
        signature = original.received_at
        assert original.status == 'RECEIVED' and signature is not None
        assert float(fee.amount) == 31 and float(fee.paid_amount) == 0 and fee.status == 'UNPAID'
        db.get(AaTextbookOrderItem, item_id).arrived_qty = 6
        db.commit()

    with session() as db:
        pending_id = db.query(AaTextbookDistributionRecord).filter_by(batch_id=batch_id, student_id=student_ids[0]).one().id
    sign_and_append = race(lambda: client.post(f'{BASE}/textbooks/distribution-records/{pending_id}/sign', headers=admin),
        lambda: append(student_ids[3]))
    assert [r.status_code for r in sign_and_append] == [200, 200], [r.text for r in sign_and_append]
    returned = client.post(f'{BASE}/textbooks/distribution-records/{initial_id}/return', headers=admin,
        json={'reason': '并发测试正式退领，不重新生成原记录'})
    assert returned.status_code == 200, returned.text
    replay = append(ids['student'])
    assert replay.status_code == 200 and replay.json()['data']['addedRecordCount'] == 0
    with session() as db:
        original = db.get(AaTextbookDistributionRecord, initial_id)
        assert original.status == 'RETURNED' and original.received_at == signature
        assert db.query(AaTextbookFeeLedger).filter_by(distribution_record_id=initial_id).one().status == 'WAIVED'
        deleted = db.query(AaTextbookDistributionRecord).filter_by(batch_id=batch_id, student_id=student_ids[3]).one()
        deleted.is_deleted = True
        db.commit()
    assert append(student_ids[3]).status_code == 409
    with session() as db:
        assert db.get(AaTextbookDistributionBatch, batch_id).status == 'DISTRIBUTING'
        assert db.get(AaTextbookDistributionBatch, batch_id).completed_at is None
    stock = client.get(f'{BASE}/textbooks/stock', headers=admin)
    assert stock.status_code == 200, stock.text
    row = stock.json()['data']['items'][0]
    assert row['arrivedQty'] == 6 and row['reservedQty'] == 1 and row['distributedQty'] == 1
    assert row['stockQty'] == 4 and row['dataConflict'] is False
    with session() as db:
        db.get(AaTextbookOrderItem, item_id).arrived_qty = 1
        db.commit()
    conflicted = client.get(f'{BASE}/textbooks/stock', headers=admin).json()['data']['items'][0]
    assert conflicted['stockQty'] == -1 and conflicted['dataConflict'] is True

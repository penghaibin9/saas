"""真实 MySQL：征订来源→正式教学名单→逐书库存→发放及幂等回读。"""
from test_aa_textbook import BASE, TID, _hdr, _seed


def test_distribution_uses_source_rosters_not_every_order_item(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaTeachingTask, AaTextbook, AaTextbookSelection, AaTextbookOrderBatch,
        AaTextbookOrderItem, AaTextbookDistributionBatch, AaTextbookDistributionRecord,
        AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AffairsAuditTrail,
        SchoolClass, StudentProfile,
    )

    ids = _seed(db_mode)
    session = get_sessionmaker()
    with session() as db:
        student = db.get(StudentProfile, ids['student'])
        second = StudentProfile(tenant_id=TID, student_no='TB2402', real_name='书乙',
            college_id=student.college_id, major_id=student.major_id, class_id=student.class_id,
            student_status='NORMAL', status='ACTIVE')
        other_class = SchoolClass(tenant_id=TID, major_id=student.major_id, class_name='另一个班', grade='2024')
        db.add_all([second, other_class]); db.flush()
        outsider = StudentProfile(tenant_id=TID, student_no='TB2403', real_name='书丙',
            college_id=student.college_id, major_id=student.major_id, class_id=other_class.id,
            student_status='NORMAL', status='ACTIVE')
        task = db.get(AaTeachingTask, ids['task'])
        elective = AaTeachingTask(tenant_id=TID, batch_id=task.batch_id, course_id=2,
            course_name='选修课程', class_id=task.class_id)
        unrelated = AaTeachingTask(tenant_id=TID, batch_id=task.batch_id, course_id=3,
            course_name='其他班课程', class_id=other_class.id)
        order = AaTextbookOrderBatch(tenant_id=TID, term_id=ids['term'], batch_name='来源分配验证', status='PARTIALLY_ARRIVED')
        selection_batch = AaSelectionBatch(tenant_id=TID, term_id=ids['term'], batch_name='正式选课名单', status='OPEN')
        books = [AaTextbook(tenant_id=TID, name=name, unit_price=10) for name in ['必修书', '选修书', '其他班教材']]
        db.add_all([outsider, elective, unrelated, order, selection_batch, *books]); db.flush()
        offer = AaSelectionCourse(tenant_id=TID, batch_id=selection_batch.id, course_id=2,
            teaching_task_id=elective.id, status='OPEN', capacity=10)
        selections = [AaTextbookSelection(tenant_id=TID, task_id=task_id, textbook_id=book.id,
            textbook_name=book.name, expected_qty=qty, status='ORDERED')
            for task_id, book, qty in zip([task.id, elective.id, unrelated.id], books, [2, 1, 1])]
        items = [AaTextbookOrderItem(tenant_id=TID, order_batch_id=order.id, textbook_id=book.id,
            textbook_name=book.name, order_qty=qty, arrived_qty=arrived, unit_price_snapshot=10)
            for book, qty, arrived in zip(books, [2, 1, 1], [1, 1, 0])]
        db.add_all([offer, *selections, *items]); db.flush()
        db.add(AaSelectionRecord(tenant_id=TID, batch_id=selection_batch.id,
            selection_course_id=offer.id, course_id=2, student_id=student.id, status='LOCKED'))
        order_id, second_id, outsider_id, other_class_id = order.id, second.id, outsider.id, other_class.id
        selection_batch_id = selection_batch.id
        source_ids, book_ids, item_ids = [row.id for row in selections], [row.id for row in books], [row.id for row in items]
        db.commit()

    admin = _hdr(client, 'school_admin01')
    body = {'orderBatchId': str(order_id), 'classId': str(ids['class']),
        'studentIds': [str(ids['student']), str(second_id)]}

    def generate():
        return client.post(f'{BASE}/textbooks/distribution-batches', headers=admin, json=body)

    response = generate()
    assert response.status_code == 409 and '来源选用快照' in response.json()['message']
    with session() as db:
        assert db.query(AaTextbookDistributionBatch).filter_by(tenant_id=TID).count() == 0
        db.add_all([AffairsAuditTrail(tenant_id=TID, biz_type='AA_TEXTBOOK_ORDER', biz_id=order_id,
            action='TEXTBOOK_ORDER_SOURCE', detail=f'selectionId={value}') for value in source_ids])
        db.commit()
    response = generate()
    assert response.status_code == 409 and '名单' in response.json()['message']
    with session() as db:
        db.get(AaSelectionBatch, selection_batch_id).status = 'LOCKED'
        db.get(AaTextbookOrderItem, item_ids[0]).order_qty = 3
        db.commit()
    response = generate()
    assert response.status_code == 409 and '数量' in response.json()['message']
    with session() as db:
        db.get(AaTextbookOrderItem, item_ids[0]).order_qty = 2
        db.commit()
    response = generate()
    assert response.status_code == 409 and '库存不足' in response.json()['message']
    with session() as db:
        assert db.query(AaTextbookDistributionRecord).filter_by(tenant_id=TID).count() == 0
        db.get(AaTextbookOrderItem, item_ids[0]).arrived_qty = 2
        db.commit()

    response = generate()
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['recordCount'] == 3
    with session() as db:
        pairs = {(row.student_id, row.textbook_id) for row in db.query(AaTextbookDistributionRecord).filter_by(tenant_id=TID)}
        assert pairs == {(ids['student'], book_ids[0]), (ids['student'], book_ids[1]), (second_id, book_ids[0])}
    repeated = generate().json()['data']
    assert repeated['idempotent'] and repeated['distributionBatchId'] == result['distributionBatchId']
    # 新名单必须重新验证；既有批次重复请求只回读既有事实，不随新选课状态重写。
    with session() as db:
        db.get(AaSelectionBatch, selection_batch_id).status = 'OPEN'
        db.commit()
    assert generate().json()['data']['idempotent']
    body['studentIds'] = [str(second_id)]
    assert generate().status_code == 409
    # 另一个班只会匹配其教材；无关教材库存不足不应占用其库存。
    with session() as db:
        db.get(AaSelectionBatch, selection_batch_id).status = 'LOCKED'
        db.get(AaTextbookOrderItem, item_ids[2]).arrived_qty = 1
        db.commit()
    body.update(classId=str(other_class_id), studentIds=[str(outsider_id)])
    response = generate()
    assert response.status_code == 200, response.text
    assert response.json()['data']['recordCount'] == 1

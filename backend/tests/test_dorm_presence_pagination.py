"""归寝默认源：真实 MySQL 分页、状态口径与查询数量回归。"""
from datetime import datetime, timedelta


def test_none_presence_paginates_before_reading_students_and_preserves_leave_truth(db_mode, monkeypatch):
    from sqlalchemy import event
    from app.core.context import set_tenant
    from app.db.session import get_engine, get_sessionmaker
    from app.models import CsLeave, DormBed, DormBuilding, DormRoom, StudentProfile
    from app.services import affairs_dorm_service as dorm, dorm_presence_service as presence
    tid = 1000000000000000001
    set_tenant(tid)
    now = datetime(2026, 9, 13, 12)
    monkeypatch.setattr(presence, '_policy', lambda: dict(presence.DEFAULT_POLICY))
    scope = [None]
    monkeypatch.setattr(dorm, '_dorm_scope_building_ids', lambda db, user: scope[0])
    with get_sessionmaker()() as db:
        building = DormBuilding(tenant_id=tid, building_name='分页楼')
        db.add(building); db.flush()
        room = DormRoom(tenant_id=tid, building_id=building.id, floor_no=1, room_no='101', capacity=61)
        db.add(room); db.flush()
        students = [StudentProfile(tenant_id=tid, student_no=f'PERF-{i:03}', real_name=f'分页学生{i}', status='ACTIVE') for i in range(61)]
        db.add_all(students); db.flush()
        db.add_all([DormBed(tenant_id=tid, building_id=building.id, room_id=room.id, bed_no=f'{i:03}', student_id=s.id, status='OCCUPIED') for i, s in enumerate(students)])
        for sid, tenant, state, end, deleted in [
            (students[0].id, tid, 'APPROVED', now + timedelta(hours=1), False),
            (students[0].id, tid, 'APPROVED', now + timedelta(hours=2), False),
            (students[1].id, tid, 'PENDING', now + timedelta(hours=2), False),
            (students[2].id, tid, 'APPROVED', now - timedelta(minutes=1), False),
            (students[3].id, tid + 1, 'APPROVED', now + timedelta(hours=2), False),
            (students[4].id, tid, 'APPROVED', now + timedelta(hours=2), True),
        ]:
            db.add(CsLeave(tenant_id=tenant, student_id=sid, leave_type='PERSONAL',
                           start_time=now-timedelta(hours=1), end_time=end, affairs_status=state,
                           status=state, is_deleted=deleted, apply_time=now-timedelta(days=1)))
        # Even a local bed pointing to a foreign student's ID must not expose that student.
        foreign = StudentProfile(tenant_id=tid + 1, student_no='OTHER-SCHOOL', real_name='外校', status='ACTIVE')
        db.add(foreign); db.flush()
        db.add(DormBed(tenant_id=tid, building_id=building.id, room_id=room.id, bed_no='999', student_id=foreign.id, status='OCCUPIED'))
        db.commit()
        first_id = str(students[0].id)
        building_id = building.id
    queries = []
    def record(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)
    engine = get_engine(); event.listen(engine, 'after_cursor_execute', record)
    try:
        first, total, counts = presence.list_presence({}, now=now, page=1, page_size=50)
        assert len(queries) == 2, '统计与当前页各一次读取，不能逐学生查询请假'
        second, total2, counts2 = presence.list_presence({}, now=now, page=2, page_size=50)
        assert total == total2 == 61 and len(first) == 50 and len(second) == 11
        assert not ({r['studentId'] for r in first} & {r['studentId'] for r in second})
        assert counts == counts2 and counts['ON_LEAVE'] == 1 and counts['UNKNOWN'] == 60
        selected, total3, _ = presence.list_presence({}, now=now, status='ON_LEAVE', page_size=1)
        assert total3 == 1 and selected[0]['studentId'] == first_id
        assert selected[0]['reason'] == 'APPROVED_LEAVE'
        with get_sessionmaker()() as db:
            expected = presence.evaluate_presence(db, student_id=int(first_id), building_id=building_id,
                                                  now=now, policy=presence.DEFAULT_POLICY)
            assert {key: selected[0][key] for key in expected} == expected
        empty, zero, all_counts = presence.list_presence({}, now=now, status='NOT_RETURNED')
        assert empty == [] and zero == 0 and all_counts['UNKNOWN'] == 60
        scope[0] = set()
        assert presence.list_presence({}, now=now)[1] == 0
        scope[0] = {building_id + 1}
        assert presence.list_presence({}, now=now)[1] == 0
    finally:
        event.remove(engine, 'after_cursor_execute', record)
        set_tenant(None)

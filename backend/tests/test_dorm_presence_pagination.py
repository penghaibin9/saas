"""归寝默认源：真实 MySQL 分页、状态口径与查询数量回归。"""
from datetime import datetime, timedelta
from collections import Counter


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


def test_manual_presence_batches_database_reads_without_changing_status_semantics(db_mode, monkeypatch):
    """已启用的数据库 Provider 不能随住校人数逐人读取请假和门禁。"""
    from sqlalchemy import event
    from app.core.context import set_tenant
    from app.db.session import get_engine, get_sessionmaker
    from app.models import CsLeave, DormAccessEvent, DormBed, DormBuilding, DormRoom, StudentProfile
    from app.services import affairs_dorm_service as dorm, dorm_presence_service as presence

    tid = 1000000000000000001
    now = datetime(2026, 9, 13, 15, 45)  # 上海时间 23:45，已过未归判定时点。
    policy = {**presence.DEFAULT_POLICY, "provider": "MANUAL"}
    set_tenant(tid)
    monkeypatch.setattr(presence, "_policy", lambda: policy)
    monkeypatch.setattr(dorm, "_dorm_scope_building_ids", lambda db, user: None)
    try:
        with get_sessionmaker()() as db:
            building = DormBuilding(tenant_id=tid, building_name="批量归寝楼")
            other_building = DormBuilding(tenant_id=tid, building_name="其他归寝楼")
            db.add_all([building, other_building]); db.flush()
            room = DormRoom(tenant_id=tid, building_id=building.id, floor_no=1, room_no="101", capacity=61)
            db.add(room); db.flush()
            students = [
                StudentProfile(tenant_id=tid, student_no=f"BATCH-{index:03}",
                               real_name=f"批量归寝学生{index}", status="ACTIVE")
                for index in range(7)
            ]
            db.add_all(students); db.flush()
            db.add_all([
                DormBed(tenant_id=tid, building_id=building.id, room_id=room.id,
                        bed_no=f"{index:03}", student_id=student.id, status="OCCUPIED")
                for index, student in enumerate(students)
            ])

            def add_event(student, event_id, event_type, event_time, *, result="SUCCESS",
                          event_building_id=None, event_tenant_id=None, deleted=False):
                db.add(DormAccessEvent(
                    tenant_id=event_tenant_id or tid, provider="MANUAL", provider_event_id=event_id,
                    student_id=student.id, building_id=event_building_id or building.id,
                    event_type=event_type, event_time=event_time, result=result, is_deleted=deleted,
                ))

            # 请假优先、按时入寝、晚归、未归、失败事件回退至此前成功事件、同秒用 id 决胜，
            # 以及无可用事件（异楼栋/跨租户/逻辑删除均不能混入）。
            db.add_all([
                CsLeave(tenant_id=tid, student_id=students[0].id, leave_type="PERSONAL",
                        start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1),
                        affairs_status="APPROVED", status="APPROVED", apply_time=now - timedelta(days=1)),
                CsLeave(tenant_id=tid, student_id=students[0].id, leave_type="PERSONAL",
                        start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=2),
                        affairs_status="APPROVED", status="APPROVED", apply_time=now - timedelta(days=1)),
            ])
            add_event(students[0], "BATCH-LEAVE-OUT", "OUT", now - timedelta(hours=2))
            add_event(students[1], "BATCH-IN", "IN", now - timedelta(hours=1, minutes=45))
            add_event(students[2], "BATCH-LATE", "IN", now - timedelta(minutes=55))
            add_event(students[3], "BATCH-OUT", "OUT", now - timedelta(hours=2))
            add_event(students[4], "BATCH-OLD-SUCCESS", "IN", now - timedelta(hours=1, minutes=45))
            add_event(students[4], "BATCH-NEW-FAILED", "OUT", now - timedelta(minutes=55), result="FAILED")
            same_time = now - timedelta(hours=1, minutes=45)
            add_event(students[5], "BATCH-TIE-IN", "IN", same_time)
            db.flush()
            add_event(students[5], "BATCH-TIE-OUT", "OUT", same_time)
            add_event(students[6], "BATCH-WRONG-BUILDING", "IN", now - timedelta(minutes=30),
                      event_building_id=other_building.id)
            add_event(students[6], "BATCH-OTHER-TENANT", "OUT", now - timedelta(minutes=30),
                      event_tenant_id=tid + 1)
            add_event(students[6], "BATCH-DELETED", "IN", now - timedelta(minutes=30), deleted=True)
            db.commit()
            student_ids = [int(student.id) for student in students]
            building_id = int(building.id)
            room_id = int(room.id)

        def expected_for(student_ids, building_id):
            with get_sessionmaker()() as db:
                return {
                    str(student_id): presence.evaluate_presence(
                        db, student_id=student_id, building_id=building_id,
                        now=now, policy=policy,
                    )
                    for student_id in student_ids
                }

        def measure(page=1, page_size=50, status=None):
            statements = []
            def record(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)
            engine = get_engine()
            event.listen(engine, "after_cursor_execute", record)
            try:
                result = presence.list_presence({}, now=now, page=page, page_size=page_size, status=status)
            finally:
                event.remove(engine, "after_cursor_execute", record)
            return result, statements

        baseline_expected = expected_for(student_ids, building_id)
        (baseline_items, baseline_total, baseline_counts), baseline_selects = measure(page_size=50)
        assert len(baseline_selects) <= 3
        assert baseline_total == 7
        baseline_status_counts = Counter(row["status"] for row in baseline_expected.values())
        assert baseline_counts == {
            key: int(baseline_status_counts.get(key, 0)) for key in presence.PRESENCE_STATUSES
        }
        baseline_actual = {row["studentId"]: row for row in baseline_items}
        for student_id, expected_row in baseline_expected.items():
            if student_id in baseline_actual:
                assert {key: baseline_actual[student_id][key] for key in expected_row} == expected_row

        # 从 7 人扩到 61 人；数据库往返不能随住校人数线性增长。
        with get_sessionmaker()() as db:
            expanded_students = [
                StudentProfile(tenant_id=tid, student_no=f"BATCH-{index:03}",
                               real_name=f"批量归寝学生{index}", status="ACTIVE")
                for index in range(7, 61)
            ]
            db.add_all(expanded_students); db.flush()
            expanded_student_ids = [int(student.id) for student in expanded_students]
            db.add_all([
                DormBed(tenant_id=tid, building_id=building_id, room_id=room_id,
                        bed_no=f"{index:03}", student_id=student_id, status="OCCUPIED")
                for index, student_id in enumerate(expanded_student_ids, start=7)
            ])
            for index, student_id in enumerate(expanded_student_ids, start=7):
                db.add(DormAccessEvent(
                    tenant_id=tid, provider="MANUAL", provider_event_id=f"BATCH-EXPAND-{index:03}",
                    student_id=student_id, building_id=building_id, event_type="IN",
                    event_time=now - timedelta(hours=1, minutes=45), result="SUCCESS",
                ))
            db.commit()
        student_ids.extend(expanded_student_ids)

        expected = expected_for(student_ids, building_id)
        (items, total, counts), expanded_selects = measure(page=1, page_size=50)
        assert len(expanded_selects) == len(baseline_selects) <= 3
        assert total == 61 and len(items) == 50
        expected_counts = Counter(row["status"] for row in expected.values())
        assert counts == {key: int(expected_counts.get(key, 0)) for key in presence.PRESENCE_STATUSES}
        actual = {row["studentId"]: row for row in items}
        for student_id, expected_row in expected.items():
            if student_id in actual:
                assert {key: actual[student_id][key] for key in expected_row} == expected_row
        assert expected[str(student_ids[0])]["status"] == "ON_LEAVE"
        assert expected[str(student_ids[4])]["status"] == "IN_DORM"
        assert expected[str(student_ids[5])]["status"] == "NOT_RETURNED"
        assert expected[str(student_ids[6])]["reason"] == "NO_USABLE_EVENT"

        (second_page, page_total, page_counts), _ = measure(page=2, page_size=50)
        assert page_total == total and page_counts == counts and len(second_page) == 11
        assert not ({row["studentId"] for row in items} & {row["studentId"] for row in second_page})
        (not_returned, filtered_total, filtered_counts), _ = measure(status="NOT_RETURNED", page_size=10)
        assert filtered_total == counts["NOT_RETURNED"] == 2
        assert filtered_counts == counts
        assert {row["studentId"] for row in not_returned} == {str(student_ids[3]), str(student_ids[5])}
    finally:
        set_tenant(None)

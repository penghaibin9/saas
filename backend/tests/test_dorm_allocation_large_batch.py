"""Isolated 2000/5000-student allocation and reservation capacity acceptance."""
from collections import defaultdict
from time import perf_counter

from sqlalchemy import event, select

from tests.test_dorm_d3_allocation import BASE, TID, _admin, _create, _seed_authorities


def test_two_thousand_students_ten_buildings_real_dry_run(client, db_mode):
    _run_large_batch(client, total=2000, building_count=10, male_buildings=6)


def test_five_thousand_students_real_dry_run_and_publish(client, db_mode):
    _run_large_batch(client, total=5000, building_count=25, male_buildings=15)


def _run_large_batch(client, *, total, building_count, male_buildings):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormAllocationItem, DormBed, DormBuilding, DormRoom, SchoolClass, StudentProfile

    seeded = _seed_authorities(students=total, beds=1)
    headers = _admin(client)
    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", str(total))
    with get_sessionmaker()() as db:
        building_ids = []
        for index in range(building_count):
            if index == 0:
                building = db.get(DormBuilding, seeded["buildingId"])
                building.floor_count = 5
            else:
                building = DormBuilding(tenant_id=TID, building_name=f"大批次楼{index + 1}",
                    building_code=f"LARGE-{index + 1}", floor_count=5, status="ENABLED",
                    gender_limit="MALE" if index < male_buildings else "FEMALE")
                db.add(building); db.flush()
            building_ids.append(building.id)
            for room_index in range(50):
                if index == 0 and room_index == 0:
                    room = db.get(DormRoom, seeded["roomId"])
                    room.capacity = 4
                    first_bed = 2
                else:
                    room = DormRoom(tenant_id=TID, building_id=building.id,
                        floor_no=room_index // 10 + 1, room_no=f"{room_index // 10 + 1}{room_index % 10 + 1:02d}",
                        capacity=4, room_type="STANDARD", status="ENABLED")
                    db.add(room); db.flush(); first_bed = 1
                for bed_no in range(first_bed, 5):
                    db.add(DormBed(tenant_id=TID, building_id=building.id, room_id=room.id,
                                  bed_no=str(bed_no), status="VACANT"))
        profiles = db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([row[0] for row in seeded["students"]])).order_by(StudentProfile.id)).all()
        for index in range(total // 40):
            school_class = SchoolClass(tenant_id=TID, major_id=1, class_name=f"规模验收{index + 1:02d}班",
                                      grade="2026", status="ACTIVE", class_status="NORMAL")
            db.add(school_class); db.flush()
            for student in profiles[index * 40:(index + 1) * 40]:
                student.class_id = school_class.id
                student.gender = "M" if index < male_buildings * 5 else "F"
        batch = db.get(DormAllocationBatch, int(batch_id))
        batch.resource_scope_json = {"buildingIds": building_ids}
        batch.rules_json = {"sameClass": True, "minimizeVacancy": True}
        db.commit()
        engine = db.get_bind()
    counts = defaultdict(int)

    def track(_conn, _cursor, statement, _parameters, _context, _executemany):
        counts[statement.lstrip().split(None, 1)[0].upper()] += 1

    event.listen(engine, "before_cursor_execute", track)
    started = perf_counter()
    try:
        response = client.post(f"{BASE}/{batch_id}/dry-run", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", track)
    elapsed = perf_counter() - started
    assert response.status_code == 200, response.text
    summary = response.json()["data"]["summary"]
    assert summary["proposed"] == total and summary["unassigned"] == 0
    assert counts["SELECT"] < 150, dict(counts)
    with get_sessionmaker()() as db:
        rows = db.execute(select(DormAllocationItem, StudentProfile, DormBed, DormRoom, DormBuilding)
            .join(StudentProfile, StudentProfile.id == DormAllocationItem.student_id)
            .join(DormBed, DormBed.id == DormAllocationItem.bed_id)
            .join(DormRoom, DormRoom.id == DormBed.room_id)
            .join(DormBuilding, DormBuilding.id == DormBed.building_id)
            .where(DormAllocationItem.allocation_batch_id == int(batch_id))).all()
        assert len(rows) == len({row[0].student_id for row in rows}) == len({row[0].bed_id for row in rows}) == total
        floors = defaultdict(set)
        for item, student, bed, room, building in rows:
            assert item.status == "PROPOSED" and bed.status == "VACANT" and bed.student_id is None
            assert building.gender_limit == ("MALE" if student.gender == "M" else "FEMALE")
            floors[student.class_id].add((building.id, room.floor_no))
        assert len(floors) == total // 40 and all(len(value) == 1 for value in floors.values())
    print(f"LARGE_BATCH students={total} buildings={building_count} beds={total} classes={total // 40} seconds={elapsed:.3f} sql={dict(counts)}")
    started = perf_counter()
    published = client.post(f"{BASE}/{batch_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    print(f"LARGE_PUBLISH students={total} seconds={perf_counter() - started:.3f}")
    from app.models import DormStay, OrientationStudent
    with get_sessionmaker()() as db:
        items = db.scalars(select(DormAllocationItem).where(
            DormAllocationItem.allocation_batch_id == int(batch_id))).all()
        stays = db.scalars(select(DormStay).where(DormStay.student_id.in_(
            [row[0] for row in seeded["students"]]))).all()
        assert len(stays) == total and {row.status for row in stays} == {"RESERVED"}
        assert len({row.bed_id for row in stays}) == len({row.student_id for row in stays}) == total
        assert all(row.checkin_at is None for row in stays)
        assert {row.status for row in items} == {"RESERVED"}
        beds = db.scalars(select(DormBed).where(DormBed.id.in_([row.bed_id for row in items]))).all()
        assert len(beds) == total and all(row.status == "LOCKED" and row.student_id is None for row in beds)
        orientation = db.scalars(select(OrientationStudent).where(
            OrientationStudent.batch_id == seeded["orientationBatchId"])).all()
        assert len(orientation) == total and all(row.dorm_status == "ASSIGNED" for row in orientation)

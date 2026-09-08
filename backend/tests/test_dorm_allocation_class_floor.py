from tests.test_dorm_d3_allocation import BASE, TID, _admin, _create, _seed_authorities


def test_real_dry_run_keeps_class_on_manual_assignment_floor(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormBed, DormRoom
    seeded = _seed_authorities(students=4, beds=1)
    headers = _admin(client)
    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", "CLASS-FLOOR")
    with get_sessionmaker()() as db:
        batch = db.get(DormAllocationBatch, int(batch_id))
        batch.rules_json = {"sameClass": True, "sameMajor": True, "minimizeVacancy": True}
        rooms = []
        # Lower IDs deliberately belong to the wrong floor.
        for floor, number in ((2, "201"), (1, "102")):
            room = DormRoom(tenant_id=TID, building_id=seeded["buildingId"],
                            floor_no=floor, room_no=number, capacity=3,
                            room_type="STANDARD", status="ENABLED")
            db.add(room); db.flush(); rooms.append(room.id)
            for number in range(1, 4):
                db.add(DormBed(tenant_id=TID, building_id=seeded["buildingId"],
                               room_id=room.id, bed_no=str(number), status="VACANT"))
        db.commit()
    manual = client.post(f"{BASE}/{batch_id}/manual-assign", headers=headers, json={
        "studentId": str(seeded["students"][0][0]), "bedId": str(seeded["bedIds"][0])})
    assert manual.status_code == 200, manual.text
    result = client.post(f"{BASE}/{batch_id}/dry-run", headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["summary"]["proposed"] == 4
    items = client.get(f"{BASE}/{batch_id}", headers=headers).json()["data"]["items"]
    assert len({item["bedId"] for item in items}) == 4
    auto = [item for item in items if item["source"] == "AUTO"]
    with get_sessionmaker()() as db:
        assert {db.get(DormBed, int(item["bedId"])).room_id for item in auto} == {rooms[1]}

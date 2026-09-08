"""Regeneration preserves a deliberate manual bed and refuses stale proposals."""
from tests.test_dorm_d3_allocation import BASE, _admin, _create, _seed_authorities


def test_regeneration_keeps_manual_bed_and_rejects_stale_resource(client, db_mode):
    seeded = _seed_authorities(students=2, beds=3)
    headers = _admin(client)
    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", "PRESERVE")
    student_id = seeded["students"][0][0]
    bed_id = seeded["bedIds"][2]
    response = client.post(f"{BASE}/{batch_id}/manual-assign", headers=headers,
                           json={"studentId": str(student_id), "bedId": str(bed_id)})
    assert response.status_code == 200, response.text
    for _ in range(2):
        response = client.post(f"{BASE}/{batch_id}/dry-run", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["summary"]["preservedManual"] == 1
        assert response.json()["data"]["summary"]["proposed"] == 2
        detail = client.get(f"{BASE}/{batch_id}", headers=headers).json()["data"]
        assert detail["capacity"]["totalDemand"] == 2
        assert detail["capacity"]["availableBeds"] == 3
        manual = next(item for item in detail["items"] if item["studentId"] == str(student_id))
        assert manual["bedId"] == str(bed_id) and manual["source"] == "MANUAL"
        assert len({item["bedId"] for item in detail["items"]}) == 2

    from app.db.session import get_sessionmaker
    from app.models import DormBed, DormAllocationItem
    with get_sessionmaker()() as db:
        db.get(DormBed, bed_id).status = "LOCKED"
        db.commit()
    response = client.post(f"{BASE}/{batch_id}/dry-run", headers=headers)
    assert response.status_code == 409, response.text
    assert "人工安排" in response.text
    with get_sessionmaker()() as db:
        item = db.query(DormAllocationItem).filter_by(
            allocation_batch_id=int(batch_id), student_id=student_id).one()
        assert item.bed_id == bed_id and item.source == "MANUAL" and item.status == "PROPOSED"

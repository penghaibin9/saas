from tests.test_dorm_d3_allocation import BASE, _admin, _create, _seed_authorities


def test_publish_rechecks_changed_student_gender_and_bed_pool(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormAllocationBatch, DormBed, DormBuilding, DormStay, OrientationStudent
    seeded = _seed_authorities(students=2, beds=3)
    headers = _admin(client)
    batch_id = _create(client, headers, seeded, "ADMIN_AUTO", "REVALIDATE")
    assert client.post(f"{BASE}/{batch_id}/dry-run", headers=headers).status_code == 200
    changes = [(OrientationStudent, seeded["orientationStudents"][0], "stage", "CANCELLED"),
               (DormBuilding, seeded["buildingId"], "gender_limit", "FEMALE"),
               (DormBed, seeded["bedIds"][0], "status", "LOCKED")]
    for model, row_id, field, value in changes:
        with get_sessionmaker()() as db:
            row = db.get(model, row_id)
            before = getattr(row, field)
            setattr(row, field, value)
            db.commit()
        response = client.post(f"{BASE}/{batch_id}/publish", headers=headers)
        assert response.status_code == 409, response.text
        with get_sessionmaker()() as db:
            assert db.get(DormAllocationBatch, int(batch_id)).status == "DRAFT"
            assert db.query(DormStay).filter(DormStay.student_id.in_(
                [s[0] for s in seeded["students"]])).count() == 0
            setattr(db.get(model, row_id), field, before)
            db.commit()
    result = client.post(f"{BASE}/{batch_id}/publish", headers=headers)
    assert result.status_code == 200, result.text
    published_version = result.json()["data"]["version"]
    repeated = client.post(f"{BASE}/{batch_id}/publish", headers=headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["data"]["version"] == published_version
    with get_sessionmaker()() as db:
        assert db.query(DormStay).filter(DormStay.student_id.in_(
            [s[0] for s in seeded["students"]])).count() == 2

"""A student's review workspace must never show another new student's materials."""
from test_dorm_d3_allocation import TID, _admin, _seed_authorities


def test_material_student_filter_applies_before_count_and_pagination(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationMaterial

    seeded = _seed_authorities(students=2, beds=1)
    first, second = seeded["orientationStudents"]
    with get_sessionmaker()() as db:
        for ori_id, (student_id, *_rest) in zip(
            seeded["orientationStudents"], seeded["students"]
        ):
            db.add(OrientationMaterial(tenant_id=TID, ori_student_id=ori_id,
                student_id=student_id, material_type="ID_CARD", status="UPLOADED",
                file_name=f"material-{ori_id}.pdf", is_current=True))
        db.commit()
    headers = _admin(client)

    def query(**params):
        response = client.get("/api/v1/orientation/materials", headers=headers, params=params)
        assert response.status_code == 200, response.text
        return response.json()["data"]

    assert query(batchId=seeded["orientationBatchId"])["total"] == 2
    for ori_id in (first, second):
        result = query(orientationStudentId=ori_id, pageSize=1)
        assert result["total"] == 1
        assert [row["fileName"] for row in result["items"]] == [f"material-{ori_id}.pdf"]
    assert query(orientationStudentId=first, batchId=seeded["orientationBatchId"] + 1)["total"] == 0

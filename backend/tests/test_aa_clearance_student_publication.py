"""Student clearance results use published formal grades, never raw exam input."""
import pytest
from sqlalchemy import event

from tests.test_aa_clearance import BASE, TID, _create_batch, _hdr, _seed, _stu_token

STUDENT_PATHS = ["/api/v1/mobile/academic/clearance/my", "/api/v1/portal/academic/clearance"]


def _assert_result(client, headers, score, record_id=None):
    for path in STUDENT_PATHS:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()["data"]
        assert payload["total"] == 1, payload
        row = payload["items"][0]
        assert row["score"] == score, row
        assert row["originScore"] == 55
        if record_id is not None:
            assert row["recordId"] == str(record_id)


def _arrange(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    batch_id = _create_batch(client, admin)
    scan = client.post(f"{BASE}/makeup/clearance/batches/{batch_id}/scan", headers=admin)
    assert scan.status_code == 200, scan.text
    response = client.get(f"{BASE}/makeup/clearance/batches/{batch_id}/records", headers=admin)
    assert response.status_code == 200, response.text
    record_id = int(response.json()["data"]["items"][0]["makeupId"])
    return ids, admin, int(batch_id), record_id


def _post(client, admin, path, body=None):
    response = client.post(f"{BASE}{path}", headers=admin, json=body)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("raw_score,published_score", [(88, 60), (40, 40), (0, 0)])
def test_both_student_endpoints_wait_for_finish_and_use_formal_score(client, db_mode, raw_score, published_score):
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicMakeup

    ids, admin, bid, mid = _arrange(client, db_mode)
    student = _stu_token("清甲", "QK2201")
    _assert_result(client, student, None, mid)
    _post(client, admin, f"/makeup/batches/{bid}/publish")
    _assert_result(client, student, None, mid)
    _post(client, admin, f"/makeup/records/{mid}/score", {"score": raw_score})
    _assert_result(client, student, None, mid)
    _post(client, admin, f"/makeup/batches/{bid}/college-review")
    _assert_result(client, student, None, mid)
    _post(client, admin, f"/makeup/batches/{bid}/finish")
    _assert_result(client, student, published_score, mid)
    with get_sessionmaker()() as db:
        record = db.get(AcademicMakeup, mid)
        assert record.final_score == raw_score
        grade = db.query(AcademicGrade).filter_by(
            tenant_id=TID, acad_student_id=ids["a1"],
            source_biz_type="CLEARANCE", source_biz_id=mid, is_deleted=False,
        ).one()
        assert grade.score == published_score


def test_invalid_or_unresolved_formal_sources_never_fall_back_to_raw_score(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaMakeupBatch, AcademicGrade, AcademicMakeup, AcademicStudent

    ids, admin, bid, mid = _arrange(client, db_mode)
    student = _stu_token("清甲", "QK2201")
    _post(client, admin, f"/makeup/batches/{bid}/publish")
    _post(client, admin, f"/makeup/records/{mid}/score", {"score": 88})
    _post(client, admin, f"/makeup/batches/{bid}/college-review")
    _post(client, admin, f"/makeup/batches/{bid}/finish")
    with get_sessionmaker()() as db:
        grade_id = db.query(AcademicGrade.id).filter_by(
            tenant_id=TID, source_biz_type="CLEARANCE", source_biz_id=mid,
        ).one()[0]
        other_student_id = db.query(AcademicStudent.id).filter_by(tenant_id=TID, student_no="QK2202").one()[0]
    cases = [
        (AaMakeupBatch, bid, "status", "REVIEWED"),
        (AaMakeupBatch, bid, "kind", "MAKEUP"),
        (AaMakeupBatch, bid, "is_deleted", True),
        (AaMakeupBatch, bid, "tenant_id", TID + 1),
        (AcademicMakeup, mid, "status", "SCORED"),
        (AcademicMakeup, mid, "record_status", "VOID"),
        (AcademicMakeup, mid, "batch_id", None),
        (AcademicGrade, grade_id, "record_status", "VOID"),
        (AcademicGrade, grade_id, "is_deleted", True),
        (AcademicGrade, grade_id, "tenant_id", TID + 1),
        (AcademicGrade, grade_id, "acad_student_id", other_student_id),
        (AcademicGrade, grade_id, "source_biz_type", "MAKEUP"),
        (AcademicGrade, grade_id, "source_biz_id", mid + 100000),
        (AcademicGrade, grade_id, "course_id", ids["english"]),
    ]
    for model, object_id, field, value in cases:
        with get_sessionmaker()() as db:
            obj = db.get(model, object_id)
            old = getattr(obj, field)
            setattr(obj, field, value)
            db.commit()
        try:
            _assert_result(client, student, None, mid)
        finally:
            with get_sessionmaker()() as db:
                setattr(db.get(model, object_id), field, old)
                db.commit()
    _assert_result(client, student, 60, mid)
    for path in STUDENT_PATHS:
        other = client.get(path, headers=_stu_token("清乙", "QK2202"))
        assert other.status_code == 200, other.text
        assert other.json()["data"]["items"] == []
        assert client.get(path, headers=admin).status_code == 403


def test_published_projection_batches_grade_read_without_business_writes(client, db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaMakeupBatch, AcademicGrade, AcademicMakeup

    ids, admin, bid, mid = _arrange(client, db_mode)
    _post(client, admin, f"/makeup/batches/{bid}/publish")
    _post(client, admin, f"/makeup/records/{mid}/score", {"score": 88})
    _post(client, admin, f"/makeup/batches/{bid}/college-review")
    _post(client, admin, f"/makeup/batches/{bid}/finish")
    with get_sessionmaker()() as db:
        source = db.get(AcademicMakeup, mid)
        for attempt in range(10, 30):
            record = AcademicMakeup(
                tenant_id=TID, acad_student_id=ids["a1"], batch_id=bid,
                course_id=ids["math"], course_code=source.course_code,
                course_version=source.course_version, course_name=source.course_name,
                attempt_no=attempt, kind="CLEARANCE", status="FINISHED", record_status="ACTIVE",
                final_score=88, origin_score=55,
            )
            db.add(record); db.flush()
            db.add(AcademicGrade(
                tenant_id=TID, acad_student_id=ids["a1"], course_id=ids["math"],
                course_name=source.course_name, source_biz_type="CLEARANCE", source_biz_id=record.id,
                score=60, source="CLEARANCE", record_status="ACTIVE",
            ))
        db.commit()
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if "t_acad_grade" in statement or "t_acad_makeup" in statement or AaMakeupBatch.__tablename__ in statement:
            statements.append(statement.strip().upper())
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(STUDENT_PATHS[0], headers=_stu_token("清甲", "QK2201"))
        assert response.status_code == 200, response.text
        rows = response.json()["data"]["items"]
        assert len(rows) == 21 and all(row["score"] == 60 for row in rows)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert sum(s.startswith("SELECT") and "FROM T_ACAD_GRADE" in s for s in statements) == 1
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)

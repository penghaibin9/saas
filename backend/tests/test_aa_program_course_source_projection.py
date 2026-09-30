"""Program detail must link the stored course version without name matching or tenant leaks."""
from decimal import Decimal

from sqlalchemy import event

from app.db.session import get_engine, get_sessionmaker
from app.models import AaCourse, AaProgram, AaProgramCourse

BASE = "/api/v1/academic-affairs"
TENANT_ID = 1000000000000000001


def _headers(client, login_name="school_admin01"):
    response = client.post("/api/v1/auth/mock-login", json={
        "loginName": login_name, "password": "any",
    })
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}


def _program(db, **kwargs):
    row = AaProgram(tenant_id=TENANT_ID, program_name="来源核验方案", **kwargs)
    db.add(row)
    db.flush()
    return row


def _course(db, code, **kwargs):
    values = {"tenant_id": TENANT_ID, "course_name": "同名课程", "credit": 8}
    values.update(kwargs)
    row = AaCourse(course_code=code, **values)
    db.add(row)
    db.flush()
    return row


def _link(db, program, course_id, **kwargs):
    row = AaProgramCourse(
        tenant_id=TENANT_ID, program_id=program.id, course_id=course_id,
        course_name="方案原课程名", credit_snapshot=Decimal("2.5"), **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def test_detail_uses_exact_version_and_preserves_program_snapshot(client, db_mode):
    with get_sessionmaker()() as db:
        program = _program(db, total_credits=10)
        old = _course(db, "SOURCE-A", version=1, status="DISABLED",
                      nature="ELECTIVE", hours_total=32)
        _course(db, "SOURCE-A", version=2, status="ENABLED", hours_total=64)
        same_name = _course(db, "SOURCE-B", version=1, hours_total=48)
        first = _link(db, program, old.id, open_term_no=1, module="专业")
        second = _link(db, program, same_name.id, open_term_no=2)
        db.commit()
        pid, old_id, other_id = program.id, old.id, same_name.id
        first_id, second_id = first.id, second.id

    response = client.get(f"{BASE}/programs/{pid}", headers=_headers(client))
    assert response.status_code == 200
    detail = response.json()["data"]
    rows = {row["programCourseId"]: row for row in detail["courses"]}
    assert rows[str(first_id)] == {
        "programCourseId": str(first_id), "courseName": "方案原课程名",
        "openTermNo": 1, "module": "专业", "credit": 2.5, "formationMode": None,
        "courseId": str(old_id), "courseCode": "SOURCE-A", "courseVersion": 1,
        "nature": "ELECTIVE", "hoursTotal": 32,
    }
    assert rows[str(second_id)]["courseId"] == str(other_id)
    assert rows[str(second_id)]["courseCode"] == "SOURCE-B"
    assert detail["creditSum"] == 5 and detail["creditGap"] == 5


def test_unresolved_sources_stay_null_without_leaking_or_name_fallback(client, db_mode):
    with get_sessionmaker()() as db:
        program = _program(db)
        _course(db, "NAME-MATCH", course_name="方案原课程名")
        deleted = _course(db, "DELETED", is_deleted=True)
        foreign = _course(db, "OTHER-TENANT", tenant_id=TENANT_ID + 1)
        for index, course_id in enumerate([None, deleted.id, foreign.id, 999999999999999999]):
            _link(db, program, course_id, open_term_no=index + 1)
        db.commit()
        pid = program.id

    response = client.get(f"{BASE}/programs/{pid}", headers=_headers(client))
    assert response.status_code == 200
    rows = response.json()["data"]["courses"]
    assert len(rows) == 4
    for row in rows:
        assert row["courseName"] == "方案原课程名" and row["credit"] == 2.5
        assert all(row[key] is None for key in (
            "courseId", "courseCode", "courseVersion", "nature", "hoursTotal",
        ))


def test_many_sources_are_batched_and_program_tenant_boundary_remains(client, db_mode):
    with get_sessionmaker()() as db:
        one = _program(db)
        many = _program(db)
        foreign = AaProgram(tenant_id=TENANT_ID + 1, program_name="其他租户方案")
        db.add(foreign)
        for index in range(40):
            course = _course(db, f"BATCH-{index}")
            _link(db, many, course.id)
            if index == 0:
                _link(db, one, course.id)
        db.commit()
        one_id, many_id, foreign_id = one.id, many.id, foreign.id

    headers = _headers(client)
    queries = []

    def count_queries(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "from t_aa_course " in " ".join(statement.lower().split()):
            queries.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        response = client.get(f"{BASE}/programs/{one_id}", headers=headers)
        assert response.status_code == 200
        one_count = len(queries)
        queries.clear()
        response = client.get(f"{BASE}/programs/{many_id}", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["data"]["courses"]) == 40
        assert one_count == len(queries) == 1
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)

    denied = client.get(f"{BASE}/programs/{foreign_id}", headers=headers)
    assert denied.status_code == 404
    assert "其他租户方案" not in denied.text

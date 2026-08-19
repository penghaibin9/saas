"""D8-U2：成绩任务列表必须由 MySQL 分页，并保持教师 COURSE dataScope。"""
from __future__ import annotations

from sqlalchemy import event, inspect, text


BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_grade_deadline_schema() -> None:
    """Make create_all-backed regression DBs match the additive W4 migration.

    Grade deadline truth is intentionally migration-owned rather than mapped onto the
    shared AaGradeTask ORM in this C-line branch.  Full-regression FAST_TEST_SCHEMA uses
    ``metadata.create_all()`` instead of Alembic, so these two additive columns would be
    absent even though every real migrated installation has them.  Keep the pagination
    contract focused on pagination by applying the exact additive schema prerequisite in
    this legacy create_all-backed test database; migrated-schema gates still validate the
    actual Alembic revision and trigger separately.
    """
    from app.db.session import get_engine

    engine = get_engine()
    with engine.begin() as conn:
        columns = {row["name"] for row in inspect(conn).get_columns("t_aa_grade_task")}
        if "deadline_at" not in columns:
            conn.execute(text(
                "ALTER TABLE t_aa_grade_task ADD COLUMN deadline_at DATETIME NULL"
            ))
        if "deadline_updated_at" not in columns:
            conn.execute(text(
                "ALTER TABLE t_aa_grade_task ADD COLUMN deadline_updated_at DATETIME NULL"
            ))
        indexes = {row["name"] for row in inspect(conn).get_indexes("t_aa_grade_task")}
        if "ix_aa_grade_task_deadline" not in indexes:
            conn.execute(text(
                "CREATE INDEX ix_aa_grade_task_deadline "
                "ON t_aa_grade_task (tenant_id, status, deadline_at)"
            ))


def test_grade_task_admin_list_uses_sql_count_limit_offset(client, db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaGradeTask

    _ensure_grade_deadline_schema()
    db = get_sessionmaker()()
    baseline = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == TID,
        AaGradeTask.status == "NOT_STARTED",
        AaGradeTask.is_deleted.is_(False),
    ).count()
    rows = [
        AaGradeTask(
            tenant_id=TID,
            term_code="D8-U2-SCALE",
            course_name=f"成绩任务分页{index:04d}",
            teacher_key="academic01",
            status="NOT_STARTED",
        )
        for index in range(257)
    ]
    db.add_all(rows)
    db.commit()
    db.close()

    statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = str(statement).lower()
        if normalized.lstrip().startswith("select") and "t_aa_grade_task" in normalized:
            statements.append(normalized)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = client.get(
            f"{BASE}/grade-tasks",
            params={"status": "NOT_STARTED", "page": 3, "pageSize": 25},
            headers=_hdr(client, "school_admin01"),
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == baseline + 257
    assert data["page"] == 3 and data["pageSize"] == 25
    assert len(data["items"]) == 25
    # 新插入任务 ID 最大；第三页偏移 50 条后应从 index=206 开始，锁住 OFFSET 语义。
    assert data["items"][0]["courseName"] == "成绩任务分页0206"

    count_sql = [statement for statement in statements if "count(" in statement]
    page_sql = [statement for statement in statements if "order by" in statement]
    assert len(count_sql) == 1, statements
    assert len(page_sql) == 1, statements
    assert " limit " in page_sql[0].replace("\n", " "), page_sql[0]


def test_grade_task_teacher_scope_survives_sql_pagination(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask

    _ensure_grade_deadline_schema()
    db = get_sessionmaker()()
    own_keys = ["academic01", "u_academic01"]
    baseline_own = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == TID,
        AaGradeTask.status == "INPUTTING",
        AaGradeTask.teacher_key.in_(own_keys),
        AaGradeTask.is_deleted.is_(False),
    ).count()
    own = [
        AaGradeTask(
            tenant_id=TID,
            term_code="D8-U2-SCOPE",
            course_name=f"U2-OWN-{index:03d}",
            teacher_key="academic01",
            status="INPUTTING",
        )
        for index in range(40)
    ]
    other = [
        AaGradeTask(
            tenant_id=TID,
            term_code="D8-U2-SCOPE",
            course_name=f"U2-OTHER-{index:03d}",
            teacher_key="other_teacher",
            status="INPUTTING",
        )
        for index in range(40)
    ]
    db.add_all(own + other)
    db.commit()
    db.close()

    response = client.get(
        f"{BASE}/grade-tasks",
        params={"status": "INPUTTING", "page": 1, "pageSize": 100},
        headers=_hdr(client, "academic01"),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == baseline_own + 40
    assert any(item["courseName"].startswith("U2-OWN-") for item in data["items"])
    assert not any(item["courseName"].startswith("U2-OTHER-") for item in data["items"])

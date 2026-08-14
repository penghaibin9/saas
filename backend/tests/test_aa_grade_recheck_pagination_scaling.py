"""D8-U3：成绩复查台账必须由 MySQL 分页，并保持教务处 TENANT_ALL 门禁。"""
from __future__ import annotations

from sqlalchemy import event


BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_grade_recheck_admin_list_uses_sql_count_limit_offset(client, db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaGradeRecheck

    db = get_sessionmaker()()
    baseline = db.query(AaGradeRecheck).filter(
        AaGradeRecheck.tenant_id == TID,
        AaGradeRecheck.status == "SUBMITTED",
        AaGradeRecheck.is_deleted.is_(False),
    ).count()
    rows = [
        AaGradeRecheck(
            tenant_id=TID,
            student_id=800000 + index,
            student_no=f"U3{index:06d}",
            student_name=f"复查学生{index:03d}",
            acad_grade_id=900000 + index,
            course_name=f"U3-RECHECK-{index:03d}",
            term="2026-2027-1",
            original_score=50 + (index % 10),
            reason="成绩复查分页规模合同",
            status="SUBMITTED",
        )
        for index in range(257)
    ]
    db.add_all(rows)
    db.commit()
    db.close()

    statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = str(statement).lower()
        if normalized.lstrip().startswith("select") and "t_aa_grade_recheck" in normalized:
            statements.append(normalized)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = client.get(
            f"{BASE}/grade-rechecks",
            params={"status": "SUBMITTED", "page": 3, "pageSize": 25},
            headers=_hdr(client, "school_admin01"),
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == baseline + 257
    assert data["page"] == 3 and data["pageSize"] == 25
    assert len(data["items"]) == 25
    # 新插入 ID 最大；第三页偏移 50 条后应从 index=206 开始，锁住 ORDER BY id DESC + OFFSET 语义。
    assert data["items"][0]["courseName"] == "U3-RECHECK-206"

    count_sql = [statement for statement in statements if "count(" in statement]
    page_sql = [statement for statement in statements if "order by" in statement]
    assert len(count_sql) == 1, statements
    assert len(page_sql) == 1, statements
    assert " limit " in page_sql[0].replace("\n", " "), page_sql[0]


def test_grade_recheck_admin_list_keeps_schoolwide_scope_guard(client, db_mode):
    response = client.get(
        f"{BASE}/grade-rechecks",
        params={"page": 1, "pageSize": 20},
        headers=_hdr(client, "academic01"),
    )
    assert response.status_code == 403, response.text

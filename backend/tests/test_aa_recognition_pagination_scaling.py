"""D8-U：成绩认定管理列表必须由 MySQL 分页，禁止全租户 materialize 后 Python 切片。"""
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


def test_recognition_admin_list_uses_sql_count_limit_offset(client, db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaGradeRecognition

    db = get_sessionmaker()()
    baseline = db.query(AaGradeRecognition).filter(
        AaGradeRecognition.tenant_id == TID,
        AaGradeRecognition.status == "SUBMITTED",
        AaGradeRecognition.is_deleted.is_(False),
    ).count()
    rows = [
        AaGradeRecognition(
            tenant_id=TID,
            student_id=910000 + index,
            student_no=f"PG{index:04d}",
            student_name=f"分页学生{index:04d}",
            source_course_name="外校课程",
            source_score=80,
            target_course_name="目标课程",
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
        if normalized.lstrip().startswith("select") and "t_aa_grade_recognition" in normalized:
            statements.append(normalized)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = client.get(
            f"{BASE}/grade-recognitions",
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
    # 新插入记录 ID 最大，第三页偏移 50 条后应从 PG0206 开始；锁住 OFFSET 语义而非只看 LIMIT。
    assert data["items"][0]["studentNo"] == "PG0206"
    assert all(item["status"] == "SUBMITTED" for item in data["items"])

    count_sql = [statement for statement in statements if "count(" in statement]
    page_sql = [statement for statement in statements if "order by" in statement]
    assert len(count_sql) == 1, statements
    assert len(page_sql) == 1, statements
    assert " limit " in page_sql[0].replace("\n", " "), page_sql[0]

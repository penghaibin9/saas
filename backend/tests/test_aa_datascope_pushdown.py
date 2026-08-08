"""数据范围过滤下推到 SQL WHERE（P1 批次C·性能）。

`academic_affairs_textbook_service.list_selections()` 和
`academic_affairs_exam_service.list_courses()` 原实现对非学校级角色，先把整租户/
整批次的全部行查出来，再在 Python 里按 college_ids 过滤、按页码切片——学院教务员
只该看到自己学院的记录，却要为此让数据库把全部记录先搬进应用内存一遍，分页也是
切片假分页。改为直接把学院范围条件和分页下推到 SQL WHERE/OFFSET/LIMIT。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_textbook_selection_list_pagination_uses_real_sql_limit(client, db_mode):
    """25 条选用记录，只取第 1 页 10 条：底层 SELECT 必须带 LIMIT，且 3 页合计不重不漏。"""
    from sqlalchemy import event

    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaTextbookSelection

    db = get_sessionmaker()()
    for i in range(25):
        db.add(AaTextbookSelection(
            tenant_id=TID, task_id=1, textbook_id=1, expected_qty=10,
            status="APPROVED", college_id=None,
        ))
    db.commit()
    db.close()

    hdr = _hdr(client, "school_admin01")
    engine = get_engine()
    statements = []

    def _hook(_conn, _cursor, statement, *_a, **_kw):
        if statement.strip().upper().startswith("SELECT") and "t_aa_textbook_selection" in statement.lower():
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _hook)
    try:
        seen_ids = set()
        total_reported = None
        for page in (1, 2, 3):
            r = client.get(f"{BASE}/textbooks/selections", headers=hdr,
                           params={"status": "APPROVED", "page": page, "pageSize": 10})
            assert r.status_code == 200, r.text
            data = r.json()["data"]
            total_reported = data["total"]
            for item in data["items"]:
                assert item["selectionId"] not in seen_ids
                seen_ids.add(item["selectionId"])
    finally:
        event.remove(engine, "before_cursor_execute", _hook)

    assert total_reported == 25
    assert len(seen_ids) == 25
    assert any("LIMIT" in s.upper() for s in statements), (
        f"取选用列表的 SELECT 里必须有 LIMIT 子句，实际语句：{statements}"
    )


def test_exam_course_list_pagination_uses_real_sql_limit(client, db_mode):
    """一个考试批次挂 15 门课程，只取第 1 页 5 条：底层 SELECT 必须带 LIMIT，
    3 页合计覆盖全部 15 门课程不重不漏。"""
    from sqlalchemy import event

    from app.db.session import get_engine, get_sessionmaker
    from app.models import AaExamBatch, AaExamCourse

    db = get_sessionmaker()()
    batch = AaExamBatch(tenant_id=TID, batch_name="dataScope下推测试批次", term_id=1, status="DRAFT")
    db.add(batch); db.flush()
    for i in range(15):
        db.add(AaExamCourse(
            tenant_id=TID, batch_id=batch.id, course_name=f"下推测试课{i}",
            teaching_task_id=i + 1, status="PENDING_CONFIRM",
        ))
    db.commit()
    bid = batch.id
    db.close()

    hdr = _hdr(client, "school_admin01")
    engine = get_engine()
    statements = []

    def _hook(_conn, _cursor, statement, *_a, **_kw):
        if statement.strip().upper().startswith("SELECT") and "t_aa_exam_course" in statement.lower():
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _hook)
    try:
        seen_ids = set()
        total_reported = None
        for page in (1, 2, 3):
            r = client.get(f"{BASE}/exam/batches/{bid}/courses", headers=hdr,
                           params={"page": page, "pageSize": 5})
            assert r.status_code == 200, r.text
            data = r.json()["data"]
            total_reported = data["total"]
            for item in data["items"]:
                assert item["examCourseId"] not in seen_ids
                seen_ids.add(item["examCourseId"])
    finally:
        event.remove(engine, "before_cursor_execute", _hook)

    assert total_reported == 15
    assert len(seen_ids) == 15
    assert any("LIMIT" in s.upper() for s in statements), (
        f"取考试课程列表的 SELECT 里必须有 LIMIT 子句，实际语句：{statements}"
    )

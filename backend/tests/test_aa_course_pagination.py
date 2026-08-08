"""课程库列表分页下推到 SQL（P1 批次C·性能）。

原实现 `list_courses()` 先 `select(AaCourse).where(*conds)...all()` 取出全部满足
分类/性质/状态过滤的课程（不受 page_size 限制），关键字匹配和分页切片都在 Python
里做——全校教学任务/排课/GPA策略配置等多处下拉都会打这个端点，课程库上千门时
每次翻页都要整表搬进内存。改为关键字下推到 SQL `LIKE`，分页下推到 SQL
`OFFSET/LIMIT`，总数改用 `COUNT(*)`。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_courses(db, count: int) -> None:
    from app.models import AaCourse
    for i in range(count):
        db.add(AaCourse(
            tenant_id=TID, course_code=f"PGTEST{i:04d}", course_name=f"分页测试课程{i}",
            category="MAJOR_CORE", nature="REQUIRED", credit=2, status="ENABLED",
        ))
    db.commit()


def test_list_courses_pagination_math_correct_across_pages(client, db_mode):
    """25 门课程，每页 10 条：三页合计应恰好覆盖全部 25 条，互不重复遗漏。"""
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    _seed_courses(db, 25)
    db.close()

    hdr = _hdr(client, "school_admin01")
    seen_ids = set()
    total_reported = None
    for page in (1, 2, 3):
        r = client.get(f"{BASE}/courses", headers=hdr,
                       params={"keyword": "分页测试课程", "page": page, "pageSize": 10})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        total_reported = data["total"]
        for item in data["items"]:
            assert item["courseId"] not in seen_ids, f"第{page}页出现了前面页已经返回过的课程"
            seen_ids.add(item["courseId"])
    assert total_reported == 25
    assert len(seen_ids) == 25, f"三页合计应覆盖全部 25 门课程，实际 {len(seen_ids)} 门"


def test_list_courses_keyword_filters_in_sql_not_python(client, db_mode):
    """关键字过滤必须真正生效（服务端 SQL 层面），不是分页之后才在 Python 里比对。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse

    db = get_sessionmaker()()
    db.add(AaCourse(tenant_id=TID, course_code="MATCH001", course_name="操作系统原理",
                    category="MAJOR_CORE", nature="REQUIRED", credit=3, status="ENABLED"))
    db.add(AaCourse(tenant_id=TID, course_code="NOMATCH001", course_name="大学英语",
                    category="PUBLIC_BASIC", nature="REQUIRED", credit=2, status="ENABLED"))
    db.commit()
    db.close()

    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/courses", headers=hdr, params={"keyword": "操作系统"})
    assert r.status_code == 200, r.text
    names = {item["courseName"] for item in r.json()["data"]["items"]}
    assert "操作系统原理" in names
    assert "大学英语" not in names


def test_list_courses_uses_real_sql_limit_not_full_scan(client, db_mode):
    """50 门课程只取第 1 页 5 条，底层 SELECT 必须带 LIMIT——不是整表拉回内存再切片
    （若整表拉回，MySQL 驱动层通常仍会一次性把全部行传回客户端，行数越多这条查询
    本身的返回体积和内存占用越大，与请求的 5 条完全不成比例）。"""
    from sqlalchemy import event

    from app.db.session import get_engine, get_sessionmaker

    db = get_sessionmaker()()
    _seed_courses(db, 50)
    db.close()

    hdr = _hdr(client, "school_admin01")
    engine = get_engine()
    statements = []

    def _hook(_conn, _cursor, statement, *_a, **_kw):
        if statement.strip().upper().startswith("SELECT") and "t_aa_course" in statement.lower():
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _hook)
    try:
        r = client.get(f"{BASE}/courses", headers=hdr,
                       params={"keyword": "分页测试课程", "page": 1, "pageSize": 5})
    finally:
        event.remove(engine, "before_cursor_execute", _hook)

    assert r.status_code == 200, r.text
    assert len(r.json()["data"]["items"]) == 5
    assert any("LIMIT" in s.upper() for s in statements), (
        f"取课程列表的 SELECT 里必须有 LIMIT 子句，实际语句：{statements}"
    )

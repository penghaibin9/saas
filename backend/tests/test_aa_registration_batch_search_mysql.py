"""注册批次搜索必须在真实 MySQL 过滤后计数、分页，不扩大租户范围。"""
import pytest
from sqlalchemy import event

BASE = "/api/v1/academic-affairs/registration-batches"
TID = 1000000000000000001
FIRST_ID = 9007199254740993001


@pytest.fixture
def batch_search_rows(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaRegistrationBatch
    with get_sessionmaker()() as db:
        rows = [AaRegistrationBatch(id=FIRST_ID + i, tenant_id=TID, batch_name=name,
                    register_type=kind, status=status) for i, (name, kind, status) in enumerate([
            ("跨页目标甲", "ANNUAL", "OPEN"), ("跨页目标乙", "SEMESTER", "OPEN"),
            ("跨页目标丙", "ANNUAL", "CLOSED"),
            *[(f"普通批次{i}", "ANNUAL", "OPEN") for i in range(25)],
            ("比例100%_核查", "ANNUAL", "OPEN"),
        ])]
        rows += [
            AaRegistrationBatch(id=FIRST_ID + 29, tenant_id=TID + 1, batch_name="跨页目标外校", register_type="ANNUAL", status="OPEN"),
            AaRegistrationBatch(id=FIRST_ID + 30, tenant_id=TID, batch_name="跨页目标删除", register_type="ANNUAL", status="OPEN", is_deleted=True),
        ]
        db.add_all(rows)
        db.commit()


def query(client, headers, **params):
    response = client.get(BASE, headers=headers, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def test_registration_search_finds_other_pages_and_queries_bounded_rows(client, batch_search_rows, auth_headers):
    from app.db.session import get_engine
    initial = query(client, auth_headers, pageSize=20)
    assert str(FIRST_ID) not in {r["batchId"] for r in initial["items"]}
    selects = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "t_aa_registration_batch" in statement:
            selects.append(statement.upper())
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        first = query(client, auth_headers, keyword="跨页目标", page=1, pageSize=2)
        second = query(client, auth_headers, keyword="跨页目标", page=2, pageSize=2)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert first["total"] == second["total"] == 3
    assert [r["batchId"] for r in first["items"] + second["items"]] == [str(FIRST_ID + i) for i in (2, 1, 0)]
    row_queries = [s for s in selects if "COUNT(" not in s]
    assert row_queries and all("LIMIT" in s for s in row_queries)


def test_registration_search_keeps_filters_tenants_deleted_and_literal_characters(client, batch_search_rows, auth_headers):
    data = query(client, auth_headers, keyword="跨页目标", status="OPEN", registerType="ANNUAL")
    assert data["total"] == 1 and data["items"][0]["batchId"] == str(FIRST_ID)
    literal = query(client, auth_headers, keyword="%_")
    assert literal["total"] == 1 and literal["items"][0]["batchName"] == "比例100%_核查"
    exact = query(client, auth_headers, keyword=str(FIRST_ID))
    assert exact["total"] == 1 and exact["items"][0]["batchId"] == str(FIRST_ID)
    for keyword in (str(FIRST_ID + 29), str(FIRST_ID + 30), "9" * 200):
        assert query(client, auth_headers, keyword=keyword)["total"] == 0


def test_registration_search_validates_input_and_preserves_view_permission(client, batch_search_rows, auth_headers):
    for params in ({"keyword": "x" * 201}, {"page": 0}, {"pageSize": 101}):
        assert client.get(BASE, headers=auth_headers, params=params).status_code == 400
    response = client.post("/api/v1/auth/mock-login", json={"loginName": "student01", "password": "any"})
    token = response.json()["data"]["accessToken"]
    assert client.get(BASE, headers={"Authorization": f"Bearer {token}"}, params={"keyword": "跨页目标"}).status_code == 403

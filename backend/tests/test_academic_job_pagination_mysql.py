"""V6.1 pagination contract adapted to the explicitly isolated local test container."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, delete
from sqlalchemy.engine import make_url
import os
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.models.data_exchange import ExportJob, ImportJob
from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
from app.services import data_exchange_job_service as jobs


TENANT = 701
PEER_TENANT = 702
STAMP = datetime(2026, 1, 2, 3, 4, 5)
MODELS = {"IMPORT": ImportJob, "EXPORT": ExportJob}


@pytest.fixture(scope="module")
def scratch_engine():
    # Dedicated disposable MySQL only; never inherit the daily sandbox target.
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert os.environ.get("APP_ENV") == "test"
    assert os.environ.get("DEPLOYMENT_MODE", "local") == "local"
    assert url.drivername == "mysql+pymysql" and url.host == "127.0.0.1"
    assert (url.port, url.database) == (32768, "student_lifecycle_test_v61_archive_sm01_w2")
    assert not url.query or dict(url.query) == {"charset": "utf8mb4"}
    engine = create_engine(url, poolclass=NullPool, isolation_level="REPEATABLE READ")
    ImportJob.__table__.create(engine, checkfirst=True)
    ExportJob.__table__.create(engine, checkfirst=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def owned_rows(scratch_engine, monkeypatch):
    connection = scratch_engine.connect()
    assert connection.dialect.default_schema_name == "student_lifecycle_test_v61_archive_sm01_w2"
    assert connection.dialect.server_version_info[:2] == (8, 0)
    transaction = connection.begin()
    seed = Session(bind=connection, expire_on_commit=False, join_transaction_mode="rollback_only")
    seed.execute(delete(ImportJob))
    seed.execute(delete(ExportJob))
    rows = []
    counters = {"IMPORT": 0, "EXPORT": 0}

    def add(kind="IMPORT", **values):
        counters[kind] += 1
        identifier = values.pop("id", counters[kind])
        counters[kind] = max(counters[kind], identifier)
        fields = dict(
            id=identifier, tenant_id=TENANT, module_code="ACADEMIC_AFFAIRS",
            operator_id=9, created_by=9, created_at=STAMP, updated_at=STAMP,
            is_deleted=False, version=2, adapter_type="SYNTHETIC_PAGING",
            adapter_ref=f"{kind}-{identifier}", status="VALIDATED" if kind == "IMPORT" else "SUCCEEDED",
        )
        fields.update(values)
        fields["import_type" if kind == "IMPORT" else "export_type"] = "ACADEMIC_ROSTER"
        row = MODELS[kind](**fields)
        seed.add(row)
        seed.flush()
        rows.append((kind, row))
        return row

    def session_factory():
        return Session(bind=connection, expire_on_commit=False, join_transaction_mode="rollback_only")

    monkeypatch.setattr(exchange, "get_sessionmaker", lambda: session_factory)
    set_tenant(TENANT)
    set_current_user(None)
    try:
        yield {"add": add, "rows": rows, "seed": seed, "connection": connection}
    finally:
        set_tenant(None)
        set_current_user(None)
        seed.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def _user(identifier=9, role="ACADEMIC_ADMIN", **extra):
    return {"userId": f"db-{identifier}", "currentRoleCode": role, **extra}


def _oracle(rows, *, actor=9, tenant=TENANT, kind="", status=""):
    # This is the existing serializer/order contract, independent of SQL paging.
    result = []
    for selected_kind in ("IMPORT", "EXPORT"):
        if kind and selected_kind != kind:
            continue
        selected = sorted(
            [row for row_kind, row in rows if row_kind == selected_kind and row.tenant_id == tenant
             and row.module_code == "ACADEMIC_AFFAIRS" and not row.is_deleted
             and row.operator_id == actor and (not status or row.status == status)],
            key=lambda row: row.id, reverse=True,
        )
        serializer = jobs._import_row if selected_kind == "IMPORT" else jobs._export_row
        result.extend(serializer(row) for row in selected)
    result.sort(key=lambda item: (item.get("createdAt") or "", int(item["id"])), reverse=True)
    return result


def test_missing_actor_is_failclosed_before_entity_session(owned_rows, monkeypatch):
    owned_rows["add"]("IMPORT", operator_id=10)
    owned_rows["add"]("EXPORT", operator_id=10)
    opened = []
    real_factory = exchange.get_sessionmaker

    def observed_factory():
        opened.append(True)
        return real_factory()

    monkeypatch.setattr(exchange, "get_sessionmaker", observed_factory)
    result = exchange.list_academic_jobs(user={"currentRoleCode": "COLLEGE_ADMIN"})
    assert result == {"list": [], "total": 0, "page": 1, "pageSize": 20}, "MISSING_ACTOR_MUST_NOT_EXPOSE_PEER_TASKS"
    assert opened == [], "MISSING_ACTOR_MUST_NOT_OPEN_ENTITY_SESSION"


@pytest.mark.parametrize("role", ["ACADEMIC_ADMIN", "COLLEGE_ADMIN"])
@pytest.mark.parametrize("kind", ["", "IMPORT", "EXPORT"])
def test_all_queries_keep_trusted_owner_scope(owned_rows, role, kind):
    add = owned_rows["add"]
    for row_kind in MODELS:
        add(row_kind)
        add(row_kind, operator_id=10)
        add(row_kind, tenant_id=PEER_TENANT)
        add(row_kind, module_code="OTHER_MODULE")
        add(row_kind, is_deleted=True)
        add(row_kind, operator_id=None, created_by=9)
    result = exchange.list_academic_jobs(
        user=_user(role=role, tenantId=PEER_TENANT, dataScope={"type": "ALL"}, collegeId=999), job_type=kind,
    )
    expected = _oracle(owned_rows["rows"], kind=kind)
    assert result == {"list": expected, "total": len(expected), "page": 1, "pageSize": 20}
    assert all(item["id"] == "1" for item in result["list"])


def test_cross_tenant_and_actor_context_change_does_not_reuse_scope(owned_rows):
    add = owned_rows["add"]
    add("IMPORT", id=1)
    add("EXPORT", id=2, tenant_id=PEER_TENANT, operator_id=10)
    assert [row["id"] for row in exchange.list_academic_jobs(user=_user())["list"]] == ["1"]
    set_tenant(PEER_TENANT)
    result = exchange.list_academic_jobs(user=_user(10, "COLLEGE_ADMIN"))
    assert result["total"] == 1
    assert result["list"] == _oracle(owned_rows["rows"], actor=10, tenant=PEER_TENANT)
    assert exchange.list_academic_jobs(user=_user())["list"] == []


@pytest.mark.parametrize("kind,status", [("import", "validated"), ("export", "succeeded"), ("", "SUCCEEDED")])
def test_raw_status_and_uppercase_contract_preserve_complete_dto(owned_rows, kind, status):
    add = owned_rows["add"]
    add("IMPORT", result_json={"note": "synthetic"}, expires_at=STAMP - timedelta(days=1))
    add("IMPORT", status="FAILED", total_rows=3, invalid_rows=2)
    add("EXPORT", expires_at=STAMP - timedelta(days=1), row_count=7, progress=100)
    result = exchange.list_academic_jobs(user=_user(), job_type=kind, status=status)
    expected = _oracle(owned_rows["rows"], kind=kind.upper(), status=status.upper())
    assert result["list"] == expected
    assert result["total"] == len(expected)
    assert any(item["status"] == "EXPIRED" for item in expected)


@pytest.mark.parametrize("wanted", ["OTHER", " IMPORT "])
def test_unknown_type_is_empty_without_tenant_lookup(owned_rows, wanted):
    set_tenant(None)
    assert exchange.list_academic_jobs(user=_user(), job_type=wanted) == {
        "list": [], "total": 0, "page": 1, "pageSize": 20,
    }


def test_valid_type_still_requires_trusted_tenant(owned_rows):
    set_tenant(None)
    with pytest.raises(AppException) as error:
        exchange.list_academic_jobs(user={"currentRoleCode": "COLLEGE_ADMIN"})
    assert error.value.code == "TENANT_CONTEXT_REQUIRED"


@pytest.mark.parametrize("page,size,expected_page,expected_size", [
    (None, None, 1, 20), (0, 0, 1, 20), (-3, -2, 1, 1), ("2", "50", 2, 50), (1, 101, 1, 100),
    (str(10 ** 100), 50, 10 ** 100, 50),
])
def test_page_bounds_and_out_of_range_shape(owned_rows, page, size, expected_page, expected_size):
    owned_rows["add"]()
    result = exchange.list_academic_jobs(user=_user(), page=page, page_size=size)
    assert result["page"] == expected_page
    assert result["pageSize"] == expected_size
    assert result["total"] == 1
    assert result["list"] == (_oracle(owned_rows["rows"]) if expected_page == 1 else [])


@pytest.mark.parametrize("argument", ["page", "page_size"])
def test_non_numeric_page_convention_remains_value_error(owned_rows, argument):
    with pytest.raises(ValueError):
        exchange.list_academic_jobs(user=_user(), **{argument: "not-a-number"})


def test_empty_and_shrinking_last_page_are_not_clamped(owned_rows):
    assert exchange.list_academic_jobs(user=_user(), page=3)["total"] == 0
    add = owned_rows["add"]
    for identifier in range(1, 52):
        add(id=identifier)
    result = exchange.list_academic_jobs(user=_user(), page=2, page_size=50)
    assert result["total"] == 51 and len(result["list"]) == 1 and result["page"] == 2
    owned_rows["rows"][0][1].is_deleted = True
    owned_rows["seed"].flush()
    result = exchange.list_academic_jobs(user=_user(), page=2, page_size=50)
    assert result == {"list": [], "total": 50, "page": 2, "pageSize": 50}


def test_same_second_cross_type_same_id_order_and_page_partition(owned_rows):
    add = owned_rows["add"]
    for identifier in range(1, 32):
        add("IMPORT", id=identifier)
        add("EXPORT", id=identifier)
    add("IMPORT", id=99, created_at=STAMP - timedelta(seconds=1))
    expected = _oracle(owned_rows["rows"])
    pages = [exchange.list_academic_jobs(user=_user(), page=page, page_size=17) for page in range(1, 5)]
    assert all(result["total"] == 63 for result in pages)
    joined = [item for result in pages for item in result["list"]]
    assert joined == expected
    assert [(item["jobType"], item["id"]) for item in joined[:4]] == [
        ("IMPORT", "31"), ("EXPORT", "31"), ("IMPORT", "30"), ("EXPORT", "30"),
    ]
    assert len({(item["jobType"], item["id"]) for item in joined}) == 63
    assert exchange.list_academic_jobs(user=_user(), page=2, page_size=17) == pages[1]


def test_only_page_entities_are_hydrated_with_bounded_sql(owned_rows, monkeypatch):
    add = owned_rows["add"]
    for identifier in range(1, 61):
        add("IMPORT", id=identifier)
        add("EXPORT", id=identifier)
    expected = _oracle(owned_rows["rows"])[7:14]
    calls = []
    statements = []
    for name in ("_import_row", "_export_row"):
        real = getattr(jobs, name)

        def observed(row, real=real):
            calls.append((row.__tablename__, row.id))
            return real(row)

        monkeypatch.setattr(jobs, name, observed)

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))

    event.listen(owned_rows["connection"], "before_cursor_execute", capture)
    try:
        result = exchange.list_academic_jobs(user=_user(), page=2, page_size=7)
    finally:
        event.remove(owned_rows["connection"], "before_cursor_execute", capture)
    assert result == {"list": expected, "total": 120, "page": 2, "pageSize": 7}
    assert len(calls) == 7, "ONLY_CURRENT_PAGE_ENTITIES_MAY_BE_SERIALIZED"
    assert len(statements) == 4 and all(sql.lstrip().upper().startswith("SELECT") for sql, _ in statements)
    assert "COUNT(" in statements[0][0].upper()
    assert "UNION ALL" in statements[1][0].upper() and "LIMIT" in statements[1][0].upper()
    assert set(calls) == {("t_import_job" if item["jobType"] == "IMPORT" else "t_export_job", int(item["id"])) for item in expected}
    for sql, parameters in statements:
        assert "operator_id" in sql and "tenant_id" in sql and "module_code" in sql and "is_deleted" in sql
        assert 9 in parameters.values() and TENANT in parameters.values() and "ACADEMIC_AFFAIRS" in parameters.values()
    assert " IN (" in statements[2][0] and " IN (" in statements[3][0]

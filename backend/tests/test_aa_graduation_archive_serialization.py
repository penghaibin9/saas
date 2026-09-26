"""毕业写入与学期封存共用行锁；真实 MySQL 用例由主控串行执行。

并发用例只纳入真实毕业域门禁，其他十二域不属于本次锁语义测试。
未替换毕业命令、权限、学期锁、毕业门禁查询或封存提交。
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Lock
from time import monotonic, sleep

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql import visitors

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, AaTerm
from app.modules.academic_affairs.services import academic_affairs_graduation_term_scope as scope
from tests.test_aa_v5_graduation_term_scope import TID, _Db, _Query, _batch, _term

BASE = "/api/v1/academic-affairs"


def test_result_guard_locks_term_then_batch_then_result_and_refreshes_cached_rows():
    events = []

    class Query(_Query):
        def populate_existing(self):
            events.append((self.model, "refresh"))
            return self

        def with_for_update(self):
            events.append((self.model, "lock"))
            return self

    class Db(_Db):
        def query(self, model):
            return Query(model, self.rows[model])

        def scalar(self, statement):
            assert statement._for_update_arg is not None
            assert statement.get_execution_options()["populate_existing"] is True
            events.append((AaTerm, "lock"))
            return super().scalar(statement)

    set_tenant({"tenantId": str(TID)})
    try:
        db = Db(terms=[_term(status="PUBLISHED")], batches=[_batch(term_id=11, status="PRECHECKED")])
        result = AaGraduationAuditResult(id=31, tenant_id=TID, batch_id=21, is_deleted=False)
        db.rows[AaGraduationAuditResult] = [result]
        assert scope.guard_result_term_writable(db, 31) is result
        assert events == [(AaTerm, "lock"), (AaGraduationAuditBatch, "refresh"),
                          (AaGraduationAuditBatch, "lock"), (AaGraduationAuditResult, "refresh"),
                          (AaGraduationAuditResult, "lock")]
    finally:
        set_tenant(None)


def _seed(client):
    from app.db.session import get_sessionmaker
    from app.models import AaArchiveBatch
    from tests.support_archive_review_identity import seed_archive_operator

    with get_sessionmaker()() as db:
        seed_archive_operator(db, TID, "school_admin01")
        term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=2, term_name="封存竞争学期",
                      start_date=datetime(2026, 2, 1), end_date=datetime(2026, 7, 31), status="PUBLISHED")
        db.add(term); db.flush()
        batch = AaArchiveBatch(tenant_id=TID, term_id=term.id, term_code="2025-2026-2",
                               status="READY", missing_count=0)
        db.add(batch); db.commit()
        ids = (term.id, batch.id)
    response = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}
    return (*ids, headers)


def _graduation_gate_only(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_service as public
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    monkeypatch.setattr(public, "_DOMAINS", [("GRADUATION", "毕业资格")])
    monkeypatch.setattr(public, "_evaluate_domains", lambda db, tid, _code: {
        "GRADUATION": policy.evaluate_graduation(db, tid)})


def _pause_first_term_lock(monkeypatch, term_id):
    reached, release = Event(), Event()
    mutex, evidence = Lock(), []
    original = Session._execute_internal

    def execute(db, statement, params=None, *args, **kwargs):
        relevant = (getattr(statement, "is_select", False)
                    and getattr(statement, "_for_update_arg", None) is not None
                    and any(getattr(table, "name", "") == "t_aa_term" for table in statement.get_final_froms()))
        selected = False
        if relevant:
            compiled = statement.compile()
            values = dict(compiled.params) | (params or {})
            for condition in visitors.iterate(statement.whereclause):
                left, right = getattr(condition, "left", None), getattr(condition, "right", None)
                if (getattr(left, "name", "") == "id"
                        and getattr(getattr(left, "table", None), "name", "") == "t_aa_term"):
                    selected = str(values.get(compiled.bind_names.get(right), getattr(right, "value", None))) == str(term_id)
                    if selected:
                        break
        pause = False
        if selected:
            with mutex:
                pause = not evidence
                evidence.append(db.connection().connection.driver_connection.thread_id())
        result = original(db, statement, params, *args, **kwargs)
        if pause:
            reached.set()
            assert release.wait(15), "测试屏障未释放；这不是业务成功回执"
        return result

    monkeypatch.setattr(Session, "_execute_internal", execute)
    return reached, release, evidence


def _assert_term_wait(future, term_id, evidence):
    from app.db.session import get_engine

    engine = get_engine()
    assert engine.dialect.name == "mysql"
    waits = []
    deadline = monotonic() + 5
    while monotonic() < deadline and not future.done():
        with engine.connect() as observer:
            waits = [dict(row) for row in observer.execute(text("""
                SELECT bt.PROCESSLIST_ID AS blocker, rt.PROCESSLIST_ID AS waiter
                FROM performance_schema.data_lock_waits w
                JOIN performance_schema.data_locks b
                  ON b.ENGINE_LOCK_ID=w.BLOCKING_ENGINE_LOCK_ID AND b.ENGINE=w.ENGINE
                JOIN performance_schema.threads bt ON bt.THREAD_ID=w.BLOCKING_THREAD_ID
                JOIN performance_schema.threads rt ON rt.THREAD_ID=w.REQUESTING_THREAD_ID
                WHERE b.OBJECT_SCHEMA=:schema AND b.OBJECT_NAME='t_aa_term'
                  AND b.INDEX_NAME='PRIMARY' AND b.LOCK_DATA=:term_id
            """), {"schema": engine.url.database, "term_id": str(term_id)}).mappings()]
        if waits:
            break
        sleep(0.02)
    assert len(evidence) >= 2 and evidence[0] != evidence[1], "必须有两个不同数据库连接竞争同一学期"
    assert any(row["blocker"] == evidence[0] and row["waiter"] == evidence[1] for row in waits), waits


def test_mysql_archive_waits_for_graduation_commit_and_rechecks_live_gate(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaArchiveBatch, ArchiveManifest

    term_id, archive_id, headers = _seed(client)
    _graduation_gate_only(monkeypatch)
    reached, release, evidence = _pause_first_term_lock(monkeypatch, term_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(client.post, BASE + "/graduation-audit-batches", headers=headers,
                             json={"batchName": "并发新增毕业批次", "termId": str(term_id)})
        try:
            assert reached.wait(5)
            archiver = pool.submit(client.post, f"{BASE}/archive/batches/{archive_id}/confirm",
                                   headers=headers, json={"force": False})
            _assert_term_wait(archiver, term_id, evidence)
            release.set()
            created, blocked = writer.result(timeout=10), archiver.result(timeout=10)
            assert created.status_code == 200, created.text
            assert blocked.status_code == 409, blocked.text
            assert "实时复核" in blocked.json()["message"]
        finally:
            release.set()
    with get_sessionmaker()() as db:
        assert db.get(AaTerm, term_id).status == "PUBLISHED"
        assert db.get(AaArchiveBatch, archive_id).status == "READY"
        assert db.query(ArchiveManifest).filter_by(tenant_id=TID, archive_batch_id=archive_id).count() == 0
        assert db.query(AaGraduationAuditBatch).filter_by(tenant_id=TID, term_id=term_id).count() == 1


def test_mysql_graduation_waits_for_archive_and_rejects_after_commit(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import ArchiveManifest, AffairsAuditTrail

    term_id, archive_id, headers = _seed(client)
    _graduation_gate_only(monkeypatch)
    reached, release, evidence = _pause_first_term_lock(monkeypatch, term_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        archiver = pool.submit(client.post, f"{BASE}/archive/batches/{archive_id}/confirm",
                               headers=headers, json={"force": False})
        try:
            assert reached.wait(5)
            writer = pool.submit(client.post, BASE + "/graduation-audit-batches", headers=headers,
                                 json={"batchName": "不得写入已封存学期", "termId": str(term_id)})
            _assert_term_wait(writer, term_id, evidence)
            release.set()
            archived, blocked = archiver.result(timeout=10), writer.result(timeout=10)
            assert archived.status_code == 200, archived.text
            assert blocked.status_code == 409, blocked.text
            assert blocked.json().get("bizCode") == "TERM_ARCHIVED"
        finally:
            release.set()
    with get_sessionmaker()() as db:
        assert db.get(AaTerm, term_id).status == "ARCHIVED"
        assert db.query(ArchiveManifest).filter_by(tenant_id=TID, archive_batch_id=archive_id).count() == 1
        assert db.query(AaGraduationAuditBatch).filter_by(tenant_id=TID, term_id=term_id).count() == 0
        assert db.query(AffairsAuditTrail).filter_by(tenant_id=TID, biz_type="AA_GRAD_AUDIT").count() == 0


@pytest.mark.parametrize(("status", "conclusion", "allowed"), [
    ("GRADUATED", None, False), ("COMPLETED", None, False), ("DELAYED", None, False),
    ("ARCHIVED", None, False), ("SYSTEM_PASSED", "GRADUATED", False),
    ("SYSTEM_ABNORMAL", None, True), ("REJECTED", None, True),
])
def test_fee_clearance_preserves_decided_facts_and_keeps_returned_remediation(monkeypatch, status, conclusion, allowed):
    from app.models import StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    result = AaGraduationAuditResult(id=31, tenant_id=TID, batch_id=21, student_id=41,
        status=status, conclusion=conclusion, overall="SYSTEM_PASSED", item_results_json="[]", is_deleted=False)

    class Db(_Db):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def connection(self, *, execution_options):
            assert self.queries == 0
            assert execution_options == {"isolation_level": "READ COMMITTED"}

        def scalars(self, statement):
            model = statement.column_descriptions[0]["entity"]
            return self.query(model).filter(*statement._where_criteria)

        def commit(self):
            self.committed = True

    db = Db(batches=[_batch(status="PRECHECKED")])
    db.committed = False
    db.rows[AaGraduationAuditResult] = [result]
    db.rows[StudentProfile] = [StudentProfile(id=41, tenant_id=TID, student_no="FEE_REMEDY", is_deleted=False)]
    monkeypatch.setattr(service, "session", lambda: db)
    monkeypatch.setattr(service, "_audit", lambda *_args: None)
    set_tenant({"tenantId": str(TID)})
    try:
        action = lambda: service.import_fee_clearance(21, {"currentRoleCode": "ACADEMIC_ADMIN"},
            [{"studentNo": "FEE_REMEDY", "status": "OWED"}])
        if allowed:
            assert action()["updated"] == 1
            assert db.committed is True
            if status == "REJECTED":
                assert result.status == "REJECTED"
        else:
            with pytest.raises(AppException) as error:
                action()
            assert error.value.http_status == 409
            assert (result.status, result.overall, result.item_results_json) == (status, "SYSTEM_PASSED", "[]")
            assert db.committed is False
    finally:
        set_tenant(None)


def test_mysql_historical_archived_batch_and_mixed_final_fee_import_are_atomic(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, GraduationEvaluationRun, StudentProfile

    _term_id, _archive_id, headers = _seed(client)
    with get_sessionmaker()() as db:
        closed = _batch(id=None, term_id=None)
        open_batch = _batch(id=None, term_id=None, status="PRECHECKED", batch_name="仍含待办的历史批次")
        first = StudentProfile(tenant_id=TID, student_no="V5_FEE_OPEN", real_name="待处理测试学生",
                               student_status="REGISTERED", status="ACTIVE", current_stage="ON_CAMPUS")
        second = StudentProfile(tenant_id=TID, student_no="V5_FEE_FINAL", real_name="已终审测试学生",
                                student_status="GRADUATED", status="ACTIVE", current_stage="ON_CAMPUS")
        db.add_all([closed, open_batch, first, second]); db.flush()
        rows = [AaGraduationAuditResult(tenant_id=TID, batch_id=open_batch.id, student_id=first.id,
                    status="SYSTEM_ABNORMAL", overall="SYSTEM_ABNORMAL", item_results_json="[]"),
                AaGraduationAuditResult(tenant_id=TID, batch_id=open_batch.id, student_id=second.id,
                    status="GRADUATED", conclusion="GRADUATED", overall="SYSTEM_PASSED", item_results_json="[]")]
        db.add_all(rows); db.commit()
        closed_id, open_id, first_id = closed.id, open_batch.id, first.id

    def snapshot():
        with get_sessionmaker()() as db:
            return (
                [(r.id, r.status, r.overall, r.item_results_json) for r in db.query(AaGraduationAuditResult)
                    .filter_by(tenant_id=TID).order_by(AaGraduationAuditResult.id)],
                [(b.id, b.status, b.generate_at) for b in db.query(AaGraduationAuditBatch)
                    .filter_by(tenant_id=TID).order_by(AaGraduationAuditBatch.id)],
                db.query(AffairsAuditTrail).filter_by(tenant_id=TID).count(),
                db.query(GraduationEvaluationRun).filter_by(tenant_id=TID).count(),
            )

    before = snapshot()
    for path, body in [
        (f"/{closed_id}/generate", {"studentIds": [str(first_id)]}),
        (f"/{closed_id}/precheck", {}),
        (f"/{closed_id}/fee-clearance", {"rows": [{"studentNo": "V5_FEE_OPEN", "status": "CLEARED"}]}),
        (f"/{open_id}/fee-clearance", {"rows": [
            {"studentNo": "V5_FEE_OPEN", "status": "CLEARED"},
            {"studentNo": "V5_FEE_FINAL", "status": "OWED"}]}),
        (f"/{open_id}/fee-clearance/mark", {"studentNo": "V5_FEE_FINAL", "status": "OWED"}),
    ]:
        response = client.post(BASE + "/graduation-audit-batches" + path, headers=headers, json=body)
        assert response.status_code == 409, (path, response.text)
        assert snapshot() == before


def test_mysql_existing_session_cannot_reuse_cached_unsealed_term(db_mode):
    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        term = _term(id=None, status="PUBLISHED")
        db.add(term); db.commit()
        term_id = term.id
    set_tenant({"tenantId": str(TID)})
    try:
        with get_sessionmaker()() as reader:
            cached = reader.get(AaTerm, term_id)
            assert cached.status == "PUBLISHED"
            with get_sessionmaker()() as writer:
                writer.get(AaTerm, term_id).status = "ARCHIVED"
                writer.commit()
            current = scope.require_creation_term(reader, str(term_id))
            assert current is cached and current.status == "ARCHIVED"
            from app.modules.academic_affairs.services.academic_affairs_archive_core_service import guard_term_writable
            with pytest.raises(AppException) as error:
                guard_term_writable(reader, current.id)
            assert error.value.code == "TERM_ARCHIVED"
    finally:
        set_tenant(None)

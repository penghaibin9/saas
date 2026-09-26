"""V5 毕业批次显式学期与归档同源范围；数据库用例由主控串行执行。"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm.evaluator import _EvaluatorCompiler

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.models import AaGraduationAuditBatch, AaTerm
from app.modules.academic_affairs.services import academic_affairs_graduation_term_scope as scope

TID = 1000000000000000001
WITHIN = datetime(2026, 6, 20)
LATER = datetime(2026, 9, 1)


@pytest.fixture(autouse=True)
def _trusted_tenant():
    set_tenant({"tenantId": str(TID)})
    yield
    set_tenant(None)


def _term(**overrides):
    values = dict(id=11, tenant_id=TID, year_code="2025-2026", term_no=2,
                  term_name="毕业审核第二学期", start_date=datetime(2026, 2, 1),
                  end_date=datetime(2026, 7, 31), is_deleted=False)
    return AaTerm(**(values | overrides))


def _batch(**overrides):
    values = dict(id=21, tenant_id=TID, term_id=None, batch_name="毕业批次",
                  grade_year="2023", status="ARCHIVED", generate_at=WITHIN,
                  created_at=WITHIN, is_deleted=False)
    return AaGraduationAuditBatch(**(values | overrides))


class _Query:
    def __init__(self, model, rows):
        self.model, self.rows = model, list(rows)

    def filter(self, *conditions):
        for condition in conditions:
            matches = _EvaluatorCompiler(self.model).process(condition)
            self.rows = [row for row in self.rows if matches(row) is True]
        return self

    def all(self):
        return self.rows

    def first(self):
        return next(iter(self.rows), None)

    def with_for_update(self):
        return self

    def populate_existing(self):
        return self


class _Db:
    def __init__(self, terms=(), batches=()):
        self.rows = {AaTerm: list(terms), AaGraduationAuditBatch: list(batches)}
        self.queries = 0

    def query(self, model):
        self.queries += 1
        return _Query(model, self.rows[model])

    def get(self, model, identity):
        return next((row for row in self.rows[model] if row.id == identity), None)

    def scalar(self, statement):
        model = statement.column_descriptions[0]["entity"]
        return self.query(model).filter(*statement._where_criteria).first()


@pytest.mark.parametrize(("changes", "expected"), [
    ({"term_id": 11, "generate_at": LATER}, True),
    ({"term_id": 11, "generate_at": None, "created_at": None}, True),
    ({"term_id": 12}, False),
    ({"term_id": None}, True),
    ({"term_id": None, "generate_at": LATER}, False),
    ({"term_id": None, "generate_at": None}, True),
    ({"term_id": None, "generate_at": datetime(2026, 7, 31, 23, 59, 59, 999999)}, True),
    ({"term_id": None, "generate_at": datetime(2026, 8, 1)}, False),
    ({"term_id": None, "generate_at": None, "created_at": LATER}, False),
    ({"term_id": None, "generate_at": None, "created_at": None}, False),
    ({"term_id": 11, "tenant_id": TID + 1}, False),
    ({"term_id": 11, "is_deleted": True}, False),
])
def test_term_predicate_prioritizes_formal_link_over_legacy_time(changes, expected):
    matches = _EvaluatorCompiler(AaGraduationAuditBatch).process(scope.batch_term_condition(_term()))
    assert (matches(_batch(**changes)) is True) is expected


def test_explicit_term_does_not_need_legacy_date_inference():
    predicate = scope.batch_term_condition(_term(start_date=None, end_date=None))
    matches = _EvaluatorCompiler(AaGraduationAuditBatch).process(predicate)
    assert matches(_batch(term_id=11)) is True
    assert matches(_batch(term_id=None)) is not True


@pytest.mark.parametrize("raw", [None, 11, True, "", "0", "-1", "1.5", " 1", "01", "١", "1\n", "9223372036854775808"])
def test_new_batch_invalid_term_fails_before_any_query(raw):
    db = _Db()
    with pytest.raises(AppException) as error:
        scope.require_creation_term(db, raw)
    assert error.value.code == "VALIDATION_ERROR"
    assert db.queries == 0


@pytest.mark.parametrize("term", [None, _term(tenant_id=TID + 1), _term(is_deleted=True)])
def test_creation_term_must_exist_in_current_tenant(term):
    with pytest.raises(AppException) as error:
        scope.require_creation_term(_Db(terms=[term] if term else []), "11")
    assert error.value.http_status == 404


def test_batch_page_names_are_batched_and_never_inferred_for_history():
    db = _Db(terms=[_term(), _term(id=12, tenant_id=TID + 1)])
    batches = [_batch(term_id=11), _batch(term_id=11), _batch(term_id=12), _batch()]
    assert scope.batch_term_names(db, batches) == {11: "毕业审核第二学期"}
    assert db.queries == 1
    assert scope.batch_term_names(db, [_batch()]) == {}
    assert db.queries == 1


def test_batch_write_guard_uses_archive_authority_and_does_not_infer_history():
    sealed = _term(status="ARCHIVED")
    db = _Db(terms=[sealed], batches=[_batch(term_id=11)])
    with pytest.raises(AppException) as error:
        scope.guard_batch_term_writable(db, 21)
    assert error.value.code == "TERM_ARCHIVED"
    legacy = _batch(status="PRECHECKED")
    assert scope.guard_batch_term_writable(_Db(terms=[sealed], batches=[legacy]), 21) is legacy


def test_historical_archived_batch_is_immutable_without_guessing_a_term():
    with pytest.raises(AppException) as error:
        scope.guard_batch_term_writable(_Db(batches=[_batch()]), 21)
    assert error.value.http_status == 409
    assert "纠错" in error.value.message


@pytest.mark.parametrize(("term_id", "at", "scope_allowed"), [(11, LATER, True), (12, WITHIN, False),
                                                              (None, WITHIN, True), (None, LATER, False)])
def test_post_archive_correction_uses_same_term_scope_before_creating_facts(term_id, at, scope_allowed):
    from app.models import AaGraduationAuditResult, GraduationDecisionFact, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_post_archive_fact_service as facts

    decision = GraduationDecisionFact(id=501, tenant_id=TID, batch_id=21, result_id=601,
                                      student_id=701, decision_no=1)
    db = _Db(terms=[_term()], batches=[_batch(term_id=term_id, generate_at=at)])
    db.rows.update({GraduationDecisionFact: [decision], AaGraduationAuditResult: [], StudentProfile: []})
    db.scalars = lambda _statement: _Query(GraduationDecisionFact, [decision])
    with pytest.raises(AppException) as error:
        facts._apply_graduation(db, SimpleNamespace(id=801, term_id=11),
                                SimpleNamespace(target_ref="501"), actor=901)
    # A matching batch reaches the next existing evidence guard; mismatches stop at the term boundary.
    assert ("缺少结果投影" in error.value.message) is scope_allowed
    assert ("无法证明属于" in error.value.message) is (not scope_allowed)


def test_archive_precheck_and_export_share_the_same_graduation_term_scope():
    from app.modules.academic_affairs.services import academic_affairs_archive_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    rows = [_batch(id=21, term_id=11, batch_name="本学期晚办理", generate_at=LATER),
            _batch(id=22, term_id=12, batch_name="另一学期", status="DRAFT"),
            _batch(id=23, batch_name="旧空关联本学期"),
            _batch(id=24, batch_name="旧空关联外学期", generate_at=LATER, status="DRAFT")]
    db = _Db(terms=[_term()], batches=rows)
    result = policy.evaluate_graduation(db, 11)
    assert result["result"] == "PASS"
    assert result["recordCount"] == 2
    exported = core._domain_rows(db, "GRADUATION", 11, "2025-2026-2")
    assert [row[0] for row in exported] == ["本学期晚办理", "旧空关联本学期"]
    assert core._domain_rows(db, "GRADUATION", None, None) == []


def test_mysql_graduation_explicit_scope_is_used_by_college_flow_precheck_and_export(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditResult, College, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_archive_core_service as core
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
    from app.modules.academic_affairs.services import academic_affairs_flow_service as flow

    with get_sessionmaker()() as db:
        term = _term(id=None)
        other = _term(id=None, year_code="2026-2027")
        college = College(tenant_id=TID, code="V5_GRAD_TERM", college_name="毕业学期范围学院", status="ACTIVE")
        db.add_all([term, other, college]); db.flush()
        student = StudentProfile(tenant_id=TID, student_no="V5_GRAD_TERM_1", real_name="毕业学期核对",
                                 college_id=college.id, current_stage="ON_CAMPUS", status="ACTIVE")
        db.add(student); db.flush()
        own = _batch(id=None, term_id=term.id, batch_name="本学期晚办理", generate_at=LATER)
        outside = _batch(id=None, term_id=other.id, batch_name="另一学期", status="DRAFT")
        legacy = _batch(id=None, batch_name="历史本学期")
        db.add_all([own, outside, legacy]); db.flush()
        db.add_all([AaGraduationAuditResult(tenant_id=TID, batch_id=batch.id, student_id=student.id,
                    status="ARCHIVED" if batch is not outside else "WAIT_PRECHECK")
                    for batch in [own, outside, legacy]])
        db.commit()
        selected = db.query(AaGraduationAuditBatch).filter(scope.batch_term_condition(term)).all()
        assert {row.id for row in selected} == {own.id, legacy.id}
        college_check = policy.evaluate_graduation(db, term.id, {college.id})
        assert college_check["recordCount"] == 2
        assert college_check["result"] != "BLOCKED"
        stage = flow._student_unit_progress(db, term, college.id, [student.id], [])[9]
        assert stage[0] == "DONE"
        assert stage[2]["byStatus"] == {"ARCHIVED": 2}
        assert {row[0] for row in core._domain_rows(db, "GRADUATION", term.id, "2025-2026-2")} == {
            "本学期晚办理", "历史本学期"}


def test_mysql_new_graduation_batch_api_requires_real_current_tenant_term_and_returns_list_names(client, db_mode):
    from app.db.session import get_sessionmaker
    from tests.support_graduation_review_identity import seed_graduation_review_identity

    with get_sessionmaker()() as db:
        seed_graduation_review_identity(db)
        term = _term(id=None)
        foreign = _term(id=None, tenant_id=TID + 1)
        deleted = _term(id=None, year_code="2026-2027", is_deleted=True)
        db.add_all([term, foreign, deleted]); db.commit()
        term_id, foreign_id, deleted_id = str(term.id), str(foreign.id), str(deleted.id)
    login = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["data"]["accessToken"]}
    base = "/api/v1/academic-affairs/graduation-audit-batches"
    for bad in [foreign_id, deleted_id, "9223372036854775807"]:
        response = client.post(base, headers=headers, json={"batchName": "不可关联", "termId": bad})
        assert response.status_code == 404, response.text
    created = client.post(base, headers=headers, json={"batchName": "显式学期毕业批次", "termId": term_id})
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["termId"] == term_id and data["termName"] == "毕业审核第二学期"
    listed = client.get(base, headers=headers, params={"batchId": data["batchId"]})
    assert listed.status_code == 200, listed.text
    payload = listed.json()["data"]
    row = (payload.get("items") or payload.get("list"))[0]
    assert row["termId"] == term_id and row["termName"] == data["termName"]


def test_mysql_archived_explicit_term_rejects_all_graduation_writes_without_partial_facts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaGraduationAuditResult, AffairsAuditTrail, GraduationDecisionFact,
                            GraduationEvaluationRun, StudentProfile)
    from tests.support_graduation_review_identity import seed_graduation_review_identity

    with get_sessionmaker()() as db:
        college = seed_graduation_review_identity(db)
        term = _term(id=None, status="ARCHIVED")
        db.add(term); db.flush()
        batch = _batch(id=None, term_id=term.id, status="PRECHECKED")
        student = StudentProfile(tenant_id=TID, student_no="V5_GRAD_SEALED", real_name="封存写保护",
                                 college_id=college.id, current_stage="ON_CAMPUS", student_status="REGISTERED",
                                 status="ACTIVE")
        db.add_all([batch, student]); db.flush()
        college_result = AaGraduationAuditResult(tenant_id=TID, batch_id=batch.id, student_id=student.id,
            overall="SYSTEM_PASSED", status="SYSTEM_PASSED", item_results_json="[]")
        # A separate batch keeps the one-result-per-student invariant while exercising final review.
        final_batch = _batch(id=None, term_id=term.id, status="REVIEWING", batch_name="封存终审批次")
        db.add(final_batch); db.flush()
        final_result = AaGraduationAuditResult(tenant_id=TID, batch_id=final_batch.id, student_id=student.id,
            overall="SYSTEM_PASSED", status="ACADEMIC_REVIEW", item_results_json="[]")
        db.add_all([college_result, final_result]); db.commit()
        tid, bid, sid = str(term.id), str(batch.id), str(student.id)
        college_result_id, final_result_id = str(college_result.id), str(final_result.id)

    headers = {}
    for key, login_name in (("school", "school_admin01"), ("college", "college_admin01")):
        login = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"})
        assert login.status_code == 200
        headers[key] = {"Authorization": "Bearer " + login.json()["data"]["accessToken"]}
    base = "/api/v1/academic-affairs"

    def snapshot():
        with get_sessionmaker()() as db:
            counts = tuple(db.query(model).filter(model.tenant_id == TID).count() for model in (
                AaGraduationAuditBatch, AaGraduationAuditResult, GraduationEvaluationRun, GraduationDecisionFact,
                AffairsAuditTrail))
            results = [(row.id, row.status, row.overall, row.item_results_json) for row in db.query(
                AaGraduationAuditResult).filter(AaGraduationAuditResult.tenant_id == TID).order_by(
                AaGraduationAuditResult.id).all()]
            return counts, results

    before = snapshot()
    commands = [
        ("school", "/graduation-audit-batches", {"batchName": "封存学期不得新建", "termId": tid}),
        ("school", f"/graduation-audit-batches/{bid}/generate", {"studentIds": [sid]}),
        ("school", f"/graduation-audit-batches/{bid}/precheck", {}),
        ("school", f"/graduation-audit-batches/{bid}/fee-clearance", {
            "rows": [{"studentNo": "V5_GRAD_SEALED", "status": "CLEARED"}]}),
        ("school", f"/graduation-audit-batches/{bid}/fee-clearance/mark", {
            "studentId": sid, "status": "CLEARED"}),
        ("school", f"/graduation-audit-batches/{bid}/archive", {}),
        ("college", f"/graduation-results/{college_result_id}/college-review", {"action": "APPROVE"}),
        ("school", f"/graduation-results/{final_result_id}/final", {"conclusion": "GRADUATED", "confirm": True}),
    ]
    for actor, path, body in commands:
        response = client.post(base + path, headers=headers[actor], json=body)
        assert response.status_code == 409, (path, response.text)
        assert response.json().get("bizCode") == "TERM_ARCHIVED", (path, response.text)
        assert snapshot() == before

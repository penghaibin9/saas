"""SM-01: one operational schedule baseline, plus independent semantic blockers.

The query fixtures exercise orchestration, not database acceptance. The two MySQL
cases use the dedicated destructive test schema only; they never seed the normal
business sandbox, call course APIs, or claim a complete 13-domain archive flow.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
from app.modules.academic_affairs.services import academic_affairs_archive_operational_policy as operational
from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as semantic
from app.modules.academic_affairs.services import academic_affairs_archive_service as public


@pytest.fixture(autouse=True)
def tenant_context():
    from app.core.context import get_tenant, set_tenant

    previous = get_tenant()
    set_tenant({"tenantId": "1"})
    try:
        yield
    finally:
        set_tenant(previous)


def _pass():
    return {"present": True, "result": "PASS", "recordCount": 0,
            "blockingCount": 0, "summary": "Unrelated domain fixture", "evidence": []}


def _isolate_other_domains(monkeypatch):
    """Keep the real legacy/operative/semantic SCHEDULE chain; isolate other domains."""
    core = policy._core

    def baseline(db, term_id, term_code, college_ids=None):
        rows = {code: _pass() for code, _label in policy.DOMAINS}
        rows["SCHEDULE"] = core._evaluate_schedule(db, term_id, college_ids)
        return rows

    monkeypatch.setattr(core, "_evaluate_domains", baseline)
    for name in ("evaluate_program", "evaluate_teaching_task", "evaluate_grade"):
        monkeypatch.setattr(semantic, name, lambda *_args, **_kwargs: _pass())
    for name in ("evaluate_status_change", "evaluate_graduation", "evaluate_selection",
                 "evaluate_makeup", "evaluate_evaluation", "evaluate_textbook"):
        monkeypatch.setattr(policy, name, lambda *_args, **_kwargs: _pass())
    monkeypatch.setattr(policy, "apply_effective_grade_policy_debt", lambda _db, _code, row: row)
    monkeypatch.setattr(operational, "evaluate_exam", lambda *_args, **_kwargs: _pass())


class _Query:
    """Already-scoped declared rows; does not simulate SQL filtering or tenancy."""
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_clauses):
        return self

    def all(self):
        return list(self.rows)

    def count(self):
        return len(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _DeclaredDb:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def query(self, model):
        return _Query(self.rows.get(model.__name__, []))


def _school(db):
    return public._evaluate_domains(db, 9, "2097-2098-2", None)["SCHEDULE"]


def test_school_missing_schedule_fact_has_single_owner(monkeypatch):
    _isolate_other_domains(monkeypatch)
    original = operational.evaluate_schedule
    calls = []

    def observe(*args, **kwargs):
        calls.append((args[1], args[2] if len(args) > 2 else kwargs.get("college_ids")))
        return original(*args, **kwargs)

    monkeypatch.setattr(operational, "evaluate_schedule", observe)
    result = _school(_DeclaredDb())
    assert result["blockingCount"] == 1, result
    assert result["summary"].count("本学期没有课表批次") == 1, result
    assert result["result"] == "BLOCKED" and result["present"] is False
    assert calls == [(9, None)]


@pytest.mark.parametrize("statuses,voided,changes,passed,reason", [
    (["PUBLISHED"], set(), 0, True, "正式发布"),
    (["ARCHIVED"], set(), 0, True, "正式归档"),
    (["ARCHIVED"], {1}, 0, False, "作废"),
    (["VOIDED"], set(), 0, False, "作废"),
    (["SUPERSEDED"], set(), 0, False, "没有 PUBLISHED"),
    (["DRAFT"], set(), 0, False, "草稿"),
    (["PUBLISHED", "PRE_PUBLISHED"], set(), 0, False, "预发布"),
    (["PUBLISHED"], set(), 2, False, "在途调停课"),
    (["PUBLISHED", "UNRECOGNIZED"], set(), 0, False, "未知状态"),
    (["PUBLISHED", "DRAFT", "VOIDED", "SUPERSEDED"], set(), 0, True, "正式发布"),
    (["ARCHIVED", "PUBLISHED"], {1}, 0, True, "正式发布"),
])
def test_school_reconciliation_preserves_operational_states(monkeypatch, statuses, voided,
                                                          changes, passed, reason):
    _isolate_other_domains(monkeypatch)
    db = _DeclaredDb({
        "AaScheduleBatch": [SimpleNamespace(id=i + 1, status=status)
                            for i, status in enumerate(statuses)],
        "AaSchedulePublish": [SimpleNamespace(batch_id=value) for value in voided],
        "AaScheduleChange": [SimpleNamespace(id=i + 1) for i in range(changes)],
    })
    result = _school(db)
    assert result["present"] is passed, result
    assert result["result"] == ("PASS" if passed else "BLOCKED"), result
    assert result["blockingCount"] == (0 if passed else 1), result
    if passed:
        assert reason in result["evidence"][0]["baseSummary"]
        assert result["summary"] == "正式课表已发布，0个应排任务全部落课，HARD冲突0"
    else:
        assert reason in result["summary"]


def test_operational_evaluation_error_stays_fail_closed(monkeypatch):
    _isolate_other_domains(monkeypatch)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("declared unavailable query")

    monkeypatch.setattr(operational, "evaluate_schedule", unavailable)
    result = _school(_DeclaredDb())
    # Existing semantic reconciliation turns a failed inherited baseline into a
    # blocking result; it must never turn the UNKNOWN/error evidence into PASS.
    assert result["result"] == "BLOCKED" and result["blockingCount"] == 1
    assert "语义检查失败：RuntimeError" in result["summary"]


def test_college_result_is_not_merged_with_school_operational_gate(monkeypatch):
    expected = {"SCHEDULE": {**_pass(), "summary": "scoped college result"}}
    monkeypatch.setattr(policy, "_evaluate_college_domains", lambda *_args: expected)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("outer school evaluation must not run for college")

    monkeypatch.setattr(operational, "evaluate_schedule", forbidden)
    assert public._evaluate_domains(_DeclaredDb(), 9, "2097-2098-2", {12}) is expected


def _validated_mysql_test_url(raw_url, environment):
    """Only the owned task schema or a canonical isolated GitHub job is safe."""
    from sqlalchemy.exc import ArgumentError
    from sqlalchemy.engine import make_url

    if environment.get("APP_ENV") != "test" or environment.get("DEPLOYMENT_MODE", "local") not in {"local", "staging"}:
        raise ValueError("MySQL fixture requires test/nonproduction mode")
    try:
        url = make_url(raw_url)
    except (ArgumentError, ValueError):
        raise ValueError("Invalid MySQL test target") from None
    if url.drivername != "mysql+pymysql" or url.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("MySQL fixture requires a loopback mysql+pymysql target")
    if url.query and dict(url.query) != {"charset": "utf8mb4"}:
        raise ValueError("MySQL fixture forbids connection routing overrides")
    pair = (url.port, url.database)
    owned = pair == (32768, "student_lifecycle_test_v61_archive_sm01_w2")
    isolated_ci = (
        pair == (3306, "student_lifecycle_test")
        and environment.get("GITHUB_ACTIONS") == "true"
        and environment.get("CI") == "true"
    )
    if not (owned or isolated_ci):
        raise ValueError("MySQL fixture requires an explicitly isolated test target")
    return url


@pytest.fixture
def mysql_db(request):
    """Validate the destructive target before asking conftest for db_mode."""
    import os

    url = _validated_mysql_test_url(os.environ["TEST_DATABASE_URL"], os.environ)
    request.getfixturevalue("db_mode")
    from app.db.session import get_engine, get_sessionmaker

    assert get_engine().dialect.name == "mysql"
    actual_url = get_engine().url
    assert (actual_url.drivername, actual_url.host, actual_url.port, actual_url.database) == (
        url.drivername, url.host, url.port, url.database,
    )
    with get_sessionmaker()() as db:
        yield db
        db.rollback()


def _mysql_term(db, year="2097-2098", tenant=1):
    from app.models import AaTerm

    term = AaTerm(tenant_id=tenant, year_code=year, term_no=2, status="PUBLISHED",
                  start_date=datetime(2098, 2, 1), end_date=datetime(2098, 6, 30))
    db.add(term)
    db.flush()
    return term


def test_mysql_no_batch_is_one_blocker_and_other_scope_cannot_supply_formal_version(mysql_db,
                                                                                  monkeypatch):
    from app.models import AaScheduleBatch

    _isolate_other_domains(monkeypatch)
    db = mysql_db
    term = _mysql_term(db)
    other = _mysql_term(db, year="2098-2099")
    db.add_all([
        AaScheduleBatch(tenant_id=1, term_id=other.id, batch_name="other term", status="PUBLISHED"),
        AaScheduleBatch(tenant_id=2, term_id=term.id, batch_name="other tenant", status="PUBLISHED"),
    ])
    db.flush()
    result = public._evaluate_domains(db, term.id, "2097-2098-2", None)["SCHEDULE"]
    assert result["result"] == "BLOCKED" and result["blockingCount"] == 1, result
    assert result["summary"].count("本学期没有课表批次") == 1
    assert result["evidence"][0]["formalBatchIds"] == []


def test_mysql_independent_operational_coverage_and_hard_blockers_are_each_counted_once(mysql_db,
                                                                                    monkeypatch):
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch

    _isolate_other_domains(monkeypatch)
    db = mysql_db
    term = _mysql_term(db)
    tasks_batch = AaTeachingTaskBatch(tenant_id=1, term_id=term.id,
                                    batch_name="declared coverage fixture", status="APPROVED")
    published = AaScheduleBatch(tenant_id=1, term_id=term.id,
                               batch_name="formal fixture", status="PUBLISHED")
    pending = AaScheduleBatch(tenant_id=1, term_id=term.id,
                             batch_name="prepublication fixture", status="PRE_PUBLISHED")
    db.add_all([tasks_batch, published, pending])
    db.flush()
    # Synthetic references only: these mapped IDs have no FK, so no course seed
    # or business course service is needed for schedule coverage reconciliation.
    tasks = [AaTeachingTask(tenant_id=1, batch_id=tasks_batch.id, course_id=9000 + i,
                            status="READY", teacher_key="fixture-teacher") for i in range(3)]
    db.add_all(tasks)
    db.flush()
    for task in tasks[:2]:
        db.add(AaScheduleItem(tenant_id=1, batch_id=published.id, task_id=task.id,
                              teacher_key="fixture-teacher", weekday=1, slot_no=1,
                              start_week=1, end_week=17, week_parity="ALL", status="EFFECTIVE"))
    db.flush()
    result = public._evaluate_domains(db, term.id, "2097-2098-2", None)["SCHEDULE"]
    assert result["result"] == "BLOCKED" and result["blockingCount"] == 3, result
    assert result["summary"].count("预发布批次 1 个") == 1
    assert "漏排1、HARD冲突1" in result["summary"]
    evidence = result["evidence"]
    assert evidence[0]["readyTasks"] == 3 and evidence[0]["effectiveItems"] == 2
    assert sum(row["type"] == "UNSCHEDULED_TASK" for row in evidence) == 1
    assert sum(row["type"] == "HARD_CONFLICT" for row in evidence) == 1
    assert next(row for row in evidence if row["type"] == "UNSCHEDULED_TASK")["taskId"] == str(tasks[2].id)


@pytest.mark.parametrize("raw_url,environment,expected", [
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2",
     {"APP_ENV": "test", "DEPLOYMENT_MODE": "local"}, ("127.0.0.1", 32768, "student_lifecycle_test_v61_archive_sm01_w2")),
    ("mysql+pymysql://fixture:fixture@localhost:32768/student_lifecycle_test_v61_archive_sm01_w2",
     {"APP_ENV": "test"}, ("localhost", 32768, "student_lifecycle_test_v61_archive_sm01_w2")),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test",
     {"APP_ENV": "test", "GITHUB_ACTIONS": "true", "CI": "true"}, ("127.0.0.1", 3306, "student_lifecycle_test")),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4",
     {"APP_ENV": "test", "GITHUB_ACTIONS": "true", "CI": "true"}, ("127.0.0.1", 3306, "student_lifecycle_test")),
], ids=["owned-task", "owned-loopback-alias", "isolated-github-default-deployment", "isolated-github-charset"])
def test_mysql_resource_guard_accepts_only_declared_safe_targets(raw_url, environment, expected):
    url = _validated_mysql_test_url(raw_url, environment)
    assert url.drivername == "mysql+pymysql"
    assert (url.host, url.port, url.database) == expected


@pytest.mark.parametrize("raw_url,overrides", [
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test", {"GITHUB_ACTIONS": "true"}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test", {"CI": "true"}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test",
     {"GITHUB_ACTIONS": "true", "CI": "true", "DEPLOYMENT_MODE": "production"}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2", {"APP_ENV": "production"}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2", {"DEPLOYMENT_MODE": "production"}),
    ("sqlite:///:memory:", {}),
    ("mysql+pymysql://fixture:fixture@remote.invalid:32768/student_lifecycle_test_v61_archive_sm01_w2", {}),
    ("mysql+mysqldb://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_e2e", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_e2e_term_restore_w2_20261012", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3306/student_lifecycle_test_v61_archive_sm01_w2", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:3307/student_lifecycle_test_v61_archive_sm01_w2", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1/student_lifecycle_test_v61_archive_sm01_w2", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2?host=remote.invalid", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2?unix_socket=/tmp/mysql.sock", {}),
    ("mysql+pymysql://fixture:fixture@127.0.0.1:32768/student_lifecycle_test_v61_archive_sm01_w2?charset=latin1", {}),
    ("not-a-database-url", {}),
], ids=["local-shared-ci-schema", "github-only", "ci-only", "github-production-deployment", "production-app", "production-deployment",
        "sqlite", "remote", "wrong-driver", "e2e", "production-schema", "shared-task-port", "restore-scratch",
        "wrong-schema-port-pair", "wrong-task-port", "implicit-port", "host-override", "socket-override",
        "wrong-charset", "malformed-url"])
def test_mysql_resource_guard_rejects_unsafe_targets(raw_url, overrides):
    environment = {"APP_ENV": "test", "DEPLOYMENT_MODE": "local", **overrides}
    with pytest.raises(ValueError):
        _validated_mysql_test_url(raw_url, environment)


def test_mysql_resource_guard_rejects_before_requesting_database_fixture(monkeypatch):
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    calls = []

    def forbidden(name):
        calls.append(name)
        raise AssertionError("Unsafe target reached destructive db_mode")

    fixture = mysql_db.__wrapped__(SimpleNamespace(getfixturevalue=forbidden))
    with pytest.raises(ValueError):
        next(fixture)
    assert calls == []

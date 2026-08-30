from __future__ import annotations

import time
from dataclasses import asdict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    AffairsRiskRecord,
    GraduationStudent,
    InternshipRecord,
    StudentProfile,
    UnifiedTodo,
)
from app.modules.platform.business_collaboration.domain_providers import (
    AffairsSearchProvider,
    GraduationSearchProvider,
    InternshipSearchProvider,
)
from app.modules.platform.business_collaboration import domain_providers as domain_provider_module
from app.modules.platform.business_collaboration.schemas import SearchContext, SearchHit
from app.modules.platform.business_collaboration.search_federation import SearchFederationService
from app.modules.platform.business_collaboration.todo_provider import TodoSearchProvider


TENANT = 7101
OTHER_TENANT = 7102


def _actor(*permissions: str, **extra):
    return {
        "userId": "u_501",
        "userType": "TEACHER",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TENANT),
        "permissionPatterns": list(permissions),
        **extra,
    }


class _Provider:
    def __init__(self, code, *, delay=0.0, hits=None, error=None):
        self.provider_code = code
        self.delay = delay
        self.hits = hits or []
        self.error = error
        self.contexts = []

    def search(self, context):
        self.contexts.append(context)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.hits


def _hit(provider: str, key: str) -> SearchHit:
    return SearchHit(
        provider=provider, type="TEST", object_id=key, dedupe_key=key,
        title=key, module_code="TEST",
    )


def test_federation_uses_one_total_deadline_and_returns_partial_safely():
    fast = _Provider("FAST", hits=[_hit("FAST", "one")])
    failed = _Provider("FAILED", error=RuntimeError("database detail must stay opaque"))
    slow = _Provider("SLOW", delay=0.25, hits=[_hit("SLOW", "late")])
    started = time.monotonic()
    service = SearchFederationService(
        [fast, failed, slow], total_deadline_seconds=0.05, max_workers=3,
    )
    try:
        result = service.search(SearchContext(tenant_id=TENANT, actor=_actor(), keyword="终稿"))
        elapsed = time.monotonic() - started
    finally:
        service.close()

    assert elapsed < 0.18, "response must not wait for the slow provider after the total budget"
    assert [hit.dedupe_key for hit in result.hits] == ["one"]
    assert result.partial is True
    assert {(error.provider, error.code) for error in result.provider_errors} == {
        ("FAILED", "FAILED"), ("SLOW", "TIMEOUT"),
    }


def test_federation_rejects_duplicate_or_empty_provider_codes():
    for providers in (
        [_Provider("STUDENT"), _Provider("STUDENT")],
        [_Provider("")],
    ):
        try:
            SearchFederationService(providers)
            raise AssertionError("invalid provider codes must fail before dispatch")
        except ValueError:
            pass


def test_federation_and_direct_provider_deny_tenant_mismatch():
    context = SearchContext(
        tenant_id=TENANT,
        actor=_actor(tenantId=str(OTHER_TENANT)),
        keyword="终稿",
    )
    service = SearchFederationService([_Provider("STUDENT")])
    try:
        result = service.search(context)
    finally:
        service.close()
    assert result.hits == [] and result.partial is False
    assert [(error.provider, error.code) for error in result.provider_errors] == [
        ("STUDENT", "DENIED")
    ]


def test_federation_dedupes_stably_and_telemetry_has_no_keyword_or_pii_fields():
    events = []
    first = _Provider("FIRST", hits=[_hit("FIRST", "shared"), _hit("FIRST", "first")])
    second = _Provider("SECOND", hits=[_hit("SECOND", "shared"), _hit("SECOND", "second")])
    service = SearchFederationService(
        [first, second], telemetry_sink=events.append,
    )
    try:
        result = service.search(SearchContext(
            tenant_id=TENANT, actor=_actor(), keyword="S20260001",
        ))
    finally:
        service.close(wait_for_running=True)

    assert [hit.dedupe_key for hit in result.hits] == ["shared", "first", "second"]
    assert len(events) == 2
    for event in events:
        payload = asdict(event)
        assert set(payload) == {"provider", "latency_bucket", "hit_count", "zero_result", "partial"}
        assert "S20260001" not in repr(payload)
        assert not ({"keyword", "studentNo", "phone", "idCard", "sql"} & set(payload))


def test_federation_reuses_bounded_workers_and_slow_telemetry_cannot_spend_deadline():
    events = []

    def slow_telemetry(event):
        time.sleep(0.2)
        events.append(event)

    service = SearchFederationService(
        [_Provider("FAST", hits=[_hit("FAST", "one")])],
        total_deadline_seconds=0.05,
        max_workers=2,
        telemetry_sink=slow_telemetry,
    )
    executor_id = id(service._executor)
    try:
        started = time.monotonic()
        first = service.search(SearchContext(
            tenant_id=TENANT, actor=_actor(), keyword="终稿",
        ))
        elapsed = time.monotonic() - started
        second = service.search(SearchContext(
            tenant_id=TENANT, actor=_actor(), keyword="实习",
        ))
        assert elapsed < 0.12
        assert first.hits and second.hits
        assert id(service._executor) == executor_id
        assert service._executor._max_workers == 2
    finally:
        service.close(wait_for_running=True)
    assert len(events) == 2


def test_federation_centrally_bounds_provider_input_and_output():
    provider = _Provider(
        "MANY",
        hits=[_hit("MANY", f"hit-{index}") for index in range(80)],
    )
    service = SearchFederationService([provider])
    try:
        original_actor = _actor()
        result = service.search(SearchContext(
            tenant_id=TENANT,
            actor=original_actor,
            keyword="终稿" + ("x" * 200),
            limit=999,
        ))
    finally:
        service.close(wait_for_running=True)

    assert len(provider.contexts) == 1
    dispatched = provider.contexts[0]
    assert len(dispatched.keyword) == 100 and dispatched.limit == 50
    assert dispatched.actor == original_actor and dispatched.actor is not original_actor
    assert len(result.hits) == 50


def test_federation_rejects_non_list_provider_result_as_opaque_failure():
    provider = _Provider("INVALID")
    provider.search = lambda _context: iter([_hit("INVALID", "one")])
    service = SearchFederationService([provider])
    try:
        result = service.search(SearchContext(
            tenant_id=TENANT, actor=_actor(), keyword="终稿",
        ))
    finally:
        service.close(wait_for_running=True)
    assert result.hits == [] and result.partial is True
    assert [(error.provider, error.code) for error in result.provider_errors] == [
        ("INVALID", "FAILED")
    ]

    malformed = _Provider("MALFORMED", hits=[{"dedupe_key": "unsafe"}])
    good = _Provider("GOOD", hits=[_hit("GOOD", "safe")])
    service = SearchFederationService([malformed, good])
    try:
        mixed = service.search(SearchContext(
            tenant_id=TENANT, actor=_actor(), keyword="终稿",
        ))
    finally:
        service.close(wait_for_running=True)
    assert [hit.dedupe_key for hit in mixed.hits] == ["safe"]
    assert [(error.provider, error.code) for error in mixed.provider_errors] == [
        ("MALFORMED", "FAILED")
    ]


def _domain_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        StudentProfile.__table__, GraduationStudent.__table__,
        InternshipRecord.__table__, AffairsRiskRecord.__table__,
    ):
        table.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        allowed = StudentProfile(
            tenant_id=TENANT, student_no="S20260001", real_name="张三", class_id=11,
            grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        denied = StudentProfile(
            tenant_id=TENANT, student_no="S20260002", real_name="张四", class_id=22,
            grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        cross = StudentProfile(
            tenant_id=OTHER_TENANT, student_no="S20260003", real_name="张五", class_id=11,
            grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([allowed, denied, cross])
        db.flush()
        grad_allowed = GraduationStudent(
            tenant_id=TENANT, student_id=allowed.id, student_no=allowed.student_no,
            name=allowed.real_name, topic_title="终稿智能审阅", stage="FINAL_REVIEW",
            record_status="ACTIVE",
        )
        grad_denied = GraduationStudent(
            tenant_id=TENANT, student_id=denied.id, student_no=denied.student_no,
            name=denied.real_name, topic_title="终稿质量分析", stage="FINAL_REVIEW",
            record_status="ACTIVE",
        )
        db.add_all([grad_allowed, grad_denied])
        db.add_all([
            InternshipRecord(
                tenant_id=TENANT, student_id=allowed.id, enterprise_name="跃科科技",
                position_name="测试工程师", status="ONBOARD",
            ),
            InternshipRecord(
                tenant_id=TENANT, student_id=denied.id, enterprise_name="跃科科技",
                position_name="开发工程师", status="ONBOARD",
            ),
            AffairsRiskRecord(
                tenant_id=TENANT, student_id=allowed.id, source="ACADEMIC_WARNING",
                source_ref_id=1, title="学业预警跟进", status="NEW",
            ),
            AffairsRiskRecord(
                tenant_id=TENANT, student_id=denied.id, source="ACADEMIC_WARNING",
                source_ref_id=2, title="学业预警跟进", status="NEW",
            ),
            AffairsRiskRecord(
                tenant_id=TENANT, student_id=allowed.id, source="MENTAL",
                source_ref_id=3, title="学业预警心理敏感标题", status="NEW",
            ),
        ])
        db.commit()
        return factory, int(allowed.id), int(grad_allowed.id)


def test_domain_providers_are_scope_first_and_academic_is_not_registered():
    factory, allowed_student_id, allowed_grad_id = _domain_factory()
    context = SearchContext(
        tenant_id=TENANT,
        actor=_actor(
            "graduationDesign.student.view", "internship.student.view", "studentAffairs.risk.view"
        ),
        keyword="终稿",
        client="pc",
    )
    graduation = GraduationSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: select(GraduationStudent.id).where(
            GraduationStudent.id == allowed_grad_id
        ),
    )
    grad_hits = graduation.search(context)
    assert [hit.title for hit in grad_hits] == ["张三"]
    assert grad_hits[0].target and grad_hits[0].target.exact is True

    internship = InternshipSearchProvider(
        factory,
        scope_applier=lambda stmt, _ctx: stmt.where(InternshipRecord.student_id == allowed_student_id),
    )
    intern_hits = internship.search(SearchContext(
        tenant_id=TENANT, actor=context.actor, keyword="跃科科技", client="pc",
    ))
    assert [hit.title for hit in intern_hits] == ["张三"]

    affairs = AffairsSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: StudentProfile.id == allowed_student_id,
    )
    affair_hits = affairs.search(SearchContext(
        tenant_id=TENANT, actor=context.actor, keyword="学业预警", client="pc",
    ))
    assert [hit.object_id for hit in affair_hits] and len(affair_hits) == 1
    assert all("心理" not in hit.title for hit in affair_hits)

    providers = [graduation, internship, affairs]
    assert {provider.provider_code for provider in providers} == {"GRADUATION", "INTERNSHIP", "AFFAIRS"}
    assert "ACADEMIC" not in {provider.provider_code for provider in providers}


def test_domain_providers_bound_keyword_before_sql_matching(monkeypatch):
    factory, allowed_student_id, allowed_grad_id = _domain_factory()
    observed = []
    original_like = domain_provider_module._like

    def capture_like(value):
        observed.append(value)
        return original_like(value)

    monkeypatch.setattr(domain_provider_module, "_like", capture_like)
    actor = _actor(
        "graduationDesign.student.view", "internship.student.view", "studentAffairs.risk.view"
    )
    long_keyword = "终稿" + ("x" * 200)
    GraduationSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: select(GraduationStudent.id).where(
            GraduationStudent.id == allowed_grad_id
        ),
    ).search(SearchContext(tenant_id=TENANT, actor=actor, keyword=long_keyword))
    InternshipSearchProvider(
        factory,
        scope_applier=lambda stmt, _ctx: stmt.where(
            InternshipRecord.student_id == allowed_student_id
        ),
    ).search(SearchContext(tenant_id=TENANT, actor=actor, keyword=long_keyword))
    AffairsSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: StudentProfile.id == allowed_student_id,
    ).search(SearchContext(tenant_id=TENANT, actor=actor, keyword=long_keyword))

    assert observed and all(len(value) == 100 for value in observed)


def test_todo_provider_reuses_visibility_and_typed_route_authorities():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UnifiedTodo.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            UnifiedTodo(
                tenant_id=TENANT, source_module="graduation", source_biz_type="FINAL",
                source_biz_id=901, todo_type="GD_FINAL_REVIEW", assignee_id=501,
                student_id=11, title="终稿待评阅", status="PENDING",
            ),
            UnifiedTodo(
                tenant_id=TENANT, source_module="graduation", source_biz_type="FINAL",
                source_biz_id=902, todo_type="GD_FINAL_REVIEW", assignee_id=999,
                student_id=12, title="终稿他人待评阅", status="PENDING",
            ),
            UnifiedTodo(
                tenant_id=TENANT, source_module="graduation", source_biz_type="FINAL",
                source_biz_id=903, todo_type="GD_FINAL_REVIEW", assignee_id=501,
                student_id=13, title=r"终稿\特殊路径", status="PENDING",
            ),
        ])
        db.commit()
    provider = TodoSearchProvider(
        factory,
        visibility_resolver=lambda _db, _ctx: UnifiedTodo.assignee_id == 501,
    )
    hits = provider.search(SearchContext(
        tenant_id=TENANT, actor=_actor(), keyword="终稿", client="pc",
    ))
    assert {hit.title for hit in hits} == {"终稿待评阅", r"终稿\特殊路径"}
    assert all(
        hit.target and hit.target.route_name == "todo-route:graduation-final-queue"
        for hit in hits
    )
    assert all(hit.allowed_actions == ["OPEN"] for hit in hits)

    escaped_hits = provider.search(SearchContext(
        tenant_id=TENANT, actor=_actor(), keyword=r"终稿\特殊", client="pc",
    ))
    assert [hit.title for hit in escaped_hits] == [r"终稿\特殊路径"]

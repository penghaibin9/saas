"""SYS-12 学年学期统一切换：真库状态机、唯一 ACTIVE、结期阻断与定时激活。

对应 V6 必测用例 SYS12-T01～T04。全部走真实 TEST_DATABASE_URL（MySQL-only 收口），
不使用 mock 学期或内存替身。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.services import academic_calendar_service as svc

TENANT = 9012
OTHER_TENANT = 9013


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _mk_term(tenant_id: int, year_code: str, term_no: int, *, is_current: bool = False) -> int:
    from app.models import AaTerm

    with _session() as db:
        term = AaTerm(
            tenant_id=tenant_id,
            year_code=year_code,
            term_no=term_no,
            term_name=f"{year_code}第{term_no}学期",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2027, 1, 15),
            teaching_weeks=18,
            is_current=is_current,
            status="PUBLISHED",
        )
        db.add(term)
        db.commit()
        db.refresh(term)
        return int(term.id)


def _enroll(tenant_id: int, term_id: int) -> dict:
    return svc.enroll_term(term_id, tenant_id=tenant_id)


def _to(term_id: int, target: str, *, tenant_id: int, reason: str = "测试", force: bool = False, scheduled_at=None):
    current = svc.get_calendar(term_id, tenant_id=tenant_id)
    return svc.transition(
        term_id,
        target,
        reason=reason,
        expected_version=int(current["version"]),
        force=force,
        scheduled_at=scheduled_at,
        tenant_id=tenant_id,
    )


def _activate(term_id: int, *, tenant_id: int, force: bool = False):
    _to(term_id, "VALIDATED", tenant_id=tenant_id)
    return _to(term_id, "ACTIVE", tenant_id=tenant_id, force=force)


def _mk_grade_task(tenant_id: int, term_id: int, status: str) -> None:
    from app.models import AaGradeTask

    with _session() as db:
        db.add(
            AaGradeTask(
                tenant_id=tenant_id,
                teaching_task_id=term_id * 100 + (1 if status == "PUBLISHED" else 2),
                term_id=term_id,
                course_name="测试课程",
                status=status,
            )
        )
        db.commit()


def _mk_archived_batch(tenant_id: int, term_id: int) -> None:
    from app.models import AaArchiveBatch

    with _session() as db:
        db.add(
            AaArchiveBatch(
                tenant_id=tenant_id,
                batch_name="测试归档批次",
                term_id=term_id,
                archived_at=datetime.utcnow(),
            )
        )
        db.commit()


# ── SYS12-T01：同租户同类型只有一个 ACTIVE ────────────────────────────────────
def test_t01_only_one_active_calendar_per_tenant(db_mode):
    first = _mk_term(TENANT, "2026-2027", 1)
    second = _mk_term(TENANT, "2026-2027", 2)
    _enroll(TENANT, first)
    _enroll(TENANT, second)

    activated = _activate(first, tenant_id=TENANT)
    assert activated["governanceStatus"] == "ACTIVE"

    # 第二个学期在旧学期未结期前不得激活
    _to(second, "VALIDATED", tenant_id=TENANT)
    with pytest.raises(AppException) as exc:
        _to(second, "ACTIVE", tenant_id=TENANT)
    assert exc.value.code == "TERM_ACTIVATION_CONFLICT"

    # 旧学期进入结期后释放哨兵，新学期才能接手
    _mk_grade_task(TENANT, first, "PUBLISHED")
    _mk_archived_batch(TENANT, first)
    _to(first, "CLOSING", tenant_id=TENANT)
    handed_over = _to(second, "ACTIVE", tenant_id=TENANT)
    assert handed_over["governanceStatus"] == "ACTIVE"

    resolved = svc.resolve_current(tenant_id=TENANT)
    assert resolved["termId"] == str(second)


def test_t01_database_constraint_blocks_two_active_rows(db_mode):
    """应用层之外，数据库唯一索引必须兜底并发激活。"""
    from app.models.academic_calendar import AcademicCalendarGovernance

    first = _mk_term(TENANT, "2027-2028", 1)
    second = _mk_term(TENANT, "2027-2028", 2)
    _enroll(TENANT, first)
    _enroll(TENANT, second)
    _activate(first, tenant_id=TENANT)

    with _session() as db:
        row = db.query(AcademicCalendarGovernance).filter_by(tenant_id=TENANT, term_id=second).first()
        row.governance_status = "ACTIVE"
        row.active_key = "ACTIVE"  # 绕过 service 直接写库，模拟并发穿透
        with pytest.raises(IntegrityError):
            db.commit()


def test_t01_active_is_isolated_between_tenants(db_mode):
    mine = _mk_term(TENANT, "2028-2029", 1)
    theirs = _mk_term(OTHER_TENANT, "2028-2029", 1)
    _enroll(TENANT, mine)
    _enroll(OTHER_TENANT, theirs)

    _activate(mine, tenant_id=TENANT)
    # 另一租户激活自己的学期不受影响——唯一约束是按 tenant 维度的
    _activate(theirs, tenant_id=OTHER_TENANT)

    assert svc.resolve_current(tenant_id=TENANT)["termId"] == str(mine)
    assert svc.resolve_current(tenant_id=OTHER_TENANT)["termId"] == str(theirs)


# ── SYS12-T02：结期阻断 ─────────────────────────────────────────────────────
def test_t02_closing_blocked_when_grades_unpublished_or_not_archived(db_mode):
    term = _mk_term(TENANT, "2029-2030", 1)
    _enroll(TENANT, term)
    _activate(term, tenant_id=TENANT)

    _mk_grade_task(TENANT, term, "ENTERING")  # 未发布

    blockers = svc.closing_blockers(term, tenant_id=TENANT)
    codes = {b["code"] for b in blockers}
    assert "GRADE_NOT_PUBLISHED" in codes
    assert "TERM_NOT_ARCHIVED" in codes

    with pytest.raises(AppException) as exc:
        _to(term, "CLOSING", tenant_id=TENANT)
    assert exc.value.code == "TERM_CLOSING_BLOCKED"
    assert exc.value.http_status == 409

    # 被阻断也要留下审计痕迹，便于事后解释
    detail = svc.get_calendar(term, tenant_id=TENANT)
    assert detail["governanceStatus"] == "ACTIVE"  # 状态未被改坏
    assert any(t["blockers"] for t in detail["transitions"])


def test_t02_force_closing_requires_explicit_flag(db_mode):
    term = _mk_term(TENANT, "2030-2031", 1)
    _enroll(TENANT, term)
    _activate(term, tenant_id=TENANT)
    _mk_grade_task(TENANT, term, "SUBMITTED")

    with pytest.raises(AppException):
        _to(term, "CLOSING", tenant_id=TENANT)

    forced = _to(term, "CLOSING", tenant_id=TENANT, force=True, reason="校长确认带未收尾业务结期")
    assert forced["governanceStatus"] == "CLOSING"


def test_t02_illegal_transition_is_rejected(db_mode):
    term = _mk_term(TENANT, "2031-2032", 1)
    _enroll(TENANT, term)
    # DRAFT 不能直接跳 ACTIVE
    with pytest.raises(AppException) as exc:
        _to(term, "ACTIVE", tenant_id=TENANT)
    assert exc.value.code == "STATE_TRANSITION_DENIED"

    # ARCHIVED 之后不可再变更
    _activate(term, tenant_id=TENANT)
    _mk_grade_task(TENANT, term, "PUBLISHED")
    _mk_archived_batch(TENANT, term)
    _to(term, "CLOSING", tenant_id=TENANT)
    _to(term, "CLOSED", tenant_id=TENANT)
    _to(term, "ARCHIVED", tenant_id=TENANT)
    with pytest.raises(AppException):
        _to(term, "ACTIVE", tenant_id=TENANT)


def test_t02_stale_version_is_rejected(db_mode):
    term = _mk_term(TENANT, "2032-2033", 1)
    _enroll(TENANT, term)
    _to(term, "VALIDATED", tenant_id=TENANT)
    with pytest.raises(AppException) as exc:
        svc.transition(term, "ACTIVE", reason="用过期版本号", expected_version=0, tenant_id=TENANT)
    assert exc.value.code == "VERSION_CONFLICT"


# ── SYS12-T03：所有 consumer 读同一期 ───────────────────────────────────────
def test_t03_all_consumers_resolve_the_same_term(db_mode):
    term = _mk_term(TENANT, "2033-2034", 1)
    _enroll(TENANT, term)
    _activate(term, tenant_id=TENANT)

    seen = {
        c["moduleCode"]: svc.resolve_current(module_code=c["moduleCode"], tenant_id=TENANT)["termId"]
        for c in svc.consumers()
    }
    assert len(set(seen.values())) == 1
    assert set(seen.values()) == {str(term)}

    # 激活同时收敛教务侧 is_current，避免出现第二个"当前学期"
    from app.models import AaTerm

    with _session() as db:
        currents = db.query(AaTerm).filter_by(tenant_id=TENANT, is_current=True).all()
    assert [int(t.id) for t in currents] == [term]


def test_t03_no_active_calendar_fails_closed_not_guessed(db_mode):
    _mk_term(TENANT, "2034-2035", 1)  # 只建学期不激活
    result = svc.resolve_current(tenant_id=TENANT)
    assert result["hasCurrent"] is False
    assert result["reasonCode"] == "NO_ACTIVE_CALENDAR"
    assert result["termId"] is None  # 绝不按系统日期猜一个


def test_t03_window_open_state_follows_the_asked_moment(db_mode):
    term = _mk_term(TENANT, "2035-2036", 1)
    _enroll(TENANT, term)
    _activate(term, tenant_id=TENANT)
    start = datetime(2026, 12, 1)
    svc.upsert_window(
        term,
        window_type="EXAM",
        module_code="ACADEMIC_AFFAIRS",
        start_at=start,
        end_at=start + timedelta(days=10),
        tenant_id=TENANT,
    )
    inside = svc.resolve_current(module_code="ACADEMIC_AFFAIRS", at=start + timedelta(days=1), tenant_id=TENANT)
    outside = svc.resolve_current(module_code="ACADEMIC_AFFAIRS", at=start + timedelta(days=30), tenant_id=TENANT)
    assert inside["windows"][0]["open"] is True
    assert outside["windows"][0]["open"] is False
    # 时间点只影响窗口，不影响哪一期是 ACTIVE
    assert inside["termId"] == outside["termId"] == str(term)


# ── SYS12-T04：定时激活幂等 ─────────────────────────────────────────────────
def test_t04_scheduled_activation_is_idempotent(db_mode):
    term = _mk_term(TENANT, "2036-2037", 1)
    _enroll(TENANT, term)
    _to(term, "VALIDATED", tenant_id=TENANT)
    _to(term, "SCHEDULED", tenant_id=TENANT, scheduled_at=datetime.utcnow() + timedelta(hours=1))

    # 未到点不激活
    early = svc.activate_due_calendars(now=datetime.utcnow())
    assert not any(item["termId"] == str(term) for item in early["activated"])
    assert svc.get_calendar(term, tenant_id=TENANT)["governanceStatus"] == "SCHEDULED"

    later = datetime.utcnow() + timedelta(hours=2)
    first_run = svc.activate_due_calendars(now=later)
    assert any(item["termId"] == str(term) for item in first_run["activated"])

    # 重复运行不得重复激活，也不得产生第二个 ACTIVE
    second_run = svc.activate_due_calendars(now=later)
    assert not any(item["termId"] == str(term) for item in second_run["activated"])
    assert svc.get_calendar(term, tenant_id=TENANT)["governanceStatus"] == "ACTIVE"


def test_t04_schedule_requires_future_time(db_mode):
    term = _mk_term(TENANT, "2037-2038", 1)
    _enroll(TENANT, term)
    _to(term, "VALIDATED", tenant_id=TENANT)
    with pytest.raises(AppException):
        _to(term, "SCHEDULED", tenant_id=TENANT, scheduled_at=datetime.utcnow() - timedelta(hours=1))


def test_t04_enroll_is_idempotent(db_mode):
    term = _mk_term(TENANT, "2038-2039", 1)
    first = _enroll(TENANT, term)
    second = _enroll(TENANT, term)
    assert first["termId"] == second["termId"] == str(term)
    assert second["governanceStatus"] == "DRAFT"


def test_governance_list_surfaces_ungoverned_terms_and_issues(db_mode):
    governed = _mk_term(TENANT, "2039-2040", 1)
    _mk_term(TENANT, "2039-2040", 2)  # 教务建了但未纳入治理
    _enroll(TENANT, governed)

    payload = svc.list_calendars(tenant_id=TENANT)
    assert len(payload["items"]) == 1
    assert len(payload["ungovernedTerms"]) == 1
    assert payload["consumers"]

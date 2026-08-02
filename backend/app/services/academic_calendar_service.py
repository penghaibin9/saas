"""SYS-12 学年学期、业务日历与统一切换。

边界
────
- ``t_aa_term``（教务）仍是学期时间轴的事实源，本服务**不复制学期主数据**；
- ``t_academic_calendar_governance`` 只承载"全校统一切换"的治理状态；
- 全系统读取当前学期的唯一入口是 :func:`resolve_current`，禁止各模块按系统日期猜当前学期。

为什么激活时会写 ``t_aa_term.is_current``
────────────────────────────────────────
"统一切换"这个动作的定义就是让全校（含教务既有链路）在同一时刻认同同一个学期。若治理侧
激活后不同步 ``is_current``，系统里会同时存在两个"当前学期"——正是本卡要消除的问题。
因此激活在同一事务内同步该标志，并写切换审计。除此之外本服务不修改任何教务业务终态
（成绩、归档、教学任务等一律只读判断）。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.academic_calendar import (ACTIVE_SENTINEL,
                                          CALENDAR_STATUS_ACTIVE,
                                          CALENDAR_STATUS_ARCHIVED,
                                          CALENDAR_STATUS_CLOSED,
                                          CALENDAR_STATUS_CLOSING,
                                          CALENDAR_STATUS_DRAFT,
                                          CALENDAR_STATUS_SCHEDULED,
                                          CALENDAR_STATUS_VALIDATED,
                                          CALENDAR_STATUSES,
                                          CALENDAR_TYPE_ACADEMIC,
                                          AcademicCalendarGovernance,
                                          CalendarTransitionEvent,
                                          CalendarWindow)

# ── CalendarConsumer 注册表 ──────────────────────────────────────────────────
# 每个按学期取值的模块必须在此登记，页面据此展示"切换会影响谁"。
# 登记不代表该模块已完成接入：``wired`` 表示是否已改为走 resolve_current()。
CALENDAR_CONSUMERS: tuple[dict[str, Any], ...] = (
    {"moduleCode": "ACADEMIC_AFFAIRS", "moduleName": "教务中心", "usage": "教学任务、考勤、成绩、归档", "wired": True},
    {"moduleCode": "STUDENT_AFFAIRS", "moduleName": "学工中心", "usage": "请假、违纪、资助批次", "wired": False},
    {"moduleCode": "INTERNSHIP", "moduleName": "岗位实习中心", "usage": "实习批次与周报周期", "wired": False},
    {"moduleCode": "GRADUATION", "moduleName": "毕业设计中心", "usage": "毕设批次与答辩场次", "wired": False},
    {"moduleCode": "EMPLOYMENT", "moduleName": "就业中心", "usage": "就业统计年度口径", "wired": False},
)

# 状态机：唯一权威。任何未登记的跳转一律拒绝。
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    CALENDAR_STATUS_DRAFT: frozenset({CALENDAR_STATUS_VALIDATED}),
    CALENDAR_STATUS_VALIDATED: frozenset({CALENDAR_STATUS_DRAFT, CALENDAR_STATUS_SCHEDULED, CALENDAR_STATUS_ACTIVE}),
    CALENDAR_STATUS_SCHEDULED: frozenset({CALENDAR_STATUS_VALIDATED, CALENDAR_STATUS_ACTIVE}),
    CALENDAR_STATUS_ACTIVE: frozenset({CALENDAR_STATUS_CLOSING}),
    # 结期期间发现还有业务未收尾，允许撤回到 ACTIVE；已 CLOSED 则不可逆。
    CALENDAR_STATUS_CLOSING: frozenset({CALENDAR_STATUS_ACTIVE, CALENDAR_STATUS_CLOSED}),
    CALENDAR_STATUS_CLOSED: frozenset({CALENDAR_STATUS_ARCHIVED}),
    CALENDAR_STATUS_ARCHIVED: frozenset(),
}

WINDOW_TYPES = ("TEACHING", "EXAM", "ORIENTATION", "INTERNSHIP", "GRADUATION", "EMPLOYMENT", "HOLIDAY")


def _floor_seconds(value: datetime | None) -> datetime | None:
    """截断到秒。MySQL DATETIME 会把微秒四舍五入（.9 进位到下一秒），
    否则刚排期/刚开窗的记录会因"生效时间比现在晚"而被误判为尚未生效。"""
    return value.replace(microsecond=0) if value else value


def _now() -> datetime:
    return _floor_seconds(datetime.utcnow())


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id() -> int | None:
    user = get_current_user_ctx() or {}
    raw = user.get("userId") or user.get("id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _session():
    return get_sessionmaker()()


def _term_model():
    from app.models import AaTerm

    return AaTerm


def _row(gov: AcademicCalendarGovernance, term: Any | None) -> dict:
    return {
        "termId": str(gov.term_id),
        "governanceStatus": gov.governance_status,
        "calendarType": gov.calendar_type,
        "timezone": gov.timezone,
        "version": int(gov.version or 0),
        "scheduledAt": gov.scheduled_at.isoformat() if gov.scheduled_at else None,
        "activatedAt": gov.activated_at.isoformat() if gov.activated_at else None,
        "closingStartedAt": gov.closing_started_at.isoformat() if gov.closing_started_at else None,
        "closedAt": gov.closed_at.isoformat() if gov.closed_at else None,
        "archivedAt": gov.archived_at.isoformat() if gov.archived_at else None,
        "lastTransitionReason": gov.last_transition_reason,
        "yearCode": getattr(term, "year_code", None),
        "termNo": getattr(term, "term_no", None),
        "termName": getattr(term, "term_name", None),
        "startDate": term.start_date.isoformat() if term is not None and term.start_date else None,
        "endDate": term.end_date.isoformat() if term is not None and term.end_date else None,
        "teachingWeeks": getattr(term, "teaching_weeks", None),
        "academicStatus": getattr(term, "status", None),
        "academicIsCurrent": bool(getattr(term, "is_current", False)),
        "allowedTransitions": sorted(ALLOWED_TRANSITIONS.get(gov.governance_status, frozenset())),
    }


def _load(db, tenant_id: int, term_id: int, *, lock: bool = False) -> AcademicCalendarGovernance:
    stmt = select(AcademicCalendarGovernance).where(
        AcademicCalendarGovernance.tenant_id == tenant_id,
        AcademicCalendarGovernance.term_id == term_id,
        AcademicCalendarGovernance.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    gov = db.scalars(stmt).first()
    if not gov:
        raise not_found("学期治理记录不存在")
    return gov


def _load_term(db, tenant_id: int, term_id: int):
    AaTerm = _term_model()
    return db.scalars(
        select(AaTerm).where(
            AaTerm.tenant_id == tenant_id, AaTerm.id == term_id, AaTerm.is_deleted.is_(False)
        )
    ).first()


# ── 唯一读取入口 ────────────────────────────────────────────────────────────
def resolve_current(
    *, module_code: str | None = None, at: datetime | None = None, tenant_id: int | None = None
) -> dict:
    """CalendarResolver：返回当前生效学期及该模块的窗口状态。

    ``at`` 只影响窗口判断，不改变哪一期是 ACTIVE——学期切换是显式治理动作，
    不允许按系统时间自动漂移（V6 SYS-12：禁止按系统日期猜当前学期）。
    """
    tid = _tenant_id(tenant_id)
    moment = at or _now()
    with _session() as db:
        gov = db.scalars(
            select(AcademicCalendarGovernance).where(
                AcademicCalendarGovernance.tenant_id == tid,
                AcademicCalendarGovernance.calendar_type == CALENDAR_TYPE_ACADEMIC,
                AcademicCalendarGovernance.active_key == ACTIVE_SENTINEL,
                AcademicCalendarGovernance.is_deleted.is_(False),
            )
        ).first()
        if not gov:
            return {
                "hasCurrent": False,
                "termId": None,
                "reasonCode": "NO_ACTIVE_CALENDAR",
                "message": "学校尚未激活当前学期，请先在系统管理·学年学期完成切换",
                "moduleCode": module_code,
                "windows": [],
            }
        term = _load_term(db, tid, gov.term_id)
        payload = _row(gov, term)
        payload.update({"hasCurrent": True, "moduleCode": module_code, "resolvedAt": moment.isoformat()})

        stmt = select(CalendarWindow).where(
            CalendarWindow.tenant_id == tid,
            CalendarWindow.term_id == gov.term_id,
            CalendarWindow.is_deleted.is_(False),
        )
        if module_code:
            stmt = stmt.where(CalendarWindow.module_code == module_code)
        windows = db.scalars(stmt).all()
        payload["windows"] = [
            {
                "windowType": w.window_type,
                "moduleCode": w.module_code,
                "startAt": w.start_at.isoformat(),
                "endAt": w.end_at.isoformat(),
                "open": bool(w.start_at <= moment <= w.end_at),
                "config": w.config_json or {},
            }
            for w in windows
        ]
        return payload


def consumers() -> list[dict]:
    """登记的日历消费者；页面用来展示切换影响面。"""
    return [dict(item) for item in CALENDAR_CONSUMERS]


# ── 治理查询 ────────────────────────────────────────────────────────────────
def list_calendars(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    AaTerm = _term_model()
    with _session() as db:
        govs = db.scalars(
            select(AcademicCalendarGovernance)
            .where(
                AcademicCalendarGovernance.tenant_id == tid,
                AcademicCalendarGovernance.is_deleted.is_(False),
            )
            .order_by(AcademicCalendarGovernance.term_id.desc())
        ).all()
        terms = {
            t.id: t
            for t in db.scalars(
                select(AaTerm).where(AaTerm.tenant_id == tid, AaTerm.is_deleted.is_(False))
            ).all()
        }
        rows = [_row(gov, terms.get(gov.term_id)) for gov in govs]

        # 未纳入治理的学期：教务建了学期但系统管理还没登记，页面要能看见并一键纳入。
        governed = {gov.term_id for gov in govs}
        ungoverned = [
            {
                "termId": str(t.id),
                "yearCode": t.year_code,
                "termNo": t.term_no,
                "termName": t.term_name,
                "academicStatus": t.status,
                "academicIsCurrent": bool(t.is_current),
            }
            for t in terms.values()
            if t.id not in governed
        ]

        # 一致性检查：教务侧多条 is_current 属于历史脏数据，必须暴露而不是静默修复。
        current_terms = [t for t in terms.values() if t.is_current]
        issues = []
        if len(current_terms) > 1:
            issues.append(
                {
                    "code": "MULTIPLE_ACADEMIC_CURRENT_TERM",
                    "message": f"教务侧存在 {len(current_terms)} 个当前学期标记，激活治理学期后将收敛为一个",
                    "termIds": [str(t.id) for t in current_terms],
                }
            )
        active = [r for r in rows if r["governanceStatus"] == CALENDAR_STATUS_ACTIVE]
        if active and current_terms and str(current_terms[0].id) != active[0]["termId"]:
            issues.append(
                {
                    "code": "ACADEMIC_CURRENT_MISMATCH",
                    "message": "教务当前学期与全校激活学期不一致，请重新激活以收敛",
                    "termIds": [active[0]["termId"]],
                }
            )
        return {"items": rows, "ungovernedTerms": ungoverned, "issues": issues, "consumers": consumers()}


def get_calendar(term_id: int, *, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        gov = _load(db, tid, int(term_id))
        payload = _row(gov, _load_term(db, tid, gov.term_id))
        payload["blockers"] = _closing_blockers(db, tid, gov.term_id)
        payload["windows"] = [
            {
                "windowType": w.window_type,
                "moduleCode": w.module_code,
                "startAt": w.start_at.isoformat(),
                "endAt": w.end_at.isoformat(),
                "config": w.config_json or {},
                "version": int(w.version or 0),
            }
            for w in db.scalars(
                select(CalendarWindow).where(
                    CalendarWindow.tenant_id == tid,
                    CalendarWindow.term_id == gov.term_id,
                    CalendarWindow.is_deleted.is_(False),
                )
            ).all()
        ]
        payload["transitions"] = [
            {
                "fromStatus": e.from_status,
                "toStatus": e.to_status,
                "reason": e.reason,
                "actorUserId": str(e.actor_user_id) if e.actor_user_id else None,
                "blockers": e.blockers_json or {},
                "traceId": e.trace_id,
                "occurredAt": e.created_at.isoformat() if e.created_at else None,
            }
            for e in db.scalars(
                select(CalendarTransitionEvent)
                .where(
                    CalendarTransitionEvent.tenant_id == tid,
                    CalendarTransitionEvent.term_id == gov.term_id,
                )
                .order_by(CalendarTransitionEvent.id.desc())
                .limit(50)
            ).all()
        ]
        return payload


def enroll_term(term_id: int, *, timezone: str = "Asia/Shanghai", tenant_id: int | None = None) -> dict:
    """把教务已建的学期纳入全校治理（幂等）。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        term = _load_term(db, tid, int(term_id))
        if not term:
            raise not_found("学期不存在")
        existing = db.scalars(
            select(AcademicCalendarGovernance).where(
                AcademicCalendarGovernance.tenant_id == tid,
                AcademicCalendarGovernance.term_id == int(term_id),
            )
        ).first()
        if existing:
            return _row(existing, term)
        gov = AcademicCalendarGovernance(
            tenant_id=tid,
            term_id=int(term_id),
            calendar_type=CALENDAR_TYPE_ACADEMIC,
            timezone=timezone,
            governance_status=CALENDAR_STATUS_DRAFT,
            active_key=None,
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(gov)
        db.flush()
        _write_event(db, tid, int(term_id), None, CALENDAR_STATUS_DRAFT, "纳入全校学期治理", {})
        db.commit()
        return _row(gov, term)


# ── 结期阻断检查 ────────────────────────────────────────────────────────────
def _closing_blockers(db, tenant_id: int, term_id: int) -> list[dict]:
    """只读判断：本学期还有哪些业务没收尾。系统管理不代业务模块确认业务事实。"""
    from app.models import AaArchiveBatch, AaGradeTask

    blockers: list[dict] = []

    unpublished = db.scalar(
        select(func.count())
        .select_from(AaGradeTask)
        .where(
            AaGradeTask.tenant_id == tenant_id,
            AaGradeTask.term_id == term_id,
            AaGradeTask.is_deleted.is_(False),
            AaGradeTask.status != "PUBLISHED",
        )
    )
    if unpublished:
        blockers.append(
            {
                "code": "GRADE_NOT_PUBLISHED",
                "ownerModule": "ACADEMIC_AFFAIRS",
                "count": int(unpublished),
                "message": f"还有 {int(unpublished)} 个成绩录入任务未发布",
            }
        )

    archived = db.scalar(
        select(func.count())
        .select_from(AaArchiveBatch)
        .where(
            AaArchiveBatch.tenant_id == tenant_id,
            AaArchiveBatch.term_id == term_id,
            AaArchiveBatch.is_deleted.is_(False),
            AaArchiveBatch.archived_at.is_not(None),
        )
    )
    if not archived:
        blockers.append(
            {
                "code": "TERM_NOT_ARCHIVED",
                "ownerModule": "ACADEMIC_AFFAIRS",
                "count": 0,
                "message": "本学期尚无已确认归档的批次",
            }
        )
    return blockers


def closing_blockers(term_id: int, *, tenant_id: int | None = None) -> list[dict]:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        return _closing_blockers(db, tid, int(term_id))


def _write_event(
    db, tenant_id: int, term_id: int, from_status: str | None, to_status: str, reason: str | None, blockers: Any
) -> str:
    trace_id = uuid.uuid4().hex
    db.add(
        CalendarTransitionEvent(
            tenant_id=tenant_id,
            term_id=term_id,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=_actor_id(),
            reason=reason,
            blockers_json={"items": blockers} if blockers else None,
            trace_id=trace_id,
            created_by=_actor_id(),
        )
    )
    return trace_id


# ── 状态机 ──────────────────────────────────────────────────────────────────
def transition(
    term_id: int,
    target_status: str,
    *,
    reason: str,
    expected_version: int,
    scheduled_at: datetime | None = None,
    force: bool = False,
    tenant_id: int | None = None,
) -> dict:
    """统一状态跳转入口。所有写操作必须带 ``expected_version``。

    ``force`` 只对结期阻断生效（学校确认愿意带着未收尾业务结期），不能跳过状态机本身。
    """
    tid = _tenant_id(tenant_id)
    target = str(target_status or "").upper()
    if target not in CALENDAR_STATUSES:
        raise AppException("VALIDATION_ERROR", f"未知的学期状态：{target}")
    if not str(reason or "").strip():
        raise AppException("VALIDATION_ERROR", "状态变更必须填写原因")

    with _session() as db:
        gov = _load(db, tid, int(term_id), lock=True)
        if int(gov.version or 0) != int(expected_version):
            raise AppException(
                "VERSION_CONFLICT",
                "该学期已被其他人修改，请刷新后重试",
                http_status=409,
                details={"currentVersion": int(gov.version or 0)},
            )
        current = gov.governance_status
        if target == current:
            return _row(gov, _load_term(db, tid, gov.term_id))  # 幂等
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise AppException(
                "STATE_TRANSITION_DENIED",
                f"不允许从 {current} 变更为 {target}",
                http_status=409,
                details={"allowed": sorted(ALLOWED_TRANSITIONS.get(current, frozenset()))},
            )

        blockers: list[dict] = []
        now = _now()

        if target == CALENDAR_STATUS_SCHEDULED:
            scheduled_at = _floor_seconds(scheduled_at)
            if not scheduled_at:
                raise AppException("VALIDATION_ERROR", "排期激活必须提供计划时间")
            if scheduled_at <= now:
                raise AppException("VALIDATION_ERROR", "排期时间必须晚于当前时间")
            gov.scheduled_at = scheduled_at

        if target == CALENDAR_STATUS_ACTIVE:
            _assert_no_other_active(db, tid, gov.term_id)
            gov.active_key = ACTIVE_SENTINEL
            gov.activated_at = now
            _sync_academic_current_term(db, tid, gov.term_id)
        else:
            # 离开 ACTIVE 时必须清空哨兵，否则唯一约束会挡住下一期激活。
            gov.active_key = None

        if target == CALENDAR_STATUS_CLOSING:
            blockers = _closing_blockers(db, tid, gov.term_id)
            if blockers and not force:
                _write_event(db, tid, gov.term_id, current, current, f"结期被阻断：{reason}", blockers)
                db.commit()
                raise AppException(
                    "TERM_CLOSING_BLOCKED",
                    "本学期仍有未收尾业务，无法进入结期",
                    http_status=409,
                    details={"blockers": blockers},
                )
            gov.closing_started_at = now

        if target == CALENDAR_STATUS_CLOSED:
            gov.closed_at = now
        if target == CALENDAR_STATUS_ARCHIVED:
            gov.archived_at = now

        gov.governance_status = target
        gov.last_transition_reason = reason
        gov.updated_by = _actor_id()
        gov.version = int(gov.version or 0) + 1
        trace_id = _write_event(db, tid, gov.term_id, current, target, reason, blockers)

        try:
            db.commit()
        except IntegrityError as exc:  # 并发激活由 uk_calendar_single_active 兜底
            db.rollback()
            raise AppException(
                "TERM_ACTIVATION_CONFLICT",
                "已有其他学期处于激活状态，请先对其开始结期",
                http_status=409,
            ) from exc

        _audit(target, gov.term_id, reason, trace_id, blockers)
        db.refresh(gov)
        return _row(gov, _load_term(db, tid, gov.term_id))


def _assert_no_other_active(db, tenant_id: int, term_id: int) -> None:
    other = db.scalars(
        select(AcademicCalendarGovernance).where(
            AcademicCalendarGovernance.tenant_id == tenant_id,
            AcademicCalendarGovernance.calendar_type == CALENDAR_TYPE_ACADEMIC,
            AcademicCalendarGovernance.active_key == ACTIVE_SENTINEL,
            AcademicCalendarGovernance.term_id != term_id,
            AcademicCalendarGovernance.is_deleted.is_(False),
        )
    ).first()
    if other:
        raise AppException(
            "TERM_ACTIVATION_CONFLICT",
            "已有其他学期处于激活状态，请先对其开始结期",
            http_status=409,
            details={"activeTermId": str(other.term_id)},
        )


def _sync_academic_current_term(db, tenant_id: int, term_id: int) -> None:
    """统一切换：让教务既有链路与全校激活学期一致（见模块 docstring）。"""
    AaTerm = _term_model()
    db.query(AaTerm).filter(
        AaTerm.tenant_id == tenant_id, AaTerm.is_current.is_(True), AaTerm.id != term_id
    ).update({"is_current": False}, synchronize_session=False)
    db.query(AaTerm).filter(AaTerm.tenant_id == tenant_id, AaTerm.id == term_id).update(
        {"is_current": True}, synchronize_session=False
    )


def _audit(target: str, term_id: int, reason: str, trace_id: str, blockers: Any) -> None:
    try:
        from app.services import audit_log

        audit_log.record(
            "ACADEMIC_CALENDAR_TRANSITION",
            f"academicCalendar:{term_id}",
            detail={"toStatus": target, "reason": reason, "traceId": trace_id, "blockers": blockers or []},
        )
    except Exception:  # noqa: BLE001 - 审计失败不得影响主流程
        pass


# ── 定时激活 ────────────────────────────────────────────────────────────────
def activate_due_calendars(*, now: datetime | None = None) -> dict:
    """把到期的 SCHEDULED 学期激活。幂等：重复运行不会重复激活，也不会产生第二个 ACTIVE。

    跨租户执行，逐租户独立判断；单个租户失败不影响其他租户。
    """
    moment = now or _now()
    activated: list[dict] = []
    skipped: list[dict] = []
    with _session() as db:
        due = db.scalars(
            select(AcademicCalendarGovernance).where(
                AcademicCalendarGovernance.governance_status == CALENDAR_STATUS_SCHEDULED,
                AcademicCalendarGovernance.scheduled_at.is_not(None),
                AcademicCalendarGovernance.scheduled_at <= moment,
                AcademicCalendarGovernance.is_deleted.is_(False),
            )
        ).all()
        targets = [(g.tenant_id, g.term_id, int(g.version or 0)) for g in due]

    for tenant_id, term_id, version in targets:
        try:
            transition(
                term_id,
                CALENDAR_STATUS_ACTIVE,
                reason="定时排期自动激活",
                expected_version=version,
                tenant_id=tenant_id,
            )
            activated.append({"tenantId": str(tenant_id), "termId": str(term_id)})
        except AppException as exc:
            skipped.append({"tenantId": str(tenant_id), "termId": str(term_id), "reason": exc.code})
    return {"activated": activated, "skipped": skipped, "checkedAt": moment.isoformat()}


# ── 业务窗口 ────────────────────────────────────────────────────────────────
def upsert_window(
    term_id: int,
    *,
    window_type: str,
    module_code: str,
    start_at: datetime,
    end_at: datetime,
    config: dict | None = None,
    expected_version: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    wtype = str(window_type or "").upper()
    if wtype not in WINDOW_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知窗口类型：{wtype}", details={"allowed": list(WINDOW_TYPES)})
    if not module_code:
        raise AppException("VALIDATION_ERROR", "窗口必须归属一个模块")
    start_at = _floor_seconds(start_at)
    end_at = _floor_seconds(end_at)
    if end_at <= start_at:
        raise AppException("VALIDATION_ERROR", "窗口结束时间必须晚于开始时间")

    with _session() as db:
        gov = _load(db, tid, int(term_id))
        if gov.governance_status in (CALENDAR_STATUS_CLOSED, CALENDAR_STATUS_ARCHIVED):
            raise AppException("TERM_CLOSED", "学期已结束，不能再调整业务窗口", http_status=409)
        existing = db.scalars(
            select(CalendarWindow).where(
                CalendarWindow.tenant_id == tid,
                CalendarWindow.term_id == int(term_id),
                CalendarWindow.window_type == wtype,
                CalendarWindow.module_code == module_code,
                CalendarWindow.is_deleted.is_(False),
            )
        ).first()
        if existing:
            if expected_version is not None and int(existing.version or 0) != int(expected_version):
                raise AppException("VERSION_CONFLICT", "该窗口已被其他人修改，请刷新后重试", http_status=409)
            existing.start_at = start_at
            existing.end_at = end_at
            existing.config_json = config or {}
            existing.updated_by = _actor_id()
            existing.version = int(existing.version or 0) + 1
            row = existing
        else:
            row = CalendarWindow(
                tenant_id=tid,
                term_id=int(term_id),
                window_type=wtype,
                module_code=module_code,
                start_at=start_at,
                end_at=end_at,
                config_json=config or {},
                created_by=_actor_id(),
                updated_by=_actor_id(),
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "windowType": row.window_type,
            "moduleCode": row.module_code,
            "startAt": row.start_at.isoformat(),
            "endAt": row.end_at.isoformat(),
            "config": row.config_json or {},
            "version": int(row.version or 0),
        }

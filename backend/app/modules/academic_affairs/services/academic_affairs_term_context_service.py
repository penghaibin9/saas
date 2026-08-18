"""A-C1 Term Context Resolver（学期上下文解析器）。

唯一职责：把现有两个层次的事实适配成一个可消费的当前学期上下文：

1. SYS-12 ``academic_calendar_service.resolve_current()`` 是全校 CalendarResolver，
   A-C1 不重复解释 ``AcademicCalendarGovernance``；
2. 尚未纳入 SYS-12 治理的历史学校，暂时兼容 ``AaTerm.is_current``；
3. 兼容路径出现多个 current 时 fail-closed，绝不 ``first()`` 猜一个；
4. 本模块只读，不创建第二 Term / Calendar truth，不修改治理状态机。

B/C/D 后续消费者应复用这个 resolver，而不是再次按 ``is_current`` 或系统日期猜当前学期。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models import AaTerm
from app.services.db_service import _tid

GOVERNANCE_SWITCH_ROUTE = "/admin/system/academic-calendar"


@dataclass(frozen=True)
class TermContextResolution:
    term: Any | None
    authority: str
    can_direct_switch: bool
    switch_route: str | None
    switch_hint: str


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or _tid() or 0)
    if tenant_id <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，无法解析当前学期")
    return tenant_id


def resolve_current_term(
    db: Session,
    *,
    tenant_id: int | None = None,
    allow_legacy_compat: bool = True,
) -> TermContextResolution:
    """Resolve one current ``AaTerm`` through SYS-12 first, then strict legacy compatibility."""
    from app.services import academic_calendar_service as calendar

    tid = _tenant_id(tenant_id)
    governance = calendar.resolve_current(
        module_code="ACADEMIC_AFFAIRS",
        tenant_id=tid,
    )
    if governance.get("hasCurrent"):
        term_id = int(governance["termId"])
        term = db.scalars(
            select(AaTerm).where(
                AaTerm.tenant_id == tid,
                AaTerm.id == term_id,
                AaTerm.is_deleted.is_(False),
            )
        ).first()
        if not term:
            raise AppException(
                "DATA_CONFLICT",
                "全校当前学期治理记录未命中有效教务学期，禁止猜测当前学期",
                details={"termId": str(term_id), "authoritySource": "CALENDAR_GOVERNANCE"},
                http_status=409,
            )
        return TermContextResolution(
            term=term,
            authority="CALENDAR_GOVERNANCE",
            can_direct_switch=False,
            switch_route=GOVERNANCE_SWITCH_ROUTE,
            switch_hint=(
                "当前学校已启用全校学期治理；教务侧只读当前结论，"
                "切换请到“学年学期与业务日历”统一执行。"
            ),
        )

    if not allow_legacy_compat:
        return TermContextResolution(
            term=None,
            authority="NO_ACTIVE_GOVERNANCE",
            can_direct_switch=False,
            switch_route=GOVERNANCE_SWITCH_ROUTE,
            switch_hint="学校尚未激活全校学期治理。",
        )

    legacy_rows = db.scalars(
        select(AaTerm).where(
            AaTerm.tenant_id == tid,
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )
    ).all()
    if len(legacy_rows) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "学校存在多个当前学期，且尚未完成全校学期治理切换，禁止随机选择",
            details={"termIds": [str(term.id) for term in legacy_rows]},
            http_status=409,
        )
    return TermContextResolution(
        term=legacy_rows[0] if legacy_rows else None,
        authority="AA_TERM_COMPAT",
        can_direct_switch=True,
        switch_route=None,
        switch_hint="当前学校尚未启用全校学期治理，暂保留教务当前学期兼容切换。",
    )

"""AA-DASHBOARD-01 readiness 真实模型兼容守卫。"""
from __future__ import annotations

from . import academic_affairs_dashboard_readiness_service as _base


def _operation_risks(db, term):
    """只使用当前模型真实存在的字段，不为调停课虚构term_id。"""
    from app.models import AaScheduleChange, AaStatusChange, AcademicWarning

    risks = []
    pending_changes = db.query(AaScheduleChange).filter(
        AaScheduleChange.tenant_id == _base._tid(),
        AaScheduleChange.status.in_(["SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"]),
        AaScheduleChange.is_deleted.is_(False),
    ).count()
    if pending_changes:
        risks.append(_base._item(
            key="SCHEDULE_CHANGE_PENDING",
            severity="RISK",
            title="存在在途调停课申请",
            summary=f"{pending_changes} 条调课、停课或补课申请尚未生效。",
            rule_code="DASHBOARD_SCHEDULE_CHANGE_PENDING",
            count=pending_changes,
            route="/admin/academic-affairs/schedule-changes",
            owner_role="学院教务员 / 教务处",
        ))

    pending_status = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _base._tid(),
        AaStatusChange.status.in_(["SUBMITTED", "IN_REVIEW"]),
        AaStatusChange.is_deleted.is_(False),
    ).count()
    if pending_status:
        risks.append(_base._item(
            key="STATUS_CHANGE_PENDING",
            severity="RISK",
            title="存在在途学籍异动",
            summary=f"{pending_status} 条学籍异动尚未完成审批或生效。",
            rule_code="DASHBOARD_STATUS_CHANGE_PENDING",
            count=pending_status,
            route="/admin/academic-affairs/status-changes",
            owner_role="学院教务员 / 教务处",
        ))

    high_warnings = db.query(AcademicWarning).filter(
        AcademicWarning.tenant_id == _base._tid(),
        AcademicWarning.level == "HIGH",
        AcademicWarning.status == "PENDING_HANDLE",
        AcademicWarning.record_status == "ACTIVE",
        AcademicWarning.is_deleted.is_(False),
    ).count()
    if high_warnings:
        risks.append(_base._item(
            key="HIGH_WARNING_PENDING",
            severity="RISK",
            title="高等级学业预警待处置",
            summary=f"{high_warnings} 条高等级学业预警尚未形成闭环。",
            rule_code="DASHBOARD_HIGH_WARNING_PENDING",
            count=high_warnings,
            route="/admin/academic-affairs/warnings",
            owner_role="辅导员 / 学院教务员",
        ))
    return risks


_base._operation_risks = _operation_risks

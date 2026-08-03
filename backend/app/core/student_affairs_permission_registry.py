"""Student-affairs permission registry: the only authoritative permission code set."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StudentAffairsPermission:
    code: str
    label: str
    domain: str
    risk_level: str
    allowed_scopes: tuple[str, ...]
    deprecated_aliases: tuple[str, ...] = ()


_PERMISSION_CODES = (
    "studentAffairs.activity.confirm",
    "studentAffairs.activity.create",
    "studentAffairs.activity.publish",
    "studentAffairs.activity.view",
    "studentAffairs.aid.adjust",
    "studentAffairs.aid.approve",
    "studentAffairs.aid.batch.manage",
    "studentAffairs.aid.counselorReview",
    "studentAffairs.aid.create",
    "studentAffairs.aid.sensitiveView",
    "studentAffairs.aid.view",
    "studentAffairs.archive.batch.manage",
    "studentAffairs.archive.psySensitive",
    "studentAffairs.archive.view",
    "studentAffairs.class.cadre.manage",
    "studentAffairs.class.create",
    "studentAffairs.class.view",
    "studentAffairs.club.manage",
    "studentAffairs.club.view",
    "studentAffairs.config.manage",
    "studentAffairs.counselorEval.appeal.create",
    "studentAffairs.counselorEval.manage",
    "studentAffairs.counselorEval.view",
    "studentAffairs.dashboard.view",
    "studentAffairs.discipline.appeal.create",
    "studentAffairs.discipline.appeal.review",
    "studentAffairs.discipline.approve",
    "studentAffairs.discipline.create",
    "studentAffairs.discipline.deliver",
    "studentAffairs.discipline.remove.approve",
    "studentAffairs.discipline.remove.create",
    "studentAffairs.discipline.view",
    "studentAffairs.dorm.allocation.manage",
    "studentAffairs.dorm.check.view",
    "studentAffairs.dorm.exception.handle",
    "studentAffairs.dorm.inspection.manage",
    "studentAffairs.dorm.resource.manage",
    "studentAffairs.dorm.transfer.approve",
    "studentAffairs.dorm.transfer.create",
    "studentAffairs.dorm.view",
    "studentAffairs.funding.approve",
    "studentAffairs.funding.create",
    "studentAffairs.funding.disburse.manage",
    "studentAffairs.funding.loan.manage",
    "studentAffairs.funding.project.manage",
    "studentAffairs.funding.publicity.manage",
    "studentAffairs.funding.reduction.manage",
    "studentAffairs.funding.sensitiveView",
    "studentAffairs.funding.view",
    "studentAffairs.funding.workstudy.manage",
    "studentAffairs.homeSchool.record.create",
    "studentAffairs.homeSchool.view",
    "studentAffairs.league.manage",
    "studentAffairs.league.view",
    "studentAffairs.leave.approve",
    "studentAffairs.leave.cancelLeaveConfirm",
    "studentAffairs.leave.create",
    "studentAffairs.leave.export",
    "studentAffairs.leave.extension.approve",
    "studentAffairs.leave.overdue.handle",
    "studentAffairs.leave.view",
    "studentAffairs.mental.manage",
    "studentAffairs.org.manage",
    "studentAffairs.org.view",
    "studentAffairs.orientation.view",
    "studentAffairs.risk.assign",
    "studentAffairs.risk.close",
    "studentAffairs.risk.create",
    "studentAffairs.risk.escalate",
    "studentAffairs.risk.handle",
    "studentAffairs.risk.psyDetail.view",
    "studentAffairs.risk.reopen",
    "studentAffairs.risk.transfer",
    "studentAffairs.risk.view",
    "studentAffairs.stats.view",
    "studentAffairs.student.view",
    "studentAffairs.talk.create",
    "studentAffairs.talk.view",
)

_CRITICAL_DOMAINS = {"mental", "discipline"}
_HIGH_DOMAINS = {"aid", "funding", "risk", "archive", "student", "homeSchool"}
_SCOPE_BY_DOMAIN = {
    "dorm": ("TENANT_ALL", "DORM_BUILDING", "CLASS"),
    "mental": ("TENANT_ALL", "STUDENT"),
    "risk": ("TENANT_ALL", "COLLEGE", "CLASS", "STUDENT"),
}
_ACTION_LABELS = {
    "view": "查看", "create": "新增", "manage": "维护", "approve": "审批",
    "review": "复核", "export": "导出", "assign": "指派", "handle": "处置",
    "transfer": "转交", "escalate": "升级", "close": "关闭", "reopen": "重开",
    "publish": "发布", "confirm": "确认", "deliver": "送达", "adjust": "调整",
}


def _definition(code: str) -> StudentAffairsPermission:
    parts = code.split(".")
    domain = parts[1] if len(parts) > 1 else "unknown"
    action = parts[-1] if parts else "view"
    risk = "CRITICAL" if domain in _CRITICAL_DOMAINS and action not in {"view"} else (
        "HIGH" if domain in _HIGH_DOMAINS or action in {"approve", "review", "export", "deliver"} else "MEDIUM"
    )
    scopes = _SCOPE_BY_DOMAIN.get(domain, ("TENANT_ALL", "COLLEGE", "CLASS"))
    label = f"{domain}·{_ACTION_LABELS.get(action, action)}"
    return StudentAffairsPermission(code, label, domain, risk, scopes)


STUDENT_AFFAIRS_PERMISSIONS = tuple(_definition(code) for code in _PERMISSION_CODES)
STUDENT_AFFAIRS_PERMISSION_BY_CODE = {item.code: item for item in STUDENT_AFFAIRS_PERMISSIONS}
STUDENT_AFFAIRS_PERMISSION_CODES = frozenset(STUDENT_AFFAIRS_PERMISSION_BY_CODE)



# 教师移动端因路径包含动态业务分支，无法只靠一个 Depends 表达的精确权限矩阵。
# 路由安全门与审计脚本都从此处读取，禁止另建第二份权限集合。
STUDENT_AFFAIRS_MOBILE_DIRECT_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "/api/v1/mobile/teacher/affairs/student-candidates": (
        "studentAffairs.talk.create",
        "studentAffairs.mental.manage",
        "studentAffairs.risk.psyDetail.view",
    ),
    "/api/v1/mobile/teacher/affairs/activities/ongoing": (
        "studentAffairs.activity.publish",
    ),
    "/api/v1/mobile/teacher/affairs/activities/{activity_id}/checkin-token": (
        "studentAffairs.activity.publish",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/{kind}": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/repair": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/repair/metrics": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/repair/jobs": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
    "/api/v1/mobile/teacher/affairs/appeals/repair/jobs/{job_id}/requeue": (
        "studentAffairs.aid.approve",
        "studentAffairs.funding.publicity.manage",
        "studentAffairs.discipline.appeal.review",
        "studentAffairs.activity.confirm",
    ),
}

def export_catalog() -> list[dict]:
    rows = []
    for item in STUDENT_AFFAIRS_PERMISSIONS:
        raw = asdict(item)
        rows.append({
            "permissionCode": raw["code"],
            "label": raw["label"],
            "domain": raw["domain"],
            "riskLevel": raw["risk_level"],
            "allowedScopes": list(raw["allowed_scopes"]),
            "deprecatedAliases": list(raw["deprecated_aliases"]),
        })
    return rows

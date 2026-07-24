"""P2 合规规则：批次启用后冻结，评估只读取批次快照。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

# 新合规项默认 required=False，避免历史批次/未配置模板被新门禁误杀；
# 学校启用 ACTIVE 合规模板或批次显式配置后可改为 True。
# agreement/insurance 默认 True，与既有 onboard 规则对齐。
DEFAULT_COMPLIANCE_RULES = {
    "enterpriseAccess": {
        "label": "企业准入考察", "required": False, "severity": "BLOCK",
        "requireQualificationReview": True, "requireOnsiteInspection": False,
        "inspectionValidDays": 365,
    },
    "studentConsent": {
        "label": "学生知情确认", "required": False, "severity": "BLOCK",
        "requireStudentConsent": True, "requireGuardianConsentForMinor": True,
    },
    "guardianConsent": {
        "label": "监护人知情确认", "required": False, "severity": "BLOCK",
    },
    "safetyEducation": {
        "label": "岗前安全教育", "required": False, "severity": "BLOCK",
        "minStudyMinutes": 60, "passScore": 80, "maxAttempts": 3, "requireCommitment": True,
    },
    "insurance": {
        "label": "实习保险", "required": True, "severity": "BLOCK",
        "requireVerified": True, "mustCoverInternshipPeriod": True,
    },
    "agreement": {
        "label": "三方协议", "required": True, "severity": "BLOCK",
        "requireEffectiveBeforeOnboard": True,
    },
    "specialFiling": {
        "label": "特殊实习备案", "required": False, "severity": "BLOCK",
        "crossProvinceRequired": True, "highRiskPositionRequired": True, "nightShiftRequired": True,
    },
    "workRights": {
        "label": "岗位劳动权益", "required": False, "severity": "BLOCK",
        "maxDailyHours": 8, "maxWeeklyHours": 40, "nightShiftAllowed": False,
        "overtimeAllowed": False, "minRemunerationRequired": False,
    },
    "emergency": {
        "label": "应急预案", "required": False, "severity": "BLOCK",
        "requireEmergencyPlan": True, "requireEnterpriseContact": True,
    },
    "advisor": {
        "label": "校内指导教师", "required": True, "severity": "BLOCK",
    },
}


def get_batch_compliance_rules(db, batch) -> dict:
    config = (batch.rules_config or {}) if batch else {}
    base = deepcopy(DEFAULT_COMPLIANCE_RULES)
    patch = config.get("compliance") or {}
    for key, value in patch.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value
    return base


def rule_version_label(batch) -> str:
    return f"batch-{getattr(batch, 'id', 'unknown')}-rv{getattr(batch, 'rules_version', 1) or 1}"


def merge_compliance(batch, compliance: dict) -> dict:
    cfg = deepcopy(batch.rules_config or {})
    merged = get_batch_compliance_rules(None, type("B", (), {"rules_config": {"compliance": compliance}})())
    # re-merge against defaults cleanly
    base = deepcopy(DEFAULT_COMPLIANCE_RULES)
    for key, value in (compliance or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value
    cfg["compliance"] = base
    batch.rules_config = cfg
    return base


def now_iso() -> str:
    return datetime.utcnow().isoformat()

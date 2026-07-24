"""岗位劳动权益合规检查，返回机器可读的 blocker/warning。"""
from __future__ import annotations

from datetime import datetime


def evaluate_position_compliance(position, student, rules) -> dict:
    cfg = (rules or {}).get("workRights", rules or {})
    blockers, warnings = [], []
    if not position:
        blockers.append("岗位不存在")
    else:
        maximum = cfg.get("maxDailyHours", 8)
        if position.daily_hours is not None and position.daily_hours > maximum:
            blockers.append(f"日工作时长超过 {maximum} 小时")
        maximum_week = cfg.get("maxWeeklyHours", 44)
        if position.weekly_hours is not None and position.weekly_hours > maximum_week:
            blockers.append(f"周工作时长超过 {maximum_week} 小时")
        if position.hazardous_flag:
            blockers.append("岗位标记为高风险/危险作业")
        if position.prohibited_reason:
            blockers.append(f"岗位禁止安排：{position.prohibited_reason}")
        if position.night_shift and not cfg.get("nightShiftAllowed", False):
            blockers.append("夜班不被当前批次规则允许")
        elif position.night_shift:
            warnings.append("含夜班，须完成特殊备案后上岗")
        if not position.work_content:
            warnings.append("未维护岗位工作内容")
        if position.remuneration_type and position.remuneration_amount is None:
            warnings.append("报酬类型已填写但金额缺失")
    batch_id = getattr(position, "batch_id", None)
    version = f"batch-{batch_id or 'unknown'}-rights"
    return {"passed": not blockers, "blockers": blockers, "warnings": warnings,
            "ruleVersion": version, "checkedAt": datetime.utcnow().isoformat()}

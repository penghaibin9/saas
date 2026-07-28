"""风险转办终态收口。

转办动作已经显式选择并校验新责任人，完成后应直接进入 ASSIGNED；
若停在 TRANSFERRED，前端没有“接收转办”动作，PROCESS 也不允许执行，记录会成为死状态。
保留 TRANSFERRED 的历史迁移入口，仅修正新 TRANSFER 动作的目标状态。
"""
from __future__ import annotations


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import affairs_risk_service as risk

    rule = dict(risk.RISK_TRANSITIONS.get("TRANSFER") or {})
    rule["to"] = "ASSIGNED"
    risk.RISK_TRANSITIONS["TRANSFER"] = rule
    _INSTALLED = True

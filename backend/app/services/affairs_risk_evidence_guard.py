"""风险动作证据安全门：高影响状态转换必须留下有效说明，消息禁止空收件人。"""
from __future__ import annotations

from app.core.exceptions import AppException

_INSTALLED = False


def _text(value, label: str, minimum: int = 5, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}需{minimum}-{maximum}字")
    return text


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_risk_service as risk

    old_message = risk._msg
    old_follow = risk.follow
    old_transfer = risk.transfer
    old_escalate = risk.escalate
    old_takeover = risk.takeover
    old_reopen = risk.reopen

    def message(db, receiver_id, title, content, mtype, risk_id):
        try:
            receiver = int(receiver_id or 0)
        except (TypeError, ValueError):
            receiver = 0
        if receiver <= 0:
            return None
        return old_message(db, receiver, title, content, mtype, risk_id)

    def follow(risk_id, user, content="", expected_version=None):
        return old_follow(risk_id, user, _text(content, "跟进记录"), expected_version)

    def transfer(risk_id, user, new_owner_id, reason="", expected_version=None):
        return old_transfer(risk_id, user, new_owner_id, _text(reason, "转办原因"), expected_version)

    def escalate(risk_id, user, reason="", expected_version=None):
        return old_escalate(risk_id, user, _text(reason, "升级依据"), expected_version)

    def takeover(risk_id, user, content="", expected_version=None):
        return old_takeover(risk_id, user, _text(content, "接管说明"), expected_version)

    def reopen(risk_id, user, reason="", expected_version=None):
        return old_reopen(risk_id, user, _text(reason, "重开原因"), expected_version)

    risk._msg = message
    risk.follow = follow
    risk.transfer = transfer
    risk.escalate = escalate
    risk.takeover = takeover
    risk.reopen = reopen
    _INSTALLED = True

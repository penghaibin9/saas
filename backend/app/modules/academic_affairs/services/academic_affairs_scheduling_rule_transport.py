"""V2-03 排课规则请求体兼容层。

历史总路由把 ruleValue 固定声明为 dict，导致列表、整数、布尔规则无法通过 Pydantic。
本层接受 `{value: 实际值}` 传输包并在进入最终规则策略前解包；数据库仍保存原始业务类型。
周次范围等原有对象请求保持兼容。
"""
from __future__ import annotations

from . import academic_affairs_scheduling_rule_policy as _policy
from . import academic_affairs_scheduling_service as _scheduling


class _RuleBodyProxy:
    def __init__(self, body):
        self._body = body

    @property
    def ruleValue(self):
        raw = getattr(self._body, "ruleValue", None)
        if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
            return raw.get("value")
        return raw

    def __getattr__(self, name):
        return getattr(self._body, name)


def unwrap_transport_value(raw):
    if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
        return raw.get("value")
    return raw


def save_rule(user, body):
    return _policy.save_rule(user, _RuleBodyProxy(body))


_scheduling.save_rule = save_rule

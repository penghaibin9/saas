"""V3 §13 移动端可观测性门禁（深审 P1-13）。

拆成学生册/教师册之后，万人学校出现"偶发慢 / 跳错对象"时很难定位。本模块登记
V3 明确要求的一组计数器，让这些问题在日志与健康探针里留下痕迹。

**隐私红线（§13）**：只记 traceId 与匿名维度——路由键、动作键、错误码、耗时分桶。
不记学号、姓名、手机号、消息正文、SQL 文本或参数。所有 record_* 入口都只接受
枚举/短标识，不接受自由文本正文。
"""
from __future__ import annotations

import threading
from collections import Counter

_lock = threading.Lock()

#: §13 要求覆盖的指标。缺一个就说明这条链路出问题时查不到。
REQUIRED_METRICS = (
    "packageBytes",       # 三包体积（由 release finalize 写入 artifact，这里只登记快照）
    "firstReady",         # 首屏可用耗时分桶
    "cacheHit",           # 首页缓存命中
    "queryCount",         # 冷路径 SQL 条数分桶
    "unknownAction",      # 未登记/无法解析的 action —— 直接对应 P0-02
    "focusFail",          # 声明 LIST_FOCUS 却没定位到对象 —— 直接对应 P0-03
    "conflict409",        # 版本冲突
    "pageLatency",        # 页面级接口耗时分桶
    "fileScanBind",       # 附件扫描与绑定结果
    "wechatDelivery",     # 微信订阅授权与下发结果
    "scopeMode",          # 数据范围模式，用于判断是否压到了同一个 scope
)

_counters: dict[str, Counter[str]] = {name: Counter() for name in REQUIRED_METRICS}


def _bucket(value_ms: float) -> str:
    """耗时分桶：只保留量级，不保留精确值，避免成为侧信道。"""
    value = float(value_ms or 0)
    for edge in (100, 300, 500, 1000, 2000, 5000):
        if value < edge:
            return f"<{edge}ms"
    return ">=5000ms"


#: 外部标签只允许 ASCII 字母数字与少量分隔符。
#: 注意不能用 str.isalnum()——它对中文返回 True，姓名会被原样记进指标里。
_SAFE_LABEL_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-:"
)


def _label(value) -> str:
    """把任意外部入参压成短标识：ASCII 白名单，最长 64。"""
    text = "".join(ch for ch in str(value or "") if ch in _SAFE_LABEL_CHARS)
    return (text or "unknown")[:64]


def _record_bucket(metric: str, bucket: str, *, count: int = 1) -> None:
    """内部生成的分桶标签（如 ``<300ms`` / ``<=15``）不经外部白名单，
    否则 ``<`` ``=`` 会被剥掉，桶名互相塌缩成同一个键。"""
    if metric not in _counters:
        raise ValueError(f"未登记的可观测性指标：{metric}")
    with _lock:
        _counters[metric][bucket] += int(count)


def record(metric: str, label, *, count: int = 1) -> None:
    """登记一个**外部来源**的标签。一律过白名单。"""
    if metric not in _counters:
        raise ValueError(f"未登记的可观测性指标：{metric}")
    with _lock:
        _counters[metric][_label(label)] += int(count)


def record_latency(metric: str, duration_ms: float) -> None:
    _record_bucket(metric, _bucket(duration_ms))


def record_unknown_action(action_key: str | None, *, client: str) -> None:
    """未登记 action / 缺参 / 当前端无落点，都记在这里。"""
    record("unknownAction", f"{_label(client)}:{_label(action_key)}")


def record_focus_result(*, route_name: str | None, focused: bool) -> None:
    """LIST_FOCUS 目标最终有没有定位到对象。focused=False 就是 P0-03 复发。"""
    record("focusFail", f"{_label(route_name)}:{'ok' if focused else 'miss'}")


def record_home_read(*, cache_hit: bool, query_count: int, duration_ms: float) -> None:
    _record_bucket("cacheHit", "hit" if cache_hit else "miss")
    _record_bucket("queryCount", _query_bucket(query_count))
    record_latency("firstReady", duration_ms)


def _query_bucket(query_count: int) -> str:
    value = int(query_count or 0)
    if value == 0:
        return "0"
    for edge in (5, 10, 15, 20):
        if value <= edge:
            return f"<={edge}"
    return ">20"


def record_file_binding(*, purpose: str, outcome: str) -> None:
    record("fileScanBind", f"{_label(purpose)}:{_label(outcome)}")


def record_wechat_delivery(*, scene: str, outcome: str) -> None:
    record("wechatDelivery", f"{_label(scene)}:{_label(outcome)}")


def snapshot() -> dict:
    """健康探针/CI 读取用。只有匿名维度，可安全导出。"""
    with _lock:
        return {
            "schema": "miniapp-v3-observability/1",
            "metrics": {name: dict(counter) for name, counter in _counters.items()},
            "requiredMetrics": list(REQUIRED_METRICS),
        }


def reset_for_tests() -> None:
    with _lock:
        for counter in _counters.values():
            counter.clear()

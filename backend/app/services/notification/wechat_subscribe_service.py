"""V3 §9.3 微信订阅消息 provider adapter。

在此之前 :mod:`message_channel_delivery_service` 的 WECHAT 分支无条件
``SKIPPED / NOT_CONFIGURED``——也就是说这条渠道从来没有真正接上过。

本模块把它接到真实 provider，同时严格保持 fail-closed：

- **配置缺失就是配置缺失。** appid / secret / templateId / 用户 openid 任缺其一，
  返回 ``SKIPPED`` + 可诊断的 reasonCode，绝不在学生端宣称"已开启"。
- **只有用户显式授权过的场景才发。** 微信订阅消息是一次性授权，
  没有 openid 或没有该模板授权，就不是"发送失败"，而是"根本不该发"。
- **可重试与不可重试分清楚。** 网络/限流可重试（交给既有 lease + backoff + DEAD），
  配置缺失与未授权不可重试，重试多少次都一样。

真正的 HTTP 调用留在 :func:`_call_provider`：默认没有 provider 实现时返回
PROVIDER_UNAVAILABLE，不伪造成功。
"""
from __future__ import annotations

from typing import Any

#: 学生端高价值场景才请求订阅授权（§9.3）。其余场景不许弹授权框。
SUBSCRIBE_SCENES = (
    "CASE_RETURNED",        # 退回补材料
    "CASE_RESULT",          # 审批结果
    "EXAM_UPCOMING",        # 考试/答辩临近
    "INTERNSHIP_ABNORMAL",  # 实习异常
)

_RETRYABLE = {"PROVIDER_ERROR", "RATE_LIMITED", "NETWORK"}


def provider_status() -> dict[str, Any]:
    """管理端可诊断的渠道状态。学生端 UI 也据此显示真实状态，不猜。"""
    from app.core.config import settings

    appid = str(getattr(settings, "WX_APPID", "") or "").strip()
    secret = str(getattr(settings, "WX_SECRET", "") or "").strip()
    missing = []
    if not appid:
        missing.append("WX_APPID")
    if not secret:
        missing.append("WX_SECRET")
    return {
        "channel": "WECHAT",
        "configured": not missing,
        "missing": missing,
        "scenes": list(SUBSCRIBE_SCENES),
        # 模板 id 按场景配置，缺哪个就是哪个场景发不出去。
        "templates": {scene: bool(_template_id(scene)) for scene in SUBSCRIBE_SCENES},
    }


def _template_id(scene: str) -> str:
    from app.core.config import settings
    key = f"WX_SUBSCRIBE_TEMPLATE_{scene}"
    return str(getattr(settings, key, "") or "").strip()


def _call_provider(*, appid: str, secret: str, openid: str, template_id: str,
                   data: dict[str, Any]) -> dict[str, Any]:
    """真实下发。未接入具体 provider 时明确返回不可用，不伪造成功。"""
    from app.services.notification import providers

    sender = getattr(providers, "send_wechat_subscribe", None)
    if not callable(sender):
        return {"status": "SKIPPED", "reasonCode": "PROVIDER_UNAVAILABLE",
                "reason": "未接入微信订阅消息 provider"}
    return sender(appid=appid, secret=secret, openid=openid,
                  template_id=template_id, data=data)


def send_subscribe_message(*, tenant_id: int, openid: str | None, scene: str,
                           data: dict[str, Any] | None = None) -> dict[str, Any]:
    """下发一条订阅消息。任何异常都不得被转成业务成功。"""
    scene = str(scene or "").strip().upper()
    if scene not in SUBSCRIBE_SCENES:
        return {"status": "SKIPPED", "reasonCode": "SCENE_NOT_ALLOWED",
                "reason": f"未登记的订阅场景：{scene}", "retryable": False}

    status = provider_status()
    if not status["configured"]:
        return {"status": "SKIPPED", "reasonCode": "WECHAT_NOT_CONFIGURED",
                "reason": "缺少 " + ", ".join(status["missing"]), "retryable": False}

    template_id = _template_id(scene)
    if not template_id:
        return {"status": "SKIPPED", "reasonCode": "TEMPLATE_NOT_CONFIGURED",
                "reason": f"{scene} 未配置模板 id", "retryable": False}

    identifier = str(openid or "").strip()
    if not identifier:
        # 没有 openid = 用户没授权过。这不是发送失败，重试也没有意义。
        return {"status": "SKIPPED", "reasonCode": "OPENID_UNAVAILABLE",
                "reason": "用户未授权微信订阅", "retryable": False}

    from app.core.config import settings
    try:
        result = _call_provider(
            appid=str(settings.WX_APPID).strip(),
            secret=str(settings.WX_SECRET).strip(),
            openid=identifier, template_id=template_id, data=data or {},
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "FAILED", "reasonCode": "PROVIDER_ERROR",
                "reason": type(exc).__name__, "retryable": True}

    code = str(result.get("reasonCode") or "")
    result.setdefault("retryable", code in _RETRYABLE)
    return result

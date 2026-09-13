"""微信订阅消息适配边界。

发送实现和逐模板一次性授权记录尚未接通，当前明确返回不可用。
openid 只证明微信绑定；模板配置和绑定均不能替代用户订阅授权。
未来接入必须同时提供发送实现、授权校验与消费，不能仅设置配置开关。
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
    from app.services.notification import providers
    sender_ready = callable(getattr(providers, "send_wechat_subscribe", None))
    # 尚无逐模板一次性授权的权威记录/消费机制，不能把 openid 当授权。
    return {
        "providerReady": sender_ready,
        "authorizationReady": False,
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
        # openid 仅代表绑定身份，不代表订阅授权。
        return {"status": "SKIPPED", "reasonCode": "OPENID_UNAVAILABLE",
                "reason": "用户未授权微信订阅", "retryable": False}

    if not status.get("providerReady"):
        return {"status": "SKIPPED", "reasonCode": "PROVIDER_UNAVAILABLE",
                "reason": "微信提醒发送服务尚未接入", "retryable": False}
    if not status.get("authorizationReady"):
        return {"status": "SKIPPED", "reasonCode": "SUBSCRIPTION_AUTH_UNAVAILABLE",
                "reason": "尚无可核验的逐模板订阅授权", "retryable": False}

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

"""移动成绩身份旧兼容入口。

稳定课程身份候选与申请已合并到 ``mobile_academic_affairs_facade`` 单一公开入口；
本模块仅保留无副作用兼容导出，不再覆盖移动主 Service 或 gaps Service。
"""
from . import mobile_academic_affairs_facade as _service

_identity_options = _service._identity_options
makeup_options_my = _service.makeup_options_my
retake_apply_my = _service.retake_apply_my
exemption_apply_my = _service.exemption_apply_my
recognition_submit_my = _service.recognition_submit_my


def __getattr__(name):
    return getattr(_service, name)


__all__ = [
    "makeup_options_my",
    "retake_apply_my",
    "exemption_apply_my",
    "recognition_submit_my",
]

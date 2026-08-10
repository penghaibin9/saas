"""困难认定退回投影兼容壳。

退回状态的学生端展示合同已经正式落入 ``mobile_affairs_service.aid_my``：
核心状态 DRAFT 直接投影为“已退回待修改”，并返回 EDIT_RETURNED / RESUBMIT。

保留本模块仅用于兼容历史 import；不得再由 api router 在启动期安装或替换业务函数。
"""


def install() -> None:
    """Compatibility no-op: returned projection is now implemented by the authority service."""
    return None

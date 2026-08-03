"""兼容模块：活动再次确认已迁入 affairs_activity_service.confirm_activity。"""


def install() -> None:
    """保留旧导入路径；不再修改运行时函数。"""
    return None

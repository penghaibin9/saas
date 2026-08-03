"""兼容模块：教师学工工作台已迁入显式 service，不再在启动期替换函数。"""
from app.services.affairs_teacher_workbench_service import teacher_affairs as _workbench


def install() -> None:
    """兼容旧导入；故意不做 monkey-patch。"""
    return None

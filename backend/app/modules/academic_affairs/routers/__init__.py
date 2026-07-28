"""教务中心 Router 包。

新增教务 Router 在模块内部聚合，由主线既有的单一 ``academic_affairs.router``
注册入口统一挂载。这里不删除、重排或运行时替换 APIRoute，也不要求修改
``app.api.v1.route_registration``。
"""

from . import academic_affairs_bundle as academic_affairs

__all__ = ["academic_affairs"]

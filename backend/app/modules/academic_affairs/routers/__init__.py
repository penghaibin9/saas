"""教务中心 Router 包。

新增教务 Router 由 ``academic_affairs_bundle`` 显式聚合，并由主路由注册文件直接导入。
包初始化不得提前加载聚合器，否则独立 Router 在循环导入中可能尚未完成路由装配。
"""

__all__ = ["academic_affairs", "academic_affairs_bundle"]

"""教务中心 Router 包。

本包不在导入阶段删除、追加或重排 APIRoute。所有 Router 必须在
``app.api.v1.route_registration`` 中显式注册，重复路径必须在原 Router 中完成迁移，
不得依赖首条路由抢占或运行时替换。
"""

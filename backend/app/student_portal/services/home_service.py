"""学生 PC 门户 · 首页工作台聚合。

V3 施工手册 SP-H01：以前这里直接把 ``mobile_student_service.me_overview()`` 的原始
结果转发给前端，Student Mini 已经升级到 typed HomeProjection（asOf/projectionVersion/
分区状态/typed action），PC 端却一直停在旧结构——同一学生在两端看到不同的待办动作、
生命周期解释和 freshness 语义。真正的聚合与分区异常边界现在都在
:mod:`app.student_portal.services.home_projection_service`，本文件只是路由到它的
薄入口，避免 router 直接依赖投影内部实现。
"""
from __future__ import annotations

from app.student_portal.services import home_projection_service


def overview(user: dict) -> dict:
    """PC 首页聚合：HomeProjection v2（真实 typed action + 分区 DATA/EMPTY/ERROR）。"""
    return home_projection_service.build_home_v2(user)

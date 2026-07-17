"""学生 PC 门户 · 办事大厅（第5期收口）。

一站式汇总本租户「已开通模块」的可办事项清单。复用 student_portal_service.get_config 的真实
按租户 modules 授权（非 mock），只输出 enabled=true 的入口，供前端做办事大厅检索/宫格。
"""
from __future__ import annotations

from app.services import student_portal_service as portal_cfg
from app.services.db_service import _tid
from app.services.mobile_student_service import _require_student

# 模块 key（与 portal-config.modules 对齐）→ 展示名 + 门户前端路由
_CATALOG = [
    ("dashboard", "首页工作台", "home"),
    ("profile", "我的档案", "profile"),
    ("orientation", "迎新报到", "orientation"),
    ("campusService", "在校服务", "campus-service"),
    ("academic", "教务学业", "academic"),
    ("graduation", "毕业设计", "graduation"),
    ("internship", "岗位实习", "internship"),
    ("employment", "就业服务", "employment"),
    ("messages", "消息通知", "messages"),
]


def catalog(user: dict) -> dict:
    """办事大厅目录（本人所在租户已开通模块）。"""
    _require_student(user)
    cfg = portal_cfg.get_config(_tid())
    modules = cfg.get("modules") or {}
    items = [{"key": k, "label": lbl, "path": path}
             for (k, lbl, path) in _CATALOG if bool(modules.get(k, False))]
    return {"items": items, "total": len(items)}

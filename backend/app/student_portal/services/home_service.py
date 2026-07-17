"""学生 PC 门户 · 首页工作台聚合。

复用 mobile_student_service.me_overview 的真实聚合（学生/阶段/待办/预警/通知/未读数/各域状态），
再叠加「快捷入口」——按本租户 portal-config 已开通模块过滤（真实配置，非 mock）。GET 本人。
"""
from __future__ import annotations

from app.services import mobile_student_service as stu
from app.services import student_portal_service as portal_cfg
from app.services.db_service import _tid

# 快捷入口目录：key（与 portal-config.modules 对齐）→ 展示名 + 门户前端路由 path
_QUICK_CATALOG = [
    ("profile", "我的档案", "profile"),
    ("academic", "教务学业", "academic"),
    ("graduation", "毕业设计", "graduation"),
    ("internship", "岗位实习", "internship"),
    ("employment", "就业服务", "employment"),
    ("orientation", "迎新报到", "orientation"),
    ("campusService", "在校服务", "campus-service"),
    ("messages", "消息通知", "messages"),
]


def _quick_entries() -> list:
    cfg = portal_cfg.get_config(_tid())
    modules = cfg.get("modules") or {}
    return [{"key": k, "label": lbl, "path": path}
            for (k, lbl, path) in _QUICK_CATALOG if modules.get(k, False)]


def overview(user: dict) -> dict:
    """PC 首页聚合：me_overview 真实数据 + 本租户已开通模块的快捷入口。"""
    base = stu.me_overview(user)  # 内部 _require_student，非学生抛 NO_PERMISSION
    base = dict(base) if isinstance(base, dict) else {"data": base}
    base["quickEntries"] = _quick_entries()
    return base

"""学生 PC 门户 · 首页工作台聚合。

复用 mobile_student_service.me_overview 的真实聚合（学生/阶段/待办/预警/通知/未读数/各域状态），
再叠加「快捷入口」——按本租户 portal-config 已开通模块过滤（真实配置，非 mock）。GET 本人。

V2 R6：首页待办必须给出可执行的独立页面路径，不能只把学生扔回“大模块首页”。
"""
from __future__ import annotations

from sqlalchemy import select

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

# source_biz_type / todo_type 关键词 → 学生 PC 独立任务页。
# 顺序由具体到通用；全部是本人门户路由，不允许生成 /admin/*。
_ACADEMIC_TASK_ROUTES = [
    (("GRADE_RECHECK", "RECHECK"), "/academic/recheck"),
    (("EVALUATION", "TEACHING_EVALUATION"), "/academic/evaluation"),
    (("REGISTRATION",), "/academic/registration"),
    (("SELECTION", "COURSE_SELECT"), "/academic/selection"),
    (("STATUS_CHANGE", "TRANSFER_MAJOR", "TRANSFER_CLASS", "SUSPEND", "RESUME"), "/academic/status"),
    (("DEFER", "EXAM"), "/academic/exam"),
    (("RETAKE", "MAKEUP", "EXEMPT"), "/academic/makeup"),
    (("WARNING",), "/academic/warning"),
    (("TEXTBOOK",), "/academic/textbook"),
    (("LEVEL_EXAM",), "/academic/level-exam"),
    (("MAJOR_SPLIT",), "/academic/major-split"),
    (("RECOGNITION",), "/academic/recognition"),
    (("GRADUATION_AUDIT", "GRADUATION_PRECHECK"), "/academic/graduation"),
]

_MODULE_DEFAULT_ROUTES = {
    "academic-affairs": "/academic",
    "academic": "/academic",
    "graduation": "/graduation",
    "internship": "/internship",
    "employment": "/employment",
    "orientation": "/orientation",
    "student-affairs": "/campus-service",
    "campus-service": "/campus-service",
    "messages": "/messages",
}


def _quick_entries() -> list:
    cfg = portal_cfg.get_config(_tid())
    modules = cfg.get("modules") or {}
    return [{"key": k, "label": lbl, "path": path}
            for (k, lbl, path) in _QUICK_CATALOG if modules.get(k, False)]


def _todo_route(*, source_module="", source_biz_type="", todo_type="", source_biz_id=None) -> str:
    """把统一待办解析为学生 PC 可执行路由；未知类型安全退回模块首页。"""
    module = str(source_module or "").strip().lower()
    signature = f"{source_biz_type or ''} {todo_type or ''}".upper()
    if module in {"academic-affairs", "academic"} or "ACADEMIC" in signature or signature.startswith("AA_"):
        for keywords, route in _ACADEMIC_TASK_ROUTES:
            if any(keyword in signature for keyword in keywords):
                return route
        return "/academic"
    return _MODULE_DEFAULT_ROUTES.get(module, "/home")


def _enrich_todo_routes(user: dict, todo_items: list[dict]) -> list[dict]:
    """按待办主键回读来源字段并补 route/sourceBizId；失败时保持原待办且安全退回模块页。"""
    items = [dict(item or {}) for item in (todo_items or [])]
    ids = [int(item["id"]) for item in items if str(item.get("id") or "").isdigit()]
    rows_by_id = {}
    if ids:
        from app.models import UnifiedTodo
        with stu._session() as db:
            rows = db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.id.in_(ids),
                UnifiedTodo.is_deleted.is_(False),
            )).all()
            rows_by_id = {str(row.id): row for row in rows}
    for item in items:
        row = rows_by_id.get(str(item.get("id") or ""))
        source_module = getattr(row, "source_module", None) if row else item.get("module")
        source_biz_type = getattr(row, "source_biz_type", None) if row else ""
        source_biz_id = getattr(row, "source_biz_id", None) if row else None
        todo_type = getattr(row, "todo_type", None) if row else item.get("type")
        item["module"] = source_module or item.get("module") or ""
        item["sourceBizType"] = source_biz_type or ""
        item["sourceBizId"] = str(source_biz_id) if source_biz_id not in (None, "") else ""
        item["route"] = _todo_route(
            source_module=source_module,
            source_biz_type=source_biz_type,
            todo_type=todo_type,
            source_biz_id=source_biz_id,
        )
    return items


def overview(user: dict) -> dict:
    """PC 首页聚合：me_overview 真实数据 + 本租户已开通模块的快捷入口。"""
    base = stu.me_overview(user)  # 内部 _require_student，非学生抛 NO_PERMISSION
    base = dict(base) if isinstance(base, dict) else {"data": base}
    base["todos"] = _enrich_todo_routes(user, base.get("todos") or [])
    base["quickEntries"] = _quick_entries()
    return base

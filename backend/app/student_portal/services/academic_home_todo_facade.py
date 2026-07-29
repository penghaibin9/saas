"""学生 PC 首页教务待办路由扩展。

latest main 的首页聚合保持原样；本门面只把统一待办补成学生本人可执行的教务路由，
并显式委托非教务模块到其既有首页，避免把教务增量写回共享 home_service。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services import mobile_student_service as stu
from app.services.db_service import _tid

from . import home_service as _base


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


def __getattr__(name):
    return getattr(_base, name)


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


def _enrich_todo_routes(todo_items: list[dict]) -> list[dict]:
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
        source_biz_type = getattr(row, "source_biz_type", None) if row else item.get("sourceBizType")
        source_biz_id = getattr(row, "source_biz_id", None) if row else item.get("sourceBizId")
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
    base = _base.overview(user)
    result = dict(base) if isinstance(base, dict) else {"data": base}
    result["todos"] = _enrich_todo_routes(result.get("todos") or [])
    return result

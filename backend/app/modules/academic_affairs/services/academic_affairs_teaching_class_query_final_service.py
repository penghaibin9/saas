"""V2-02 教学班详情最终读侧：补名单管理模式结论。"""
from __future__ import annotations

from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_query_service as _base
from .academic_affairs_teaching_class_change_service import _manual_mode


def __getattr__(name):
    return getattr(_base, name)


def list_teaching_classes(*args, **kwargs):
    return _base.list_teaching_classes(*args, **kwargs)


def get_teaching_class(user, teaching_class_id: int) -> dict:
    result = _base.get_teaching_class(user, teaching_class_id)
    from app.models import AaSelectionCourse

    with session() as db:
        selection_exists = db.query(AaSelectionCourse.id).filter(
            AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.teaching_task_id == int(result["teachingTaskId"]),
            AaSelectionCourse.is_deleted.is_(False),
        ).first() is not None
    current_source = ""
    current_id = str(result.get("currentRosterVersionId") or "")
    for version in result.get("rosterVersions") or []:
        if str(version.get("rosterVersionId") or "") == current_id:
            current_source = str(version.get("sourceType") or "")
            break
    result["rosterManagement"] = _manual_mode(
        selection_exists,
        result.get("classType") or "",
        current_source,
    )
    return result

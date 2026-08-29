"""独立教学班名单版本历史兼容入口。

正式名单版本统一由 ``academic_affairs_teaching_class_service`` 持有；
锁定选课允许 0 人正式版本的特殊语义统一由
``academic_affairs_selection_roster_projection_service`` 持有。
本模块只保留旧 import 路径，不再维护第二套名单写事务。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_selection_roster_projection_service as _selection_projection
from . import academic_affairs_teaching_class_service as _canonical


def __getattr__(name):
    """其余历史 helper 透明转给唯一正式 TeachingClass Service。"""
    return getattr(_canonical, name)


def create_roster_version(
    db,
    teaching_class,
    student_ids,
    *,
    source_type: str,
    source_id=None,
    member_source_ids=None,
    reason="",
):
    """兼容旧调用；有效业务规则委托给当前正式 owner。"""
    ids, _profiles = _canonical._member_profiles(db, student_ids)
    source = str(source_type or "").strip().upper()

    if not ids:
        if source != "SELECTION_LOCK":
            raise AppException("DATA_CONFLICT", "非选课教学班的正式名单不能为空", http_status=409)
        if source_id in (None, ""):
            raise AppException(
                "DATA_CONFLICT",
                "选课空名单版本必须绑定真实选课批次",
                http_status=409,
            )
        return _selection_projection._create_empty_selection_version(
            db,
            teaching_class,
            batch_id=int(source_id),
            reason=reason,
        )

    return _canonical.create_roster_version(
        db,
        teaching_class,
        ids,
        source_type=source,
        source_id=source_id,
        member_source_ids=member_source_ids,
        reason=reason,
    )


# 历史按值导入继续可用，但函数对象直接来自当前选课名单投影 owner。
project_selection_course_locked = _selection_projection.project_selection_course_locked
project_selection_batch_locked = _selection_projection.project_selection_batch_locked

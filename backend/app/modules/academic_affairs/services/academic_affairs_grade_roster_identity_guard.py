"""R9 成绩发布名单版本守卫。

成绩提交时已经冻结名单版本；教务终审发布前再次确认该版本仍是教学班当前版本。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_identity_facade as _base
from .academic_affairs_roster_consumer_service import require_consumer_snapshot_current

_original_publish = _base.publish_grades


def publish_grades(task_id, user) -> dict:
    from app.models import AaGradeTask

    with _base._legacy.session() as db:
        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(task_id),
            AaGradeTask.tenant_id == _base._legacy._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).first()
        if not task:
            raise not_found("成绩录入任务不存在")
        if not task.teaching_task_id:
            raise AppException("DATA_CONFLICT", "普通成绩发布必须关联教学任务")
        snapshot, _current = require_consumer_snapshot_current(
            db, "GRADE_TASK", int(task.id), int(task.teaching_task_id),
        )
    result = _original_publish(task_id, user)
    return {**result, "rosterIdentity": snapshot}


# 包级服务和底层历史导入都命中同一守卫。
_base.publish_grades = publish_grades
_base._legacy.publish_grades = publish_grades

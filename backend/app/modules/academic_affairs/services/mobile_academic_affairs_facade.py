"""移动教务兼容入口。

收口仍使用姓名匹配的教师课表和考勤班级选项；其余移动教务能力委托既有服务。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import no_permission
from app.services.db_service import _tid

from . import mobile_academic_affairs_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def stable_teacher_keys(user) -> set[str]:
    """只返回工号族标识，不包含realName。"""
    return set(_derive_keys(user or {}))


def stable_teacher_key(user) -> str:
    user = user or {}
    login = str(user.get("loginName") or "").strip()
    if login:
        return login
    context_id = str(user.get("activeContextId") or "").strip()
    if context_id.startswith("ctx_") and len(context_id) > 4:
        return context_id[4:]
    uid = str(user.get("userId") or "").strip()
    if uid.startswith("u_") and len(uid) > 2:
        return uid[2:]
    return uid


def teacher_schedule_my(user) -> dict:
    """教师课表只用稳定工号查询；缺工号时fail-closed。"""
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as schedule

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    teacher_key = stable_teacher_key(user)
    if not teacher_key:
        raise no_permission("当前教师账号缺少稳定工号，请联系管理员")
    with _legacy.session() as db:
        batch = _legacy._latest_published_batch(db)
    if not batch:
        return {"batchId": "", "items": [], "note": "暂无已发布课表"}
    data = schedule.teacher_view(batch.id, user, teacher_key)
    return {"batchId": str(batch.id), **data}


def teacher_attendance_class_options(user) -> dict:
    """只返回当前教师真实教学任务班级；姓名和辅导员班级不作为课堂点名授权。"""
    from app.models import AaTeachingTask, SchoolClass

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    role = str((user or {}).get("currentRoleCode") or "").upper()
    keys = stable_teacher_keys(user)
    if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"} and not keys:
        return {"items": [], "hasData": False, "note": "当前账号缺少稳定教师工号"}

    with _legacy.session() as db:
        conditions = [
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status != "MERGED",
            AaTeachingTask.class_id.is_not(None),
        ]
        if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
            conditions.append(AaTeachingTask.teacher_key.in_(sorted(keys)))
        tasks = db.scalars(select(AaTeachingTask).where(*conditions)).all()

        by_id = {}
        for task in tasks:
            school_class = db.get(SchoolClass, int(task.class_id))
            if not school_class or school_class.is_deleted or school_class.tenant_id != _tid():
                continue
            by_id[school_class.id] = {
                "classId": str(school_class.id),
                "className": school_class.class_name,
                "grade": school_class.grade or "",
                "source": "TEACHING_TASK",
            }
        items = sorted(by_id.values(), key=lambda item: int(item["classId"]))
        return {"items": items, "hasData": bool(items)}

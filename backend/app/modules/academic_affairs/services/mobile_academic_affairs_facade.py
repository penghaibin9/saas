"""移动教务兼容入口。

收口仍使用姓名匹配的教师课表，并把课堂考勤入口从“可手填课程的行政班”升级为
“当前学期本人真实教学任务”；其余移动教务能力委托既有服务。
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
    """返回当前学期本人真实教学任务，供点名场次精确选择课程+班级。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, SchoolClass

    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    role = str((user or {}).get("currentRoleCode") or "").upper()
    keys = stable_teacher_keys(user)
    if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"} and not keys:
        return {"items": [], "hasData": False, "note": "当前账号缺少稳定教师工号"}

    with _legacy.session() as db:
        current_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).first()
        if not current_term:
            return {"items": [], "hasData": False, "note": "当前学校尚未设置当前学期"}

        conditions = [
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status.notin_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER", "MERGED"]),
            AaTeachingTask.class_id.is_not(None),
        ]
        if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
            conditions.append(AaTeachingTask.teacher_key.in_(sorted(keys)))
        tasks = db.scalars(select(AaTeachingTask).where(*conditions)).all()

        items = []
        for task in tasks:
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != _tid():
                continue
            if int(batch.term_id or 0) != int(current_term.id):
                continue
            school_class = db.get(SchoolClass, int(task.class_id))
            if not school_class or school_class.is_deleted or school_class.tenant_id != _tid():
                continue
            items.append({
                "teachingTaskId": str(task.id),
                "classId": str(school_class.id),
                "className": school_class.class_name,
                "grade": school_class.grade or "",
                "courseName": task.course_name or "",
                "teacherKey": task.teacher_key or "",
                "termId": str(current_term.id),
                "termCode": f"{current_term.year_code}-{current_term.term_no}",
                "taskStatus": task.status,
                "source": "TEACHING_TASK",
            })
        items.sort(key=lambda item: (
            item["courseName"], item["className"], int(item["teachingTaskId"])
        ))
        return {
            "items": items,
            "hasData": bool(items),
            "termId": str(current_term.id),
            "termCode": f"{current_term.year_code}-{current_term.term_no}",
            "note": "仅展示当前学期本人真实教学任务",
        }

"""V2-02 名单变更最终数据范围层。"""
from __future__ import annotations

from app.core.affairs_security import no_data_scope
from app.services.db_service import _tid

from . import academic_affairs_teaching_class_change_service as _base
from . import academic_affairs_teaching_class_lock_service as _teaching_class
from .academic_affairs_task_security_facade import _scope


def __getattr__(name):
    return getattr(_base, name)


def _validate_student_scope(db, user, student_ids) -> None:
    from app.models import Major, SchoolClass

    ids, profiles = _teaching_class._member_profiles(db, student_ids)
    scope = _scope(user, db)
    if scope.all:
        return

    class_ids = sorted({int(profiles[value].class_id) for value in ids if profiles[value].class_id})
    classes = db.query(SchoolClass).filter(
        SchoolClass.tenant_id == _tid(),
        SchoolClass.id.in_(class_ids or [0]),
        SchoolClass.is_deleted.is_(False),
    ).all()
    major_ids = sorted({int(row.major_id) for row in classes if row.major_id})
    majors = db.query(Major).filter(
        Major.tenant_id == _tid(),
        Major.id.in_(major_ids or [0]),
        Major.is_deleted.is_(False),
    ).all()
    college_by_major = {int(row.id): int(row.college_id) for row in majors if row.college_id}
    class_college = {int(row.id): college_by_major.get(int(row.major_id)) for row in classes if row.major_id}

    invalid = []
    for student_id in ids:
        class_id = int(profiles[student_id].class_id) if profiles[student_id].class_id else None
        in_class = bool(class_id and scope.class_ids and class_id in scope.class_ids)
        in_college = bool(
            class_id
            and scope.college_ids
            and class_college.get(class_id) in scope.college_ids
        )
        if not in_class and not in_college:
            invalid.append(student_id)
    if invalid:
        raise no_data_scope(f"拟加入名单中有 {len(invalid)} 名学生不在当前学院或班级数据范围")


# 基础服务公开函数在运行时读取本全局函数；替换后预览和正式创建使用同一范围口径。
_base._validate_student_scope = _validate_student_scope


def preview_roster_change(user, teaching_class_id: int, student_ids) -> dict:
    return _base.preview_roster_change(user, teaching_class_id, student_ids)


def create_manual_roster_version(user, teaching_class_id: int, student_ids, reason: str) -> dict:
    return _base.create_manual_roster_version(user, teaching_class_id, student_ids, reason)

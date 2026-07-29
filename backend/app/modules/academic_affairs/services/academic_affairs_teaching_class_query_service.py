"""独立教学班查询与数据范围 Service。"""
from __future__ import annotations

import json

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.permissions import is_super_admin
from app.services.db_service import _iso, _tid, session

from . import academic_affairs_teaching_class_service as teaching_class_service

_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}


def _user_keys(user) -> set[str]:
    return {str(value) for value in (_derive_keys(user) or set()) if str(value).strip()}


def _accessible_rows(db, user, rows):
    from app.models import AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch

    role = str((user or {}).get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
        return list(rows)
    if role not in _ADMIN_ROLES:
        keys = _user_keys(user)
        if not keys:
            raise no_data_scope("当前教师账号没有稳定工号，无法确认授课教学班")
        class_ids = {
            int(value) for (value,) in db.query(AaTeachingClassTeacher.teaching_class_id).filter(
                AaTeachingClassTeacher.tenant_id == _tid(),
                AaTeachingClassTeacher.teacher_key.in_(sorted(keys)),
                AaTeachingClassTeacher.status == "ACTIVE",
                AaTeachingClassTeacher.is_deleted.is_(False),
            ).all()
        }
        return [row for row in rows if int(row.id) in class_ids]

    context = build_affairs_context(user, db)
    if str(context.scope_type or "").upper() == "TENANT_ALL":
        return list(rows)
    class_ids = {int(value) for value in (context.allowed_class_ids(db) or set())}
    college_ids = {int(value) for value in (context.college_ids or set())}
    if not class_ids and not college_ids:
        raise no_data_scope("当前身份未配置教学班学院或班级范围")

    task_ids = [int(row.teaching_task_id) for row in rows]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.id.in_(task_ids or [0]),
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    task_by_id = {int(row.id): row for row in tasks}
    batch_ids = sorted({int(row.batch_id) for row in tasks})
    batches = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.id.in_(batch_ids or [0]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).all()
    batch_by_id = {int(row.id): row for row in batches}
    allowed = []
    for row in rows:
        task = task_by_id.get(int(row.teaching_task_id))
        if not task:
            continue
        if class_ids and task.class_id and int(task.class_id) in class_ids:
            allowed.append(row)
            continue
        batch = batch_by_id.get(int(task.batch_id))
        if college_ids and batch and batch.college_id and int(batch.college_id) in college_ids:
            allowed.append(row)
    return allowed


def _teacher_dto(row):
    return {
        "teacherRelationId": str(row.id),
        "teacherId": str(row.teacher_id or ""),
        "teacherKey": row.teacher_key,
        "teacherName": row.teacher_name or "",
        "roleType": row.role_type,
        "startWeek": row.start_week,
        "endWeek": row.end_week,
        "status": row.status,
    }


def _class_dto(row, task=None, teachers=None):
    return {
        "teachingClassId": str(row.id),
        "teachingTaskId": str(row.teaching_task_id),
        "termId": str(row.term_id),
        "courseId": str(row.course_id),
        "classCode": row.class_code,
        "className": row.class_name,
        "classType": row.class_type,
        "capacity": row.capacity,
        "rosterStatus": row.roster_status,
        "rosterVersionNo": row.current_roster_version_no,
        "currentRosterVersionId": str(row.current_roster_version_id or ""),
        "status": row.status,
        "courseCode": task.course_code if task else "",
        "courseName": task.course_name if task else "",
        "administrativeClassId": str(task.class_id or "") if task else "",
        "administrativeClassName": str(getattr(task, "class_name", None) or "") if task else "",
        "taskStatus": task.status if task else "",
        "expectedStudents": task.expected_students if task else None,
        "teachers": [_teacher_dto(item) for item in (teachers or [])],
    }


def _manual_mode(selection_exists: bool, class_type: str, current_source: str) -> dict:
    managed_by_selection = (
        bool(selection_exists)
        or str(class_type or "").upper() == "SELECTION"
        or str(current_source or "").upper() == "SELECTION_LOCK"
    )
    return {
        "managedBySelection": managed_by_selection,
        "canManualChange": not managed_by_selection,
        "reason": (
            "该教学班名单由选课结果管理，请在选课管理中补退选并重新锁定名单"
            if managed_by_selection else ""
        ),
    }


def list_teaching_classes(user, term_id=None, status=None, class_type=None, keyword=None,
                          page=1, page_size=30):
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask

    with session() as db:
        query = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.is_deleted.is_(False),
        )
        if term_id:
            query = query.filter(AaTeachingClass.term_id == int(term_id))
        if status:
            query = query.filter(AaTeachingClass.status == status)
        if class_type:
            query = query.filter(AaTeachingClass.class_type == class_type)
        rows = query.order_by(AaTeachingClass.term_id.desc(), AaTeachingClass.id.desc()).all()
        rows = _accessible_rows(db, user, rows)
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.id.in_([int(row.teaching_task_id) for row in rows] or [0]),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        task_by_id = {int(row.id): row for row in tasks}
        if keyword:
            key = str(keyword).strip().lower()
            rows = [
                row for row in rows
                if key in (row.class_code or "").lower()
                or key in (row.class_name or "").lower()
                or key in (
                    (task_by_id.get(int(row.teaching_task_id)).course_name
                     if task_by_id.get(int(row.teaching_task_id)) else "") or ""
                ).lower()
            ]
        teacher_rows = db.query(AaTeachingClassTeacher).filter(
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id.in_([int(row.id) for row in rows] or [0]),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
        ).all()
        teachers_by_class = {}
        for teacher in teacher_rows:
            teachers_by_class.setdefault(int(teacher.teaching_class_id), []).append(teacher)
        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        selected = rows[start:start + int(page_size)]
        return [
            _class_dto(
                row,
                task_by_id.get(int(row.teaching_task_id)),
                teachers_by_class.get(int(row.id), []),
            ) for row in selected
        ], total


def get_teaching_class(user, teaching_class_id: int) -> dict:
    from app.models import (
        AaSelectionCourse, AaTeachingClass, AaTeachingClassMember,
        AaTeachingClassRosterVersion, AaTeachingClassTeacher,
        AaTeachingTask, StudentProfile,
    )

    with session() as db:
        row = db.query(AaTeachingClass).filter(
            AaTeachingClass.id == int(teaching_class_id),
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.is_deleted.is_(False),
        ).first()
        if not row or not _accessible_rows(db, user, [row]):
            raise no_data_scope("教学班不存在或不在当前数据范围")
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == row.teaching_task_id,
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        teachers = db.query(AaTeachingClassTeacher).filter(
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id == row.id,
            AaTeachingClassTeacher.is_deleted.is_(False),
        ).order_by(AaTeachingClassTeacher.id).all()
        versions = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.tenant_id == _tid(),
            AaTeachingClassRosterVersion.teaching_class_id == row.id,
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).order_by(AaTeachingClassRosterVersion.version_no.desc()).all()
        current_members = []
        if row.current_roster_version_id:
            members = db.query(AaTeachingClassMember).filter(
                AaTeachingClassMember.tenant_id == _tid(),
                AaTeachingClassMember.roster_version_id == row.current_roster_version_id,
                AaTeachingClassMember.status == "ACTIVE",
                AaTeachingClassMember.is_deleted.is_(False),
            ).all()
            profile_ids = [int(item.student_id) for item in members]
            profiles = db.query(StudentProfile).filter(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(profile_ids or [0]),
                StudentProfile.is_deleted.is_(False),
            ).all()
            profile_by_id = {int(item.id): item for item in profiles}
            for member in members:
                profile = profile_by_id.get(int(member.student_id))
                current_members.append({
                    "memberId": str(member.id),
                    "studentId": str(member.student_id),
                    "studentNo": profile.student_no if profile else "",
                    "realName": profile.real_name if profile else "学生主档缺失",
                    "classId": str(profile.class_id or "") if profile else "",
                    "sourceType": member.source_type,
                    "sourceId": str(member.source_id or ""),
                    "status": member.status,
                })
        result = _class_dto(row, task, teachers)
        result["currentMembers"] = current_members
        result["rosterVersions"] = [{
            "rosterVersionId": str(version.id),
            "versionNo": version.version_no,
            "sourceType": version.source_type,
            "sourceId": str(version.source_id or ""),
            "memberCount": version.member_count,
            "rosterHash": version.roster_hash,
            "status": version.status,
            "reason": version.reason or "",
            "lockedAt": _iso(version.locked_at),
            "lockedBy": version.locked_by or "",
        } for version in versions]
        try:
            result["sourceSnapshot"] = json.loads(row.source_snapshot_json or "{}")
        except (TypeError, ValueError):
            result["sourceSnapshot"] = {}
        selection_exists = db.query(AaSelectionCourse.id).filter(
            AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.teaching_task_id == int(row.teaching_task_id),
            AaSelectionCourse.is_deleted.is_(False),
        ).first() is not None
        current_source = ""
        current_id = str(result.get("currentRosterVersionId") or "")
        for version in result["rosterVersions"]:
            if str(version.get("rosterVersionId") or "") == current_id:
                current_source = str(version.get("sourceType") or "")
                break
        result["rosterManagement"] = _manual_mode(selection_exists, row.class_type, current_source)
        return result


def backfill_teaching_classes(user, term_id: int, dry_run=True, reason=""):
    return teaching_class_service.backfill_term(
        user, int(term_id), dry_run=bool(dry_run), reason=reason,
    )

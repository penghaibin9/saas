"""非选课教学班名单变更与影响预览。

- 选课管理的教学班禁止人工覆盖；
- 非选课教学班可创建 MANUAL 新版本；
- 先展示课表、考勤、考务、成绩影响；
- 考勤、考务或成绩已消费名单时阻断直接变更。
"""
from __future__ import annotations

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_query_service as query_service
from . import academic_affairs_teaching_class_service as teaching_class_service


def _change_sets(current_ids, proposed_ids) -> dict:
    current = {int(value) for value in current_ids}
    proposed = {int(value) for value in proposed_ids}
    return {
        "currentIds": sorted(current),
        "proposedIds": sorted(proposed),
        "addedIds": sorted(proposed - current),
        "removedIds": sorted(current - proposed),
        "unchangedIds": sorted(current & proposed),
        "changed": current != proposed,
    }


def _impact_summary(schedule_count: int, attendance_count: int, exam_count: int, grade_count: int) -> dict:
    blocking = int(attendance_count or 0) + int(exam_count or 0) + int(grade_count or 0)
    return {
        "scheduleCount": int(schedule_count or 0),
        "attendanceCount": int(attendance_count or 0),
        "examCourseCount": int(exam_count or 0),
        "gradeTaskCount": int(grade_count or 0),
        "blockingConsumerCount": blocking,
        "blocked": blocking > 0,
        "blockerMessage": (
            "名单已被考勤、考务或成绩任务消费，本阶段禁止直接创建新版本；请先完成下游名单迁移。"
            if blocking > 0 else ""
        ),
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


def _get_class(db, user, teaching_class_id: int, *, lock=False):
    from app.models import AaTeachingClass

    query = db.query(AaTeachingClass).filter(
        AaTeachingClass.id == int(teaching_class_id),
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise not_found("教学班不存在")
    if not query_service._accessible_rows(db, user, [row]):
        raise no_data_scope("该教学班不在当前数据范围")
    if row.status != "ACTIVE":
        raise AppException("DATA_CONFLICT", "仅使用中的教学班可调整名单", http_status=409)
    return row


def _current_version(db, teaching_class):
    from app.models import AaTeachingClassRosterVersion

    if not teaching_class.current_roster_version_id:
        return None
    return db.query(AaTeachingClassRosterVersion).filter(
        AaTeachingClassRosterVersion.id == teaching_class.current_roster_version_id,
        AaTeachingClassRosterVersion.tenant_id == _tid(),
        AaTeachingClassRosterVersion.is_deleted.is_(False),
    ).first()


def _current_member_ids(db, teaching_class) -> list[int]:
    from app.models import AaTeachingClassMember

    if not teaching_class.current_roster_version_id:
        return []
    return [
        int(value) for (value,) in db.query(AaTeachingClassMember.student_id).filter(
            AaTeachingClassMember.tenant_id == _tid(),
            AaTeachingClassMember.roster_version_id == teaching_class.current_roster_version_id,
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        ).all()
    ]


def _selection_exists(db, teaching_class) -> bool:
    from app.models import AaSelectionCourse

    return db.query(AaSelectionCourse.id).filter(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.teaching_task_id == teaching_class.teaching_task_id,
        AaSelectionCourse.is_deleted.is_(False),
    ).first() is not None


def _validate_student_scope(db, user, student_ids) -> None:
    from app.models import Major, SchoolClass

    ids, profiles = teaching_class_service._member_profiles(db, student_ids)
    context = build_affairs_context(user, db)
    if str(context.scope_type or "").upper() == "TENANT_ALL":
        return
    allowed_class_ids = {int(value) for value in (context.allowed_class_ids(db) or set())}
    allowed_college_ids = {int(value) for value in (context.college_ids or set())}
    if not allowed_class_ids and not allowed_college_ids:
        raise no_data_scope("当前身份未配置可管理的学院或班级范围")

    class_ids = sorted({
        int(profiles[value].class_id) for value in ids if profiles[value].class_id
    })
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
    class_college = {
        int(row.id): college_by_major.get(int(row.major_id))
        for row in classes if row.major_id
    }

    invalid = []
    for student_id in ids:
        class_id = int(profiles[student_id].class_id) if profiles[student_id].class_id else None
        in_class = bool(class_id and class_id in allowed_class_ids)
        in_college = bool(
            class_id and class_college.get(class_id) in allowed_college_ids
        )
        if not in_class and not in_college:
            invalid.append(student_id)
    if invalid:
        raise no_data_scope(f"拟加入名单中有 {len(invalid)} 名学生不在当前学院或班级数据范围")


def _downstream_impact(db, teaching_class) -> dict:
    from app.models import (
        AaAttendanceSession, AaExamCourse, AaGradeTask, AaScheduleItem,
        AaTeachingTask, AaTerm,
    )

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == teaching_class.teaching_task_id,
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    schedule_count = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.task_id == teaching_class.teaching_task_id,
        AaScheduleItem.is_deleted.is_(False),
    ).count()
    exam_count = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.teaching_task_id == teaching_class.teaching_task_id,
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).count()
    grade_count = db.query(AaGradeTask).filter(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.teaching_task_id == teaching_class.teaching_task_id,
        AaGradeTask.is_deleted.is_(False),
    ).count()

    attendance_count = 0
    if task:
        term = db.query(AaTerm).filter(
            AaTerm.id == teaching_class.term_id,
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
        term_code = f"{term.year_code}-{term.term_no}" if term else None
        attendance_query = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.course_name == task.course_name,
            AaAttendanceSession.is_deleted.is_(False),
        )
        if task.class_id:
            attendance_query = attendance_query.filter(AaAttendanceSession.class_id == task.class_id)
        if term_code:
            attendance_query = attendance_query.filter(AaAttendanceSession.term_code == term_code)
        attendance_count = attendance_query.count()
    return _impact_summary(schedule_count, attendance_count, exam_count, grade_count)


def _preview_in_db(db, user, teaching_class, student_ids) -> dict:
    proposed_ids = sorted({int(value) for value in student_ids})
    if not proposed_ids:
        raise AppException("VALIDATION_ERROR", "正式名单至少需要1名学生")
    _validate_student_scope(db, user, proposed_ids)
    current_version = _current_version(db, teaching_class)
    mode = _manual_mode(
        _selection_exists(db, teaching_class),
        teaching_class.class_type,
        current_version.source_type if current_version else "",
    )
    if not mode["canManualChange"]:
        raise AppException("DATA_CONFLICT", mode["reason"], details=mode, http_status=409)
    changes = _change_sets(_current_member_ids(db, teaching_class), proposed_ids)
    impact = _downstream_impact(db, teaching_class)
    return {
        "teachingClassId": str(teaching_class.id),
        "currentVersionNo": int(teaching_class.current_roster_version_no or 0),
        "currentMemberCount": len(changes["currentIds"]),
        "proposedMemberCount": len(changes["proposedIds"]),
        "addedStudentIds": [str(value) for value in changes["addedIds"]],
        "removedStudentIds": [str(value) for value in changes["removedIds"]],
        "unchangedCount": len(changes["unchangedIds"]),
        "changed": changes["changed"],
        "impact": impact,
        "canCreate": bool(changes["changed"] and not impact["blocked"]),
        "mode": mode,
    }


def preview_roster_change(user, teaching_class_id: int, student_ids) -> dict:
    with session() as db:
        teaching_class = _get_class(db, user, int(teaching_class_id))
        return _preview_in_db(db, user, teaching_class, student_ids)


def create_manual_roster_version(user, teaching_class_id: int, student_ids, reason: str) -> dict:
    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "名单变更原因必填且不少于5字")

    from app.models import AffairsAuditTrail
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with session() as db:
        teaching_class = _get_class(db, user, int(teaching_class_id), lock=True)
        guard_term_writable(db, int(teaching_class.term_id))
        preview = _preview_in_db(db, user, teaching_class, student_ids)
        if not preview["changed"]:
            raise AppException("DATA_CONFLICT", "拟提交名单与当前正式名单完全一致，无需创建新版本", http_status=409)
        if preview["impact"]["blocked"]:
            raise AppException(
                "DATA_CONFLICT", preview["impact"]["blockerMessage"],
                details=preview, http_status=409,
            )

        version, created = teaching_class_service.create_roster_version(
            db, teaching_class, student_ids,
            source_type="MANUAL", source_id=None, reason=reason_text,
        )
        if not created:
            raise AppException("DATA_CONFLICT", "当前正式名单版本未发生变化", http_status=409)

        context = get_current_user_ctx() or {}
        db.add(AffairsAuditTrail(
            tenant_id=_tid(), biz_type="AA_TEACHING_CLASS",
            biz_id=int(teaching_class.id), action="ROSTER_VERSION_CREATE",
            operator=str(context.get("userId") or context.get("loginName") or ""),
            role_name=str(context.get("currentRoleCode") or ""),
            detail=(
                f"versionNo={version.version_no};memberCount={version.member_count};"
                f"added={len(preview['addedStudentIds'])};removed={len(preview['removedStudentIds'])};"
                f"schedule={preview['impact']['scheduleCount']};reason={reason_text}"
            )[:990],
        ))
        db.commit()
        return {
            "teachingClassId": str(teaching_class.id),
            "rosterVersionId": str(version.id),
            "versionNo": int(version.version_no),
            "memberCount": int(version.member_count),
            "sourceType": version.source_type,
            "reason": reason_text,
            "impact": preview["impact"],
        }

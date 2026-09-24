"""课表服务兼容入口。

修复学生课表中选课课程跨批次污染：LOCKED选课只并入当前发布课表批次内的排课项，
并按 schedule item 去重。其它排课、发布、冲突和管理能力继续委托既有 service。
"""
from __future__ import annotations

from . import academic_affairs_schedule_service as _legacy
from . import academic_affairs_schedule_final_service as _final
from . import academic_affairs_schedule_write_scope_r3 as _write_scope_r3
from . import academic_affairs_major_split_public_service as _major_split_public
from . import academic_affairs_major_split_allocate_r3 as _major_split_allocate_r3

# R3 targeted hardening installers.  The package imports this facade after both public
# modules exist, so the aliases already held by routers see the same module objects.
_write_scope_r3.install(_final)
_major_split_public.allocate = _major_split_allocate_r3.allocate


def __getattr__(name):
    return getattr(_legacy, name)


def _enrolled_items(db, student_id, batch_id, membership=None):
    from app.models import AaScheduleItem, AaSelectionCourse, AaSelectionRecord

    locked = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _legacy._tid(),
        AaSelectionRecord.student_id == int(student_id),
        AaSelectionRecord.status == "LOCKED",
        AaSelectionRecord.is_deleted.is_(False),
    ).all()
    if not locked:
        return []

    record_by_course = {int(row.selection_course_id): row.id for row in locked}
    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.id.in_(list(record_by_course)),
        AaSelectionCourse.tenant_id == _legacy._tid(),
        AaSelectionCourse.is_deleted.is_(False),
    ).all()

    out = []
    seen_item_ids = set()
    for course in courses:
        if not course.teaching_task_id:
            continue
        query = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _legacy._tid(),
            AaScheduleItem.batch_id == int(batch_id),
            AaScheduleItem.task_id == int(course.teaching_task_id),
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        )
        if membership is not None:
            query=query.filter(membership)
        rows=query.all()
        for item in rows:
            if item.id in seen_item_ids:
                continue
            seen_item_ids.add(item.id)
            out.append(_legacy._item_row(
                item,
                source="ENROLLED",
                selection_record_id=record_by_course.get(int(course.id)),
            ))
    return out


def merge_student_schedule_items(base_items, enrolled_items):
    """同一课表项只返回一次；若同时命中行政班和选课，保留选课来源解释。"""
    merged = {}
    anonymous_index = 0
    for row in list(base_items or []) + list(enrolled_items or []):
        item_id = str(row.get("itemId") or "").strip()
        if item_id:
            key = f"id:{item_id}"
        else:
            # 历史脏数据没有itemId时不得全部压成同一个空键，使用完整排课事实去重。
            key = "fact:" + "|".join(str(row.get(field) or "") for field in (
                "weekday", "slotNo", "startWeek", "endWeek", "weekParity",
                "courseName", "teacherKey", "classroom",
            ))
            if key == "fact:|||||||":
                anonymous_index += 1
                key = f"anonymous:{anonymous_index}"
        merged[key] = row

    return sorted(
        merged.values(),
        key=lambda row: (
            int(row.get("weekday") or 0),
            int(row.get("slotNo") or 0),
            int(row.get("startWeek") or 0),
            str(row.get("courseName") or ""),
        ),
    )


def student_view(batch_id, user, student_id):
    """行政班课表 + 本人LOCKED选课，同一批次内合并并去重。"""
    from sqlalchemy import select, exists, or_
    from app.models import AaScheduleItem, StudentProfile, AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion

    with _legacy.session() as db:
        student = db.get(StudentProfile, int(student_id))
        if not student or student.is_deleted or student.tenant_id != _legacy._tid():
            raise _legacy.not_found("学生不存在")

        # Once a task has a formal teaching class, its current roster owns membership.
        # Administrative class fallback is retained only for unprojected legacy tasks.
        tid=_legacy._tid()
        projected=exists(select(AaTeachingClass.id).where(
            AaTeachingClass.tenant_id==tid,AaTeachingClass.teaching_task_id==AaScheduleItem.task_id,
            AaTeachingClass.is_deleted.is_(False)))
        roster_tasks=select(AaTeachingClass.teaching_task_id).join(AaTeachingClassRosterVersion,
            (AaTeachingClassRosterVersion.id==AaTeachingClass.current_roster_version_id)
            & (AaTeachingClassRosterVersion.teaching_class_id==AaTeachingClass.id)
            & (AaTeachingClassRosterVersion.tenant_id==tid)
            & (AaTeachingClassRosterVersion.status=='LOCKED')
            & AaTeachingClassRosterVersion.is_deleted.is_(False)).join(AaTeachingClassMember,
            (AaTeachingClassMember.teaching_class_id==AaTeachingClass.id)
            & (AaTeachingClassMember.roster_version_id==AaTeachingClass.current_roster_version_id)
            & (AaTeachingClassMember.tenant_id==tid)).where(
                AaTeachingClass.tenant_id==tid,AaTeachingClass.status=='ACTIVE',AaTeachingClass.roster_status=='LOCKED',
                AaTeachingClass.is_deleted.is_(False),AaTeachingClass.current_roster_version_id.is_not(None),
                AaTeachingClassMember.student_id==student.id,AaTeachingClassMember.status=='ACTIVE',
                AaTeachingClassMember.is_deleted.is_(False))
        membership=AaScheduleItem.task_id.in_(roster_tasks)
        if student.class_id:
            membership=or_(membership,(AaScheduleItem.class_id==int(student.class_id)) & ~projected)
        base_items=_legacy._view(db,batch_id,[membership])
        enrolled_membership=or_(membership,~projected)
        enrolled_items = _enrolled_items(db, student.id, batch_id,enrolled_membership)
        items = merge_student_schedule_items(base_items, enrolled_items)
        note = "" if items else "当前正式课表中暂无本人课程"
        return {"items": items, "note": note}

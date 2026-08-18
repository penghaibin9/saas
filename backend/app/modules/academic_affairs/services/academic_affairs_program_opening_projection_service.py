"""A-W2 canonical Opening Projection facade.

The existing governance service remains the structural/difference engine.  This facade
applies the canonical Program activation resolver before the projection is exposed,
so a class override and its major+grade fallback can coexist without producing two
competing execution plans.  It persists nothing and therefore does not create a second
OpeningPlan truth.
"""
from __future__ import annotations

from collections import Counter

from app.services.db_service import _tid, session

from . import academic_affairs_program_governance_service as legacy
from . import academic_affairs_program_activation_service as activation

PROGRAM_UNRESOLVED = "PROGRAM_UNRESOLVED"
_ALLOWED_FILTERS = set(legacy._ALLOWED_DIFF_STATUSES) | {PROGRAM_UNRESOLVED}


def _summary(items: list[dict]) -> dict:
    base = legacy._summary(items)
    counts = Counter(str(item.get("status") or "") for item in items)
    unresolved_programs = counts[PROGRAM_UNRESOLVED]
    if unresolved_programs:
        base["unresolved"] += unresolved_programs
        base["blockerCount"] += unresolved_programs
        base["canGenerateOrConfirm"] = False
        base["conclusion"] = f"存在 {base['blockerCount']} 个开课阻断差异"
    base["programUnresolved"] = unresolved_programs
    return base


def _scope_key(row: dict):
    major_id = str(row.get("majorId") or "").strip()
    grade = str(row.get("gradeYear") or "").strip()
    class_id = str(row.get("classId") or "").strip()
    if not major_id or not grade:
        return None
    return int(major_id), grade, (int(class_id) if class_id else None)


def _unresolved_row(row: dict, resolution) -> dict:
    return {
        "key": f"program-unresolved-{row.get('majorId') or 'none'}-{row.get('gradeYear') or 'none'}-{row.get('classId') or 'generic'}",
        "programId": "",
        "programName": "",
        "programStatus": "",
        "majorId": row.get("majorId") or "",
        "gradeYear": row.get("gradeYear") or "",
        "classId": row.get("classId") or "",
        "className": row.get("className") or "",
        "courseId": "",
        "courseCode": "",
        "courseName": "",
        "planTermNo": row.get("planTermNo"),
        "status": PROGRAM_UNRESOLVED,
        "message": resolution.message,
        "taskIds": [],
        "teacherName": "",
        "responsibility": "PROGRAM_BINDING",
        "programResolutionRule": resolution.rule,
        "fixRoute": "/admin/academic-affairs/programs",
    }


def _over_opened_from_dropped(row: dict, task_id: str) -> dict:
    converted = dict(row)
    converted.update({
        "key": f"over-opened-task-{task_id}",
        "programId": "",
        "programName": "",
        "programStatus": "",
        "status": "OVER_OPENED",
        "message": "教学任务存在，但不属于该班级当前唯一生效方案本学期应开课程",
        "taskIds": [str(task_id)],
        "responsibility": "TEACHING_TASK",
        "fixRoute": "/admin/academic-affairs/teaching-tasks",
    })
    return converted


def opening_differences(user, term_id: int, major_id: int | None = None,
                        grade_year: str | None = None, status: str | None = None) -> dict:
    """Return the derived opening projection after canonical Program resolution."""
    active_filter = str(status or "").strip().upper()
    if active_filter and active_filter not in _ALLOWED_FILTERS:
        active_filter = ""

    raw = legacy.opening_differences(user, term_id, major_id, grade_year, None)
    raw_items = list(raw.get("items") or [])
    existing_over_opened = [row for row in raw_items if row.get("status") == "OVER_OPENED"]
    candidates = [row for row in raw_items if row.get("status") != "OVER_OPENED"]

    kept_by_key: dict[str, dict] = {}
    dropped_with_tasks: list[dict] = []
    unresolved_by_scope: dict[tuple, dict] = {}
    winner_course_keys: set[tuple[int, int]] = set()

    with session() as db:
        resolution_cache = {}
        for row in candidates:
            key = _scope_key(row)
            program_id = str(row.get("programId") or "").strip()
            if key is None or not program_id:
                kept_by_key.setdefault(str(row.get("key") or id(row)), row)
                continue

            if key not in resolution_cache:
                scope_major, scope_grade, scope_class = key
                resolution_cache[key] = activation.resolve_program_for_scope(
                    db,
                    tenant_id=_tid(),
                    major_id=scope_major,
                    grade_year=scope_grade,
                    class_id=scope_class,
                )
            resolution = resolution_cache[key]
            if resolution.status != "RESOLVED":
                unresolved_by_scope.setdefault(key, _unresolved_row(row, resolution))
                if row.get("taskIds"):
                    dropped_with_tasks.append(row)
                continue

            if int(program_id) != int(resolution.program.id):
                if row.get("taskIds"):
                    dropped_with_tasks.append(row)
                continue

            kept_by_key.setdefault(str(row.get("key") or id(row)), row)
            course_id = str(row.get("courseId") or "").strip()
            class_id = str(row.get("classId") or "").strip()
            if course_id and class_id:
                winner_course_keys.add((int(course_id), int(class_id)))

    items = list(kept_by_key.values()) + list(unresolved_by_scope.values())

    over_opened_by_task: dict[str, dict] = {}
    for row in existing_over_opened:
        task_ids = [str(value) for value in (row.get("taskIds") or [])]
        if task_ids:
            for task_id in task_ids:
                over_opened_by_task.setdefault(task_id, row)
        else:
            over_opened_by_task.setdefault(str(row.get("key") or id(row)), row)

    for row in dropped_with_tasks:
        course_id = str(row.get("courseId") or "").strip()
        class_id = str(row.get("classId") or "").strip()
        if course_id and class_id and (int(course_id), int(class_id)) in winner_course_keys:
            continue
        for task_id in row.get("taskIds") or []:
            task_key = str(task_id)
            over_opened_by_task.setdefault(task_key, _over_opened_from_dropped(row, task_key))

    items.extend(over_opened_by_task.values())
    items.sort(key=lambda row: (
        0 if row.get("status") != "READY" else 1,
        row.get("majorId") or "",
        row.get("gradeYear") or "",
        row.get("className") or "",
        row.get("courseCode") or row.get("courseName") or "",
    ))

    full_summary = _summary(items)
    display_items = [row for row in items if row.get("status") == active_filter] if active_filter else items
    return {
        **raw,
        "activeProgramStatuses": sorted(activation.CURRENT_EFFECTIVE_PROGRAM_STATUSES),
        "summary": full_summary,
        "filteredTotal": len(display_items),
        "activeFilter": active_filter,
        "items": display_items,
    }

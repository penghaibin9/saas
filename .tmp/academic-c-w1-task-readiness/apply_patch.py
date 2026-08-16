from pathlib import Path

canonical_path = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_service.py")
canonical = canonical_path.read_text(encoding="utf-8")
old = '''_ATTENDANCE_TASK_STATUSES = {"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"}\n\n\ndef _op():\n'''
new = '''_ATTENDANCE_TASK_STATUSES = {"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"}\n\n\ndef attendance_task_executable(status) -> bool:\n    """Single executable-state contract shared by attendance read and write paths."""\n    return str(status or "").strip().upper() in _ATTENDANCE_TASK_STATUSES\n\n\ndef _op():\n'''
if canonical.count(old) != 1:
    raise SystemExit(f"canonical helper anchor count={canonical.count(old)}")
canonical = canonical.replace(old, new, 1)
canonical_path.write_text(canonical, encoding="utf-8")

public_path = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py")
public = public_path.read_text(encoding="utf-8")
old = '''_ATTENDANCE_TASK_STATUSES = _canonical._ATTENDANCE_TASK_STATUSES\n_ADMIN_SPECIAL = "ADMIN_SPECIAL"\n'''
new = '''attendance_task_executable = _canonical.attendance_task_executable\n_ADMIN_SPECIAL = "ADMIN_SPECIAL"\n'''
if public.count(old) != 1:
    raise SystemExit(f"public helper import anchor count={public.count(old)}")
public = public.replace(old, new, 1)
old = '''            if str(task.status or "").upper() not in _ATTENDANCE_TASK_STATUSES:\n                raise AppException("DATA_CONFLICT", "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤")\n'''
new = '''            if not attendance_task_executable(task.status):\n                raise AppException("DATA_CONFLICT", "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤")\n'''
if public.count(old) != 1:
    raise SystemExit(f"public task-state guard anchor count={public.count(old)}")
public = public.replace(old, new, 1)
public_path.write_text(public, encoding="utf-8")

facade_path = Path("backend/app/modules/academic_affairs/services/mobile_academic_affairs_facade.py")
facade = facade_path.read_text(encoding="utf-8")
old = '''def teacher_attendance_class_options(user) -> dict:\n    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, SchoolClass\n    from .academic_affairs_attendance_occurrence_consumer import formal_schedule_patterns_for_tasks\n'''
new = '''def teacher_attendance_class_options(user) -> dict:\n    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm, SchoolClass\n    from .academic_affairs_attendance_occurrence_consumer import formal_schedule_patterns_for_tasks\n    from .academic_affairs_attendance_service import attendance_task_executable\n'''
if facade.count(old) != 1:
    raise SystemExit(f"facade import anchor count={facade.count(old)}")
facade = facade.replace(old, new, 1)
old = '''                AaTeachingTask.is_deleted.is_(False),\n                AaTeachingTask.status.notin_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER", "MERGED"]),\n                AaTeachingTask.class_id.is_not(None),\n'''
new = '''                AaTeachingTask.is_deleted.is_(False),\n                AaTeachingTask.class_id.is_not(None),\n'''
if facade.count(old) != 1:
    raise SystemExit(f"facade broad-status filter anchor count={facade.count(old)}")
facade = facade.replace(old, new, 1)
old = '''            tasks = db.scalars(select(AaTeachingTask).where(*conditions)).all()\n\n        class_ids = sorted({int(task.class_id) for task in tasks if task.class_id})\n'''
new = '''            tasks = db.scalars(select(AaTeachingTask).where(*conditions)).all()\n            tasks = [task for task in tasks if attendance_task_executable(task.status)]\n\n        class_ids = sorted({int(task.class_id) for task in tasks if task.class_id})\n'''
if facade.count(old) != 1:
    raise SystemExit(f"facade executable filter anchor count={facade.count(old)}")
facade = facade.replace(old, new, 1)
facade_path.write_text(facade, encoding="utf-8")

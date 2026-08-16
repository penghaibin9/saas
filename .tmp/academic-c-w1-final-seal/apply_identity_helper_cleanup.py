from pathlib import Path

path = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py")
text = path.read_text(encoding="utf-8")

old = '''    task_teacher = str(getattr(task, "teacher_key", "") or "").strip()\n    item_teacher = str(getattr(item, "teacher_key", "") or "").strip()\n    if not task_teacher or not item_teacher or task_teacher != item_teacher:\n        _conflict("正式课表教师身份与教学任务不一致")\n    task_class = int(getattr(task, "class_id", 0) or 0)\n    item_class = int(getattr(item, "class_id", 0) or 0)\n    if task_class and item_class and task_class != item_class:\n        _conflict("正式课表班级身份与教学任务不一致")\n    task_course = int(getattr(task, "course_id", 0) or 0)\n    item_course = int(getattr(item, "course_id", 0) or 0)\n    if task_course and item_course and task_course != item_course:\n        _conflict("正式课表课程身份与教学任务不一致")\n\n    published_at = getattr(selected_head, "published_at", None)\n'''
new = '''    item_teacher, item_class = _validate_task_item_identity(task, item)\n\n    published_at = getattr(selected_head, "published_at", None)\n'''
if text.count(old) != 1:
    raise SystemExit(f"write-side duplicate identity anchor count={text.count(old)}")
text = text.replace(old, new, 1)

if text.count("_validate_task_item_identity(task, item)") < 2:
    raise SystemExit("shared task/item identity helper is not used by both read and write paths")
path.write_text(text, encoding="utf-8")

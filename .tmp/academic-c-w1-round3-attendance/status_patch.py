from pathlib import Path

path = Path("backend/scripts/e2e_academic_affairs_round3.py")
text = path.read_text(encoding="utf-8")

old = '''    for task in options.get("items") or []:\n        if not task.get("formalOccurrenceReady"):\n            continue\n        task_id = str(task.get("teachingTaskId") or "").strip()\n'''
new = '''    allowed_task_statuses = {"TEACHER_CONFIRMED", "COLLEGE_REVIEW", "APPROVED", "READY"}\n    for task in options.get("items") or []:\n        if not task.get("formalOccurrenceReady"):\n            continue\n        if str(task.get("taskStatus") or "").upper() not in allowed_task_statuses:\n            continue\n        task_id = str(task.get("teachingTaskId") or "").strip()\n'''
if old not in text:
    raise SystemExit("Round3 task-status filter anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

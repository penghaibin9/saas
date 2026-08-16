from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"exact replacement guard failed for {path}: count={text.count(old)}")
    p.write_text(text.replace(old, new))


service = "backend/app/modules/academic_affairs/services/academic_affairs_selection_course_command_service.py"
replace(
    service,
    '''        if str(task.status or "").upper() != "READY":\n            raise _conflict(\n                "教学任务未处于 READY，不可作为选课供给",\n                teachingTaskId=str(task_id),\n                taskStatus=str(task.status or ""),\n            )\n        if not getattr(task, "course_id", None) or int(task.course_id) != course_id:\n''',
    '''        if str(task.status or "").upper() != "READY":\n            raise _conflict(\n                "教学任务未处于 READY，不可作为选课供给",\n                teachingTaskId=str(task_id),\n                taskStatus=str(task.status or ""),\n            )\n        formation_mode = str(getattr(task, "formation_mode", None) or "").strip().upper()\n        if formation_mode != "SELECTABLE":\n            raise _conflict(\n                "教学任务不是 SELECTABLE 选课形成模式，不可作为选课供给",\n                teachingTaskId=str(task_id),\n                formationMode=formation_mode or None,\n                requiredFormationMode="SELECTABLE",\n            )\n        if not getattr(task, "course_id", None) or int(task.course_id) != course_id:\n''',
)

# Replace the stale module contract note now that A-C4 is an INT-owned persisted fact.
test_path = "backend/tests/test_aa_selection_w4_task_identity.py"
replace(
    test_path,
    '''Focused MySQL contracts only.  formationMode is intentionally not asserted here until\nA-C4 publishes its authoritative enum/formation contract.\n''',
    '''Focused MySQL contracts only.  A-C4 formationMode is now an INT-owned persisted fact:\nformal SelectionCourse supply accepts only READY + SELECTABLE TeachingTask rows.\n''',
)
replace(
    test_path,
    '''        def task(batch, bound_course, status, suffix):\n            row = AaTeachingTask(\n''',
    '''        def task(batch, bound_course, status, suffix, formation_mode="SELECTABLE"):\n            row = AaTeachingTask(\n''',
)
replace(
    test_path,
    '''                weekly_hours=2,\n                total_hours=32,\n                start_week=2,\n''',
    '''                weekly_hours=2,\n                total_hours=32,\n                formation_mode=formation_mode,\n                start_week=2,\n''',
)
replace(
    test_path,
    '''        wrong_term = task(other_task_batch, course, "READY", "term")\n\n        result = {\n''',
    '''        wrong_term = task(other_task_batch, course, "READY", "term")\n        null_formation = task(task_batch, course, "READY", "null", None)\n        admin_fixed = task(task_batch, course, "READY", "fixed", "ADMIN_FIXED")\n        merged = task(task_batch, course, "READY", "merged", "MERGED")\n\n        result = {\n''',
)
replace(
    test_path,
    '''            "wrongTerm": int(wrong_term.id),\n            "teacherName": ready.teacher_name,\n''',
    '''            "wrongTerm": int(wrong_term.id),\n            "nullFormation": int(null_formation.id),\n            "adminFixed": int(admin_fixed.id),\n            "merged": int(merged.id),\n            "teacherName": ready.teacher_name,\n''',
)
anchor = '''def test_w4_task_course_mismatch_fails_closed(client, db_mode):\n'''
insert = '''@pytest.mark.parametrize("fact_key", ["nullFormation", "adminFixed", "merged"])\ndef test_w4_non_selectable_formation_fails_closed(client, db_mode, fact_key):\n    facts = _seed(db_mode)\n    admin = _admin(client)\n    response = _add(\n        client, admin, _batch(client, admin, facts["term"]), facts["course"], facts[fact_key],\n    )\n    assert response.status_code == 409, response.text\n    assert "SELECTABLE" in response.text and "编班" in response.text\n\n\n'''
p = Path(test_path)
text = p.read_text()
if text.count(anchor) != 1:
    raise SystemExit(f"test insertion guard failed: count={text.count(anchor)}")
p.write_text(text.replace(anchor, insert + anchor))
replace(
    test_path,
    '''    # A-C4 is still pending: W4 must not invent a local formationMode enum.\n    assert "formationMode" not in command_source\n''',
    '''    assert 'formation_mode != "SELECTABLE"' in command_source\n    assert 'requiredFormationMode="SELECTABLE"' in command_source\n''',
)

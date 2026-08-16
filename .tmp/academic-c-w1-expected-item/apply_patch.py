from pathlib import Path

consumer_path = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_occurrence_consumer.py")
consumer = consumer_path.read_text(encoding="utf-8")

old = '''    session_date: str,\n    slot_no,\n    lock: bool = False,\n) -> dict:\n'''
new = '''    session_date: str,\n    slot_no,\n    expected_schedule_item_id=None,\n    lock: bool = False,\n) -> dict:\n'''
if old not in consumer:
    raise SystemExit("resolver signature anchor missing")
consumer = consumer.replace(old, new, 1)

old = '''    if requested_slot <= 0:\n        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次")\n\n    requested = _parse_date(session_date)\n'''
new = '''    if requested_slot <= 0:\n        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次")\n\n    expected_item_id = None\n    if expected_schedule_item_id not in (None, ""):\n        try:\n            expected_item_id = int(expected_schedule_item_id)\n        except (TypeError, ValueError) as exc:\n            raise AppException("VALIDATION_ERROR", "scheduleItemId 须为有效数字") from exc\n        if expected_item_id <= 0:\n            raise AppException("VALIDATION_ERROR", "scheduleItemId 须为有效数字")\n\n    requested = _parse_date(session_date)\n'''
if old not in consumer:
    raise SystemExit("resolver early-validation anchor missing")
consumer = consumer.replace(old, new, 1)

old = '''    item = candidates[0]\n    item, change_evidence = _lock_and_validate_selected_item(\n        db, item, task, lock=lock,\n    )\n    selected_head = next(\n'''
new = '''    item = candidates[0]\n    item, change_evidence = _lock_and_validate_selected_item(\n        db, item, task, lock=lock,\n    )\n    if expected_item_id is not None and expected_item_id != int(item.id):\n        _conflict(\n            "正式课次已变化，请刷新后重新进入点名",\n            details={\n                "expectedScheduleItemId": str(expected_item_id),\n                "resolvedScheduleItemId": str(item.id),\n                "teachingTaskId": str(task.id),\n                "sessionDate": requested.isoformat(),\n                "slotNo": requested_slot,\n            },\n        )\n    selected_head = next(\n'''
if old not in consumer:
    raise SystemExit("selected item expectation anchor missing")
consumer = consumer.replace(old, new, 1)
consumer_path.write_text(consumer, encoding="utf-8")

public_path = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py")
public = public_path.read_text(encoding="utf-8")
public_anchor = '''                    slot_no=slot_no,\n                    lock=True,\n'''
if public.count(public_anchor) != 1:
    raise SystemExit(f"public resolver slot/lock anchor count={public.count(public_anchor)}")
public = public.replace(
    public_anchor,
    '''                    slot_no=slot_no,\n                    expected_schedule_item_id=body.get("scheduleItemId"),\n                    lock=True,\n''',
    1,
)
public_path.write_text(public, encoding="utf-8")

from pathlib import Path

path = Path("backend/scripts/e2e_academic_affairs_round3.py")
text = path.read_text(encoding="utf-8")

old = '''        for pattern in task.get("formalSchedulePatterns") or []:\n            try:\n                weekday = int(pattern.get("weekday") or 0)\n                slot_no = int(pattern.get("slotNo") or 0)\n'''
new = '''        for pattern in task.get("formalSchedulePatterns") or []:\n            try:\n                schedule_item_id = int(pattern.get("scheduleItemId") or 0)\n                weekday = int(pattern.get("weekday") or 0)\n                slot_no = int(pattern.get("slotNo") or 0)\n'''
if old not in text:
    raise SystemExit("Round3 scheduleItemId validation anchor missing")
text = text.replace(old, new, 1)

old = '''            if weekday not in range(1, 8) or slot_no <= 0 or start_week <= 0 or end_week < start_week:\n                continue\n'''
new = '''            if schedule_item_id <= 0 or weekday not in range(1, 8) or slot_no <= 0 or start_week <= 0 or end_week < start_week:\n                continue\n'''
if old not in text:
    raise SystemExit("Round3 scheduleItemId positive guard anchor missing")
text = text.replace(old, new, 1)

old = '''                    "scheduleItemId": str(pattern.get("scheduleItemId") or ""),\n                    "scopeHeadVersion": int(pattern.get("scopeHeadVersion") or 0),\n'''
new = '''                    "scheduleItemId": str(schedule_item_id),\n                    "scopeHeadVersion": int(pattern.get("scopeHeadVersion") or 0),\n'''
if old not in text:
    raise SystemExit("Round3 normalized scheduleItem metadata anchor missing")
text = text.replace(old, new, 1)

old = '''                        "sessionDate": candidate.isoformat(),\n                        "slotNo": slot_no,\n                        "sessionType": "常规",\n'''
new = '''                        "sessionDate": candidate.isoformat(),\n                        "slotNo": slot_no,\n                        "scheduleItemId": str(schedule_item_id),\n                        "sessionType": "常规",\n'''
if old not in text:
    raise SystemExit("Round3 scheduleItemId payload anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

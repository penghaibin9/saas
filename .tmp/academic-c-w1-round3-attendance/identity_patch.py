from pathlib import Path

path = Path("backend/scripts/e2e_academic_affairs_round3.py")
text = path.read_text(encoding="utf-8")
old = '''                        "sessionDate": candidate.isoformat(),\n                        "slotNo": slot_no,\n                        "sessionType": "常规",\n'''
new = '''                        "sessionDate": candidate.isoformat(),\n                        "slotNo": slot_no,\n                        "scheduleItemId": str(pattern.get("scheduleItemId") or ""),\n                        "sessionType": "常规",\n'''
if old not in text:
    raise SystemExit("Round3 scheduleItemId payload anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

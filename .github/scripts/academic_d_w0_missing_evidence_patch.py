from pathlib import Path

path = Path("backend/app/modules/academic_affairs/services/academic_affairs_graduation_immutable_service.py")
source = path.read_text(encoding="utf-8")
old = '''    if not rows or not required_unknown_blockers:\n        return "SYSTEM_ABNORMAL"\n    for item in rows:\n'''
new = '''    if not rows or not required_unknown_blockers:\n        return "SYSTEM_ABNORMAL"\n    present_codes = {str(item.get("item") or "").upper() for item in rows}\n    if not required_unknown_blockers.issubset(present_codes):\n        return "SYSTEM_ABNORMAL"\n    for item in rows:\n'''
if source.count(old) != 1:
    raise SystemExit(f"expected exactly one strict-overall insertion point, found {source.count(old)}")
patched = source.replace(old, new, 1)
path.write_text(patched, encoding="utf-8")

check = path.read_text(encoding="utf-8")
for token in (
    'present_codes = {str(item.get("item") or "").upper() for item in rows}',
    'if not required_unknown_blockers.issubset(present_codes):',
):
    if token not in check:
        raise SystemExit(f"missing patched token: {token}")
print("D-W0 missing required evidence fail-closed patch applied")

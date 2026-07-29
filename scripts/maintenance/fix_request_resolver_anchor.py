from pathlib import Path


path = Path("scripts/maintenance/resolve_student_affairs_request_conflicts.py")
text = path.read_text(encoding="utf-8")
old = '''    text = insert_once(
        text,
        "}\\n\\nfunction selectedInternshipBatch(path)",
        helper_block + "\\nfunction selectedInternshipBatch(path)",
        "student portal graduation temp helpers",
    )
    # insert_once above duplicates function name from anchor; normalize once.
    text = text.replace(
        "function selectedInternshipBatch(path)\\nfunction selectedInternshipBatch(path)",
        "function selectedInternshipBatch(path)",
    )
'''
new = '''    marker = "\\n\\nfunction selectedInternshipBatch(path) {"
    if "function readTempFiles()" not in text:
        if marker not in text:
            raise RuntimeError("missing student portal helper insertion marker")
        text = text.replace(marker, helper_block + marker, 1)
'''
if new not in text:
    if old not in text:
        raise RuntimeError("request resolver anchor block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("request resolver anchor fixed", flush=True)

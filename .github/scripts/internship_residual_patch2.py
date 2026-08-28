from pathlib import Path


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} matches, got {actual}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Archive staff scope is keyed by stable advisor_user_id, not display name.
replace_exact(
    "tests/test_internship_archive.py",
    "def _mentor(name, tid=TID):",
    "def _mentor(name, user_id=None, tid=TID):",
)
replace_exact(
    "tests/test_internship_archive.py",
    '        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",',
    '        "userId": str(user_id or f"u-{name}"), "realName": name, "userType": "TEACHER",',
)
replace_exact(
    "tests/test_internship_archive.py",
    "            db.add(advisor); db.flush()\n            r = InternshipRecord(tenant_id=TID, student_id=s.id,",
    "            db.add(advisor); db.flush()\n            ids[f\"adv_{key}\"] = advisor.id\n            r = InternshipRecord(tenant_id=TID, student_id=s.id,",
)
replace_exact(
    "tests/test_internship_archive.py",
    'headers=_mentor("刘强"), params={"batchId": ids["batch"]}',
    'headers=_mentor("刘强", ids["adv_a"]), params={"batchId": ids["batch"]}',
)

# Special filing review-flow must use the authoritative File Center write path.
# The earlier direct row remains only as harmless setup data; the filing itself binds
# the real store_bytes file returned below.
replace_exact(
    "tests/test_internship_v93_special_filing_review_flow.py",
    '    db.close()\n    return ids\n\n\ndef _create_filing(ids):',
    '''    db.close()
    _ctx(REQUESTER)
    from app.services import file_service
    stored = file_service.store_bytes(
        b"special-filing-authoritative-evidence",
        "special-filing-evidence.txt",
        biz_type="TEMP_PRIVATE",
        user=REQUESTER,
        visibility="PRIVATE",
    )
    ids["file"] = stored["fileId"]
    return ids


def _create_filing(ids):''',
)

print("residual internship patch2 applied")

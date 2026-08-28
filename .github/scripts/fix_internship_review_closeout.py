from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


# 1) Frozen participant rosters: apply internship row scope only. Do not reuse
# new-batch eligibility filters (current_stage/student_status), otherwise alumni
# disappear from a legally frozen historical roster.
participant_path = ROOT / "backend/app/modules/internship/services/internship_participant_service.py"
participant = participant_path.read_text(encoding="utf-8")
anchor = "# ── 名单读写 ──────────────────────────────────────────────────────────────\n\n"
helper = '''def _visible_participant_student_ids(db, rows, user: dict | None = None) -> set[int]:
    """Frozen-roster visibility = caller internship data scope only.

    The participant rows are historical evidence after freeze. Do not pass their student IDs
    through ``student_scope_resolver.resolve`` because that resolver intentionally applies
    new-batch eligibility filters (current_stage/student_status). A participant who later
    graduates or changes lifecycle status must remain in the frozen roster while still being
    constrained by the caller's current internship row scope.
    """
    student_ids = {int(r.student_id) for r in rows if getattr(r, "student_id", None)}
    if not student_ids:
        return set()
    if user is None:
        return student_ids

    from app.models import InternshipRecord
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.modules.internship.services.internship_student_service import _current_scope

    internship_ids = {int(r.internship_id) for r in rows if getattr(r, "internship_id", None)}
    visible: set[int] = set()
    if internship_ids:
        q = apply_internship_record_scope(
            select(InternshipRecord.student_id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.id.in_(internship_ids),
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        )
        visible.update(int(value) for value in db.scalars(q).all())

    # Legacy participant rows without internship_id have no trustworthy record relation on
    # which a scoped teacher can be authorized. Fail closed for SCOPED roles; tenant admins
    # may still inspect the frozen snapshot for audit/reconciliation.
    if _current_scope(user).get("mode") != "SCOPED":
        visible.update(
            int(r.student_id) for r in rows
            if getattr(r, "student_id", None) and not getattr(r, "internship_id", None)
        )
    return visible


'''
if "def _visible_participant_student_ids" not in participant:
    participant = replace_once(participant, anchor, helper + anchor, "participant helper anchor")

old = '''        requested_ids = [int(r.student_id) for r in rows]
        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": requested_ids}),
                                user=user, limit=None) if requested_ids else None
        allowed_ids = {int(s.id) for s in allowed.students} if allowed else set()
        rows = [r for r in rows if int(r.student_id) in allowed_ids]
'''
new = '''        allowed_ids = _visible_participant_student_ids(db, rows, user=user)
        rows = [r for r in rows if int(r.student_id) in allowed_ids]
'''
# This exact old block appears in list_participants and summary.
if participant.count(old) != 2:
    raise SystemExit(f"participant roster scope blocks: expected 2, got {participant.count(old)}")
participant = participant.replace(old, new, 2)

old = '''        allowed = scope.resolve(db, _tid(), scope.parse_rule({"studentIds": [int(row.student_id)]}),
                                user=user, limit=None)
        if int(row.student_id) not in {int(s.id) for s in allowed.students}:
            from app.core.exceptions import no_permission
            raise no_permission("该参与人不在你的数据范围内")
'''
new = '''        if int(row.student_id) not in _visible_participant_student_ids(db, [row], user=user):
            from app.core.exceptions import no_permission
            raise no_permission("该参与人不在你的数据范围内")
'''
participant = replace_once(participant, old, new, "participant remove scope")

old = '''        from app.core.affairs_security import student_directory_scope
        allow_classes, allow_students = student_directory_scope(user) if user is not None else (None, None)
        scoped_view = allow_classes is not None or allow_students is not None
'''
new = '''        from app.modules.internship.services.internship_student_service import _current_scope
        scoped_view = bool(user is not None and _current_scope(user).get("mode") == "SCOPED")
'''
participant = replace_once(participant, old, new, "participant summary scope marker")
participant_path.write_text(participant, encoding="utf-8")


# 2) InternshipRecord optimistic locking: lock the row before version comparison and
# advance version on every guarded mutation. This prevents two stale writers from both
# validating the same version and then overwriting each other.
student_path = ROOT / "backend/app/modules/internship/services/internship_student_service.py"
student = student_path.read_text(encoding="utf-8")
old = '''def _get(db, rec_id) -> InternshipRecord:
    r = db.get(InternshipRecord, _as_id(rec_id))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("实习学生记录不存在或不在当前数据范围内")
    return r


'''
new = old + '''def _get_for_update(db, rec_id) -> InternshipRecord:
    r = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(rec_id),
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False),
    ).with_for_update())
    if not r:
        raise not_found("实习学生记录不存在或不在当前数据范围内")
    return r


'''
if "def _get_for_update" not in student:
    student = replace_once(student, old, new, "student lock helper")

for fn in ("update_student_record", "assign_advisor", "set_status", "set_eligibility", "set_destination"):
    marker = f"def {fn}"
    start = student.find(marker)
    if start < 0:
        raise SystemExit(f"missing function {fn}")
    next_def = student.find("\ndef ", start + len(marker))
    end = len(student) if next_def < 0 else next_def
    block = student[start:end]
    old_line = "        r = _get(db, rec_id)"
    if old_line not in block:
        raise SystemExit(f"{fn}: expected unlocked record read")
    block = block.replace(old_line, "        r = _get_for_update(db, rec_id)", 1)
    student = student[:start] + block + student[end:]

old = '''        _trail(db, r.id, f"STATUS_{action}", detail)
        db.commit()
'''
new = '''        r.version = int(r.version or 0) + 1
        _trail(db, r.id, f"STATUS_{action}", detail)
        db.commit()
'''
student = replace_once(student, old, new, "status version advance")

old = '''        r.eligibility_status = status
        _trail(db, r.id, "ELIGIBILITY", {"status": status, "reason": reason})
        db.commit()
'''
new = '''        r.eligibility_status = status
        r.version = int(r.version or 0) + 1
        _trail(db, r.id, "ELIGIBILITY", {"status": status, "reason": reason,
                                          "recordVersion": int(r.version or 0)})
        db.commit()
'''
student = replace_once(student, old, new, "eligibility version advance")

old = '''        r.destination_type = destination
        _trail(db, r.id, "DESTINATION", {"destination": destination, "reason": reason})
        db.commit()
'''
new = '''        r.destination_type = destination
        r.version = int(r.version or 0) + 1
        _trail(db, r.id, "DESTINATION", {"destination": destination, "reason": reason,
                                          "recordVersion": int(r.version or 0)})
        db.commit()
'''
student = replace_once(student, old, new, "destination version advance")
student_path.write_text(student, encoding="utf-8")


# 3) Regression contracts for the two review findings.
test_path = ROOT / "backend/tests/test_internship_prelaunch_static_contracts.py"
tests = test_path.read_text(encoding="utf-8")
addition = '''

def test_frozen_participant_roster_scope_does_not_reapply_lifecycle_eligibility():
    text = src("app/modules/internship/services/internship_participant_service.py")
    assert "def _visible_participant_student_ids" in text
    assert "apply_internship_record_scope" in text
    start = text.index("def list_participants")
    end = text.index("def add_participants", start)
    assert "scope.resolve" not in text[start:end]
    start = text.index("def summary")
    assert "scope.resolve" not in text[start:]


def test_student_guarded_mutations_lock_and_advance_record_version():
    text = src("app/modules/internship/services/internship_student_service.py")
    assert "def _get_for_update" in text
    for name in ("update_student_record", "assign_advisor", "set_status", "set_eligibility", "set_destination"):
        start = text.index(f"def {name}")
        next_def = text.find("\\ndef ", start + 4)
        block = text[start:] if next_def < 0 else text[start:next_def]
        assert "_get_for_update(db, rec_id)" in block
    for name in ("set_status", "set_eligibility", "set_destination"):
        start = text.index(f"def {name}")
        next_def = text.find("\\ndef ", start + 4)
        block = text[start:] if next_def < 0 else text[start:next_def]
        assert "r.version = int(r.version or 0) + 1" in block
'''
if "test_frozen_participant_roster_scope_does_not_reapply_lifecycle_eligibility" not in tests:
    tests = tests.rstrip() + addition + "\n"
test_path.write_text(tests, encoding="utf-8")

print("internship review closeout patch applied")

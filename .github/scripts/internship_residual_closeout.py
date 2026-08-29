from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    text = read(path)
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} matches, got {actual}: {old!r}")
    write(path, text.replace(old, new))


# 1) Archive score guard: production ARCHIVE compliance requires a stable advisor identity.
replace_exact(
    "tests/test_internship_score_archive_guard.py",
    "    from app.db.session import get_sessionmaker\n    from app.models import (",
    "    from app.db.session import get_sessionmaker\n    from app.models import User\n    from app.models import (",
)
replace_exact(
    "tests/test_internship_score_archive_guard.py",
    "        record = InternshipRecord(\n            tenant_id=TID,\n            student_id=student.id,\n            advisor_name=\"成绩归档老师\",",
    "        advisor = User(\n            tenant_id=TID, login_name=f\"score-archive-advisor-{uuid4().hex[:8]}\",\n            real_name=\"成绩归档老师\", password_hash=\"test-only\",\n            user_type=\"TEACHER\", status=\"ACTIVE\",\n        )\n        db.add(advisor)\n        db.flush()\n        record = InternshipRecord(\n            tenant_id=TID,\n            student_id=student.id,\n            advisor_user_id=advisor.id,\n            advisor_name=\"成绩归档老师\",",
)

# 2) Archive completeness: both fixture records get real advisor identities; B remains incomplete
# because its business materials are intentionally absent.
replace_exact(
    "tests/test_internship_archive.py",
    "                            InternshipStudentEval, StudentProfile, WeeklyReport)",
    "                            InternshipStudentEval, StudentProfile, User, WeeklyReport)",
)
replace_exact(
    "tests/test_internship_archive.py",
    "            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,",
    "            advisor = User(tenant_id=TID,\n                           login_name=f\"archive-advisor-{key}-{uuid4().hex[:8]}\",\n                           real_name=adv, password_hash=\"test-only\",\n                           user_type=\"TEACHER\", status=\"ACTIVE\")\n            db.add(advisor); db.flush()\n            r = InternshipRecord(tenant_id=TID, student_id=s.id,\n                                 advisor_user_id=advisor.id, advisor_name=adv,",
)

# 3) Special filing first-create coverage must bind a real clean TEMP_PRIVATE evidence file.
replace_exact(
    "tests/test_internship_v93_batch2_remaining_first_create.py",
    "    ids = _seed(db)\n    db.commit()\n    db.close()\n\n    _admin_ctx()\n    svc.create({\n        \"internshipId\": str(ids[\"internship\"]), \"filingType\": \"OTHER\",",
    "    ids = _seed(db)\n    file_id = _seed_evidence_file(db)\n    db.commit()\n    db.close()\n\n    _admin_ctx()\n    svc.create({\n        \"internshipId\": str(ids[\"internship\"]), \"filingType\": \"OTHER\",",
)
replace_exact(
    "tests/test_internship_v93_batch2_remaining_first_create.py",
    "    ids = _seed(db)\n    db.commit()\n    db.close()\n\n    def _do(seq):\n        _admin_ctx()\n        svc.create({\n            \"internshipId\": str(ids[\"internship\"]), \"filingType\": \"OTHER\",",
    "    ids = _seed(db)\n    file_id = _seed_evidence_file(db)\n    db.commit()\n    db.close()\n\n    def _do(seq):\n        _admin_ctx()\n        svc.create({\n            \"internshipId\": str(ids[\"internship\"]), \"filingType\": \"OTHER\",",
)
replace_exact(
    "tests/test_internship_v93_batch2_remaining_first_create.py",
    "        \"fileIds\": [\"f-evidence-1\"],",
    "        \"fileIds\": [file_id],",
    count=2,
)

# 4) Special filing review-flow fixture gets an actual current-user-owned evidence file.
replace_exact(
    "tests/test_internship_v93_special_filing_review_flow.py",
    "    from app.models import InternshipBatch, InternshipRecord, StudentProfile\n",
    "    from app.models import InternshipBatch, InternshipRecord, StudentProfile\n    from app.models.file import FileObject\n",
)
replace_exact(
    "tests/test_internship_v93_special_filing_review_flow.py",
    "    db.add(record)\n    db.flush()\n    db.commit()\n    ids = {\"batch\": batch.id, \"internship\": record.id, \"student\": profile.id}",
    "    db.add(record)\n    db.flush()\n    evidence = FileObject(\n        tenant_id=TID, file_key=f\"test/filing/{uuid.uuid4().hex}.pdf\",\n        file_name=\"特殊备案依据.pdf\", status=\"AVAILABLE\", scan_status=\"CLEAN\",\n        biz_type=\"TEMP_PRIVATE\", biz_id=None, visibility=\"PRIVATE\",\n        owner_user_id=REQUESTER[\"userId\"],\n    )\n    db.add(evidence)\n    db.flush()\n    db.commit()\n    ids = {\"batch\": batch.id, \"internship\": record.id, \"student\": profile.id,\n           \"file\": str(evidence.id)}",
)
replace_exact(
    "tests/test_internship_v93_special_filing_review_flow.py",
    "        \"fileIds\": [\"f-evidence-1\"],",
    "        \"fileIds\": [ids[\"file\"]],",
)

# 5) Portal score appeal requires explicit internship context plus a real PUBLISHED score.
portal_anchor = "def test_my_view(client, db_mode):\n"
portal_helper = '''def _seed_score_context(no, name):
    from datetime import datetime
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipFinalScore, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2022",
            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE",
        )
        db.add(student)
        db.flush()
        batch = InternshipBatch(
            tenant_id=TID, batch_name="门户成绩申诉批次",
            batch_no=f"PORTAL-APPEAL-{uuid4().hex[:8]}", status="RUNNING", planned_count=1,
        )
        db.add(batch)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID, student_id=student.id, batch_id=batch.id,
            status="ASSESSING", risk_level="NONE",
        )
        db.add(record)
        db.flush()
        score = InternshipFinalScore(
            tenant_id=TID, internship_id=record.id, student_id=student.id,
            batch_id=batch.id, total_score=80, pass_line=60,
            is_pass=True, incomplete=False, status="PUBLISHED",
            published_by_name="学校管理员", published_at=datetime.utcnow(), version=1,
        )
        db.add(score)
        db.commit()
        return {"internship": record.id, "batch": batch.id, "score": score.id}
    finally:
        db.close()


'''
replace_exact("tests/test_portal_internship.py", portal_anchor, portal_helper + portal_anchor)
replace_exact(
    "tests/test_portal_internship.py",
    '    _seed("IN-003", "实习三")',
    '    ids = _seed_score_context("IN-003", "实习三")',
)
replace_exact(
    "tests/test_portal_internship.py",
    '                     json={"reason": "实习成绩与考勤/周报表现不符，申请复核。"}).json()',
    '                     json={"internshipId": str(ids["internship"]),\n                           "reason": "实习成绩与考勤/周报表现不符，申请复核。"}).json()',
)
replace_exact(
    "tests/test_portal_internship.py",
    '    assert client.post(f"{PORTAL}/score/appeal", headers=h, json={"reason": "短"}).json()["code"] != 0',
    '    assert client.post(f"{PORTAL}/score/appeal", headers=h,\n                       json={"internshipId": str(ids["internship"]), "reason": "短"}).json()["code"] != 0',
)

# 6) Direct tenant-bound service helper calls must have the same tenant context as HTTP middleware.
replace_exact(
    "tests/test_internship_scope.py",
    "    from app.core.security import create_access_token\n",
    "    from app.core.context import set_tenant\n    from app.core.security import create_access_token\n",
)
scope_anchor = '''    scope_other = {
        "mode": "SCOPED", "collegeNames": {"IX外院"}, "classNames": set(),
        "studentNos": set(), "advisorNames": set(), "advisorUserIds": set(),
    }

    db = get_sessionmaker()()
'''
scope_replacement = '''    scope_other = {
        "mode": "SCOPED", "collegeNames": {"IX外院"}, "classNames": set(),
        "studentNos": set(), "advisorNames": set(), "advisorUserIds": set(),
    }

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
'''
replace_exact("tests/test_internship_scope.py", scope_anchor, scope_replacement)

# 7) Enterprise evaluation is a formal assessment-stage artifact; keep the production guard.
replace_exact(
    "tests/test_internship_enterprise_eval.py",
    '                                 status="ONBOARD", risk_level="NONE", batch_id=b.id)',
    '                                 status="ASSESSING", risk_level="NONE", batch_id=b.id)',
)

print("residual internship fixture corrections applied")

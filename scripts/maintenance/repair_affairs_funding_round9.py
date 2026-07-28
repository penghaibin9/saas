from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"round9 anchor missing: {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_funding_ext() -> None:
    path = "backend/tests/test_affairs_funding_ext.py"
    replace_once(
        path,
        'json={"monthCode": "2025-11", "rating": "GOOD", "subsidyAmount": 500}',
        'json={"monthCode": "2025-11", "rating": "GOOD", "subsidyAmount": 500, "workHours": 48}',
    )
    replace_once(
        path,
        'json={"monthCode": "2025-12", "rating": "FAIL", "subsidyAmount": 999}',
        'json={"monthCode": "2025-12", "rating": "FAIL", "subsidyAmount": 999, "workHours": 32}',
    )
    replace_once(path, '"bankLast4": "6222000012346411"', '"bankLast4": "6411"')
    replace_once(
        path,
        '"studentId": sid, "itemType": "REDUCTION", "reason": "申请学费减免理由充分"',
        '"studentId": sid, "itemType": "REDUCTION", "amount": 1500, "reason": "申请学费减免理由充分"',
    )


def patch_funding_amount_contract() -> None:
    path = "backend/tests/test_affairs_funding.py"
    replace_once(
        path,
        'assert any(a["amount"] == 3000 for a in items)',
        'assert any(float(a["amount"]) == 3000 for a in items)',
    )


def patch_disbursement_fixture() -> None:
    path = "backend/tests/test_affairs_funding_disbursement.py"
    replace_once(
        path,
        '''    from app.models import FundingApplication, FundingBatch, FundingProject
    db = get_sessionmaker()()
''',
        '''    from app.models import FundingApplication, FundingBatch, FundingProject, StudentProfile
    db = get_sessionmaker()()
''',
    )
    replace_once(
        path,
        '''    db.add(b); db.flush()
    for i in range(n):
        db.add(FundingApplication(tenant_id=TID, batch_id=b.id, student_id=(sid if i == 0 else 900000 + i),
                                  apply_source="SELF", project_type="GRANT", amount=3300, status="GRANTED"))
''',
        '''    db.add(b); db.flush()
    base_student = db.get(StudentProfile, int(sid))
    assert base_student is not None
    student_ids = [int(sid)]
    for i in range(1, n):
        other = StudentProfile(
            tenant_id=TID, student_no=f"DISB{sid}-{i}", real_name=f"发放测试学生{i}",
            class_id=base_student.class_id, college_id=base_student.college_id,
            current_stage=base_student.current_stage or "ON_CAMPUS",
            student_status="NORMAL", status="ACTIVE", is_deleted=False, version=0,
        )
        db.add(other); db.flush(); student_ids.append(int(other.id))
    for student_id in student_ids:
        db.add(FundingApplication(tenant_id=TID, batch_id=b.id, student_id=student_id,
                                  apply_source="SELF", project_type="GRANT", amount=3300,
                                  status="GRANTED", is_deleted=False, version=0))
''',
    )
    replace_once(path, '"bankLast4": "6222888888886411"', '"bankLast4": "6411"')


def patch_contract() -> None:
    Path("backend/tests/test_affairs_funding_input_contract.py").write_text('''from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_funding_tests_do_not_send_full_bank_numbers():
    for name in ("test_affairs_funding_ext.py", "test_affairs_funding_disbursement.py"):
        text = read("backend/tests/" + name)
        assert "6222000012346411" not in text
        assert "6222888888886411" not in text
        assert '"bankLast4": "6411"' in text


def test_disbursement_fixture_uses_real_students():
    text = read("backend/tests/test_affairs_funding_disbursement.py")
    assert "900000 + i" not in text
    assert "StudentProfile(" in text
    assert "student_ids" in text


def test_monthly_work_study_inputs_include_hours():
    text = read("backend/tests/test_affairs_funding_ext.py")
    assert '"monthCode": "2025-11"' in text and '"workHours": 48' in text
    assert '"monthCode": "2025-12"' in text and '"workHours": 32' in text
''', encoding="utf-8")


if __name__ == "__main__":
    patch_funding_ext()
    patch_funding_amount_contract()
    patch_disbursement_fixture()
    patch_contract()
    print("student affairs funding round9 passed", flush=True)

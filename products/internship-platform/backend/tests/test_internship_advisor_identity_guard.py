"""包 8：校内导师稳定主体授权反向合同。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

TID = 1000000000000000001


def test_same_name_never_expands_advisor_scope(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    from app.modules.internship.services import internship_advisor_identity_guard as guard

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="稳定导师范围批次",
            batch_no="ADVISOR-STABLE-SCOPE",
            status="RUNNING",
            planned_count=3,
        )
        db.add(batch)
        db.flush()
        records = []
        for index, advisor_user_id in enumerate((9001, 9002, None), start=1):
            student = StudentProfile(
                tenant_id=TID,
                student_no=f"ADV-{index}",
                real_name=f"学生{index}",
                current_stage="INTERNSHIP",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            db.flush()
            record = InternshipRecord(
                tenant_id=TID,
                student_id=student.id,
                batch_id=batch.id,
                advisor_user_id=advisor_user_id,
                advisor_name="同名导师",
                status="PREPARING",
                eligibility_status="PENDING",
                destination_type="NONE",
                risk_level="NONE",
            )
            db.add(record)
            db.flush()
            records.append(record)
        db.commit()

        user = {"userId": "9001", "realName": "同名导师"}
        rows = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == TID,
            guard._advisor_condition(user),
        ).order_by(InternshipRecord.id)).all()
        assert [row.advisor_user_id for row in rows] == [9001]
        assert guard.stable_advisor_matches(records[0], user) is True
        assert guard.stable_advisor_matches(records[1], user) is False
        assert guard.stable_advisor_matches(records[2], user) is False

        # 即使姓名完全相同，换一个稳定 userId 也只能命中自己的记录。
        other = {"userId": "9002", "realName": "同名导师"}
        assert guard.stable_advisor_matches(records[0], other) is False
        assert guard.stable_advisor_matches(records[1], other) is True
    finally:
        db.close()


def test_missing_stable_user_id_fails_closed_even_when_name_matches(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    from app.modules.internship.services import internship_advisor_identity_guard as guard

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="历史姓名记录批次",
            batch_no="ADVISOR-NAME-ONLY",
            status="RUNNING",
            planned_count=1,
        )
        student = StudentProfile(
            tenant_id=TID,
            student_no="ADV-LEGACY",
            real_name="历史学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([batch, student])
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            advisor_user_id=None,
            advisor_name="历史导师",
            status="PREPARING",
            eligibility_status="PENDING",
            destination_type="NONE",
            risk_level="NONE",
        )
        db.add(record)
        db.commit()

        assert guard.stable_advisor_matches(
            record, {"userId": "12345", "realName": "历史导师"},
        ) is False
        assert guard.stable_advisor_matches(
            record, {"realName": "历史导师"},
        ) is False
    finally:
        db.close()


def test_new_assignment_rejects_name_only_lookup(db_mode):
    from app.db.session import get_sessionmaker
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_advisor_identity_guard as guard
    from app.modules.internship.services import internship_student_service

    db = get_sessionmaker()()
    try:
        with pytest.raises(AppException) as exc:
            internship_student_service._advisor(
                db, advisor_user_id=None, advisor_name="同名导师",
            )
        assert "advisorUserId" in str(exc.value)
        assert internship_student_service._advisor is guard._stable_advisor
    finally:
        db.close()


def test_non_numeric_or_missing_token_user_id_has_empty_advisor_condition(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    from app.modules.internship.services import internship_advisor_identity_guard as guard

    db = get_sessionmaker()()
    try:
        for user in ({}, {"userId": ""}, {"userId": "not-a-number", "realName": "导师"}):
            rows = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == TID,
                guard._advisor_condition(user),
            )).all()
            assert rows == []
    finally:
        db.close()

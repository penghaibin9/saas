"""教师移动端周报权威路由：同名导师仍按稳定 user_id 授权。"""
from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001


def test_versioned_weekly_review_uses_stable_advisor_identity(db_mode):
    """同名不得扩权，但真正绑定 advisor_user_id 的导师必须能从权威路由批阅。"""
    from app.api.v1.mobile_internship_weekly_versioned import teacher_weekly_review_versioned
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile, User, WeeklyReport

    db = get_sessionmaker()()
    try:
        owner = User(
            tenant_id=TID,
            login_name="same-name-intern-owner",
            real_name="同名实习导师",
            password_hash="test-only",
            user_type="TEACHER",
            status="ACTIVE",
        )
        other = User(
            tenant_id=TID,
            login_name="same-name-intern-other",
            real_name="同名实习导师",
            password_hash="test-only",
            user_type="TEACHER",
            status="ACTIVE",
        )
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="同名导师移动批阅批次",
            batch_no="MOBILE-SAME-NAME-ADVISOR",
            planned_count=1,
            status="RUNNING",
        )
        student = StudentProfile(
            tenant_id=TID,
            student_no="MOBILE-SAME-NAME-001",
            real_name="同名导师测试学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([owner, other, batch, student])
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            advisor_user_id=owner.id,
            advisor_name="同名实习导师",
            status="ONBOARD",
            eligibility_status="QUALIFIED",
            destination_type="ASSIGNED",
            risk_level="NONE",
        )
        db.add(record)
        db.flush()
        report = WeeklyReport(
            tenant_id=TID,
            internship_id=record.id,
            week_number=1,
            work_content="完成本周实习任务并记录真实过程。",
            harvest_content="完成阶段学习并整理问题。",
            word_count=24,
            report_version=1,
            submitted_at=datetime.utcnow(),
            status="PENDING_REVIEW",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        report_id = str(report.id)
        expected_version = int(report.version)
        owner_id = int(owner.id)
        other_id = int(other.id)
    finally:
        db.close()

    payload = {
        "action": "APPROVE",
        "comment": "同意本周周报",
        "expectedVersion": expected_version,
    }
    other_user = {
        "userId": f"db-{other_id}",
        "realName": "同名实习导师",
        "userType": "TEACHER",
        "currentRoleCode": "INTERN_MENTOR",
    }
    with pytest.raises(AppException) as denied:
        teacher_weekly_review_versioned(report_id, payload, user=other_user)
    assert denied.value.code == "NO_PERMISSION"

    owner_user = {
        "userId": f"db-{owner_id}",
        "realName": "同名实习导师",
        "userType": "TEACHER",
        "currentRoleCode": "INTERN_MENTOR",
    }
    ok = teacher_weekly_review_versioned(report_id, payload, user=owner_user)
    assert ok["code"] == 0
    assert ok["data"]["status"] == "APPROVED"
    assert ok["data"]["version"] == expected_version + 1

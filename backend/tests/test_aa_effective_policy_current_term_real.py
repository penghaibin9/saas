"""P0-3：无显式学期的正式成绩必须绑定唯一当前学期并冻结对应策略。"""
from datetime import datetime


def test_termless_formal_grade_binds_unique_current_term_and_policy(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AcademicGrade
    from app.models.academic_affairs_effective_grade import (
        AaEffectiveGradePolicy,
        AaEffectiveGradePolicySnapshot,
    )

    tenant_id = 1000000000000093002
    db = get_sessionmaker()()
    try:
        current = AaTerm(
            tenant_id=tenant_id,
            year_code="2032-2033",
            term_no=1,
            term_name="2032-2033学年第一学期",
            start_date=datetime(2032, 9, 1),
            is_current=True,
            status="PUBLISHED",
        )
        db.add(current)
        db.flush()
        db.add_all([
            AaEffectiveGradePolicy(
                tenant_id=tenant_id,
                policy_code="CURRENT_TERM_BASE",
                policy_version=1,
                attempt_strategy="LATEST_ATTEMPT",
                makeup_strategy="CAP_AND_OVERRIDE",
                makeup_cap=60,
                retake_strategy="REPLACE_IF_PASSED",
                recognition_priority=75,
                effective_from_term_id=None,
                status="ACTIVE",
            ),
            AaEffectiveGradePolicy(
                tenant_id=tenant_id,
                policy_code="CURRENT_TERM_POLICY",
                policy_version=2,
                attempt_strategy="HIGHEST_PASSED",
                makeup_strategy="CAP_AND_OVERRIDE",
                makeup_cap=60,
                retake_strategy="REPLACE_IF_PASSED",
                recognition_priority=75,
                effective_from_term_id=current.id,
                status="ACTIVE",
            ),
        ])
        db.flush()

        grade = AcademicGrade(
            tenant_id=tenant_id,
            acad_student_id=93002,
            course_id=93002,
            course_code="CURRENT_TERM_COURSE",
            course_version=1,
            attempt_no=1,
            course_name="当前学期策略测试课程",
            nature="REQUIRED",
            credit_value=2,
            score=80,
            pass_status="PASSED",
            exam_type="RECOGNIZED",
            source="RECOGNIZED",
            source_biz_type="RECOGNITION",
            source_biz_id=93002,
            record_status="ACTIVE",
        )
        db.add(grade)
        db.flush()

        assert grade.term == "2032-2033-1"
        assert grade.effective_policy_code == "CURRENT_TERM_POLICY"
        assert grade.effective_policy_version == 2
        assert grade.effective_attempt_strategy == "HIGHEST_PASSED"
        snapshot = db.query(AaEffectiveGradePolicySnapshot).filter(
            AaEffectiveGradePolicySnapshot.tenant_id == tenant_id,
            AaEffectiveGradePolicySnapshot.academic_grade_id == grade.id,
            AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
        ).one()
        assert snapshot.policy_code == "CURRENT_TERM_POLICY"
        assert snapshot.identity_type == "COURSE_CODE"
        db.rollback()
    finally:
        db.close()

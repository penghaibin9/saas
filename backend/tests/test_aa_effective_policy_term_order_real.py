"""P0-3：策略生效必须按学期业务时间，不能依赖数据库ID大小。"""
from datetime import datetime


def test_effective_policy_uses_term_chronology_not_insert_id(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy
    from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as policy

    tenant_id = 1000000000000093001
    db = get_sessionmaker()()
    try:
        # 故意先插入未来学期，再插入较早学期：未来学期ID更小。
        future = AaTerm(
            tenant_id=tenant_id,
            year_code="2031-2032",
            term_no=1,
            term_name="2031-2032学年第一学期",
            start_date=datetime(2031, 9, 1),
            status="PUBLISHED",
        )
        db.add(future)
        db.flush()
        earlier = AaTerm(
            tenant_id=tenant_id,
            year_code="2030-2031",
            term_no=2,
            term_name="2030-2031学年第二学期",
            start_date=datetime(2031, 2, 20),
            status="PUBLISHED",
        )
        db.add(earlier)
        db.flush()
        assert int(future.id) < int(earlier.id)

        base = AaEffectiveGradePolicy(
            tenant_id=tenant_id,
            policy_code="TERM_ORDER_BASE",
            policy_version=1,
            attempt_strategy="LATEST_ATTEMPT",
            makeup_strategy="CAP_AND_OVERRIDE",
            makeup_cap=60,
            retake_strategy="REPLACE_IF_PASSED",
            recognition_priority=75,
            effective_from_term_id=None,
            status="ACTIVE",
        )
        future_policy = AaEffectiveGradePolicy(
            tenant_id=tenant_id,
            policy_code="TERM_ORDER_FUTURE",
            policy_version=2,
            attempt_strategy="HIGHEST_PASSED",
            makeup_strategy="CAP_AND_OVERRIDE",
            makeup_cap=60,
            retake_strategy="REPLACE_IF_PASSED",
            recognition_priority=75,
            effective_from_term_id=future.id,
            status="ACTIVE",
        )
        db.add_all([base, future_policy])
        db.commit()

        monkeypatch.setattr(policy, "_tid", lambda: tenant_id)
        assert policy.resolve_active_policy(db, earlier.id).policy_code == "TERM_ORDER_BASE"
        assert policy.resolve_active_policy(db, future.id).policy_code == "TERM_ORDER_FUTURE"
    finally:
        db.close()

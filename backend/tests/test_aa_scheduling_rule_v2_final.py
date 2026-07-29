"""V2-03 排课规则最终安全层回归。"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

TID = 1000000000000000001


def _rule(row_id, key, value, *, term_id=11, batch_id=None):
    return SimpleNamespace(
        id=row_id,
        term_id=term_id,
        batch_id=batch_id,
        rule_key=key,
        rule_value_json=json.dumps(value, ensure_ascii=False),
    )


def test_final_facade_is_injected_into_engine_and_public_scheduling_service():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_autoschedule_service as auto
    from app.modules.academic_affairs.services import academic_affairs_scheduling_service as scheduling

    final = services.academic_affairs_scheduling_rule_final_facade
    assert auto._load_params is final.load_effective_params
    assert scheduling.save_rule is final.save_rule
    assert scheduling.delete_rule is final.delete_rule
    assert scheduling.submit_availability is final.submit_availability
    assert scheduling.list_availability is final.list_availability
    assert scheduling.review_availability is final.review_availability


def test_batch_rule_overrides_term_rule_and_defaults_use_real_slots():
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    rows = [
        _rule(1, "AUTO_WEEKDAYS", [1, 2], term_id=11),
        _rule(2, "AUTO_WEEKDAYS", [3], term_id=11, batch_id=22),
        _rule(3, "AUTO_TEACHER_MAX_PER_DAY", 5, term_id=11),
    ]
    params = final._merge_rule_rows(
        rows,
        term_id=11,
        batch_id=22,
        teaching_weeks=20,
        enabled_slots=[1, 2, 4],
    )

    assert params["weekdays"] == [3]
    assert params["slots"] == [1, 2, 4]
    assert params["teacherMaxPerDay"] == 5
    assert params["startWeek"] == 1 and params["endWeek"] == 18


def test_duplicate_rule_fails_closed_instead_of_last_write_wins():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    rows = [
        _rule(1, "AUTO_WEEKDAYS", [1, 2], term_id=11),
        _rule(2, "AUTO_WEEKDAYS", [3, 4], term_id=11),
    ]
    with pytest.raises(AppException) as exc:
        final._merge_rule_rows(
            rows,
            term_id=11,
            batch_id=22,
            teaching_weeks=18,
            enabled_slots=[1, 2],
        )
    assert "重复记录" in exc.value.message


def test_corrupt_or_unknown_rule_fails_closed():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    corrupt = SimpleNamespace(
        id=7, term_id=11, batch_id=None,
        rule_key="AUTO_WEEKDAYS", rule_value_json="{broken",
    )
    with pytest.raises(AppException) as corrupt_exc:
        final._merge_rule_rows(
            [corrupt], term_id=11, batch_id=22,
            teaching_weeks=18, enabled_slots=[1, 2],
        )
    assert "配置损坏" in corrupt_exc.value.message

    unknown = _rule(8, "LEGACY_MAGIC_RULE", True, term_id=11)
    with pytest.raises(AppException) as unknown_exc:
        final._merge_rule_rows(
            [unknown], term_id=11, batch_id=22,
            teaching_weeks=18, enabled_slots=[1, 2],
        )
    assert "不支持" in unknown_exc.value.message


def test_whole_day_forbidden_dominates_specific_slots():
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    value = final._normalize_for_engine(
        "AUTO_FORBIDDEN",
        [
            {"weekday": 2, "slotNo": 1},
            {"weekday": 2},
            {"weekday": 3, "slotNo": 2},
        ],
        teaching_weeks=18,
        enabled_slots=[1, 2, 3],
    )
    assert value == [{"weekday": 2}, {"weekday": 3, "slotNo": 2}]


def test_auto_slots_fail_closed_without_real_enabled_timeslots():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    with pytest.raises(AppException) as exc:
        final._normalize_for_engine(
            "AUTO_SLOTS", [1, 2], teaching_weeks=18, enabled_slots=[],
        )
    assert "作息节次" in exc.value.message


def test_mysql_rule_save_and_engine_read_share_one_governed_fact(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaTerm, AaTimeSlot
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    user = {
        "userId": "u_school_admin01",
        "loginName": "school_admin01",
        "realName": "学校管理员",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TID),
    }
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    try:
        db = get_sessionmaker()()
        term = AaTerm(
            tenant_id=TID,
            year_code="2098-2099",
            term_no=1,
            term_name="V2-03测试学期",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaScheduleBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="V2-03自动排课测试批次",
            status="DRAFT",
        )
        db.add(batch)
        db.add_all([
            AaTimeSlot(tenant_id=TID, slot_no=1, slot_name="第1节", enabled=True, status="ENABLED"),
            AaTimeSlot(tenant_id=TID, slot_no=3, slot_name="第3节", enabled=True, status="ENABLED"),
        ])
        db.commit()
        term_id, batch_id = term.id, batch.id
        db.close()

        final.save_rule(user, SimpleNamespace(
            ruleKey="AUTO_WEEKDAYS", termId=str(term_id), batchId=None,
            ruleValue=[1, 2], remark="学期默认",
        ))
        final.save_rule(user, SimpleNamespace(
            ruleKey="AUTO_WEEKDAYS", termId=str(term_id), batchId=str(batch_id),
            ruleValue=[4], remark="批次覆盖",
        ))

        db = get_sessionmaker()()
        params = final.load_effective_params(db, term_id, batch_id)
        db.close()
        assert params["weekdays"] == [4]
        assert params["slots"] == [1, 3]
    finally:
        set_current_user(None)
        set_tenant(None)


def test_mysql_availability_requires_real_term_and_enabled_slot(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTimeSlot
    from app.modules.academic_affairs.services import academic_affairs_scheduling_rule_final_facade as final

    user = {
        "userId": "u_teacher_v203",
        "loginName": "teacher_v203",
        "realName": "排课测试教师",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "tenantId": str(TID),
    }
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    try:
        db = get_sessionmaker()()
        term = AaTerm(
            tenant_id=TID,
            year_code="2097-2098",
            term_no=2,
            term_name="不可排时间测试学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        db.add(AaTimeSlot(
            tenant_id=TID, slot_no=2, slot_name="第2节",
            enabled=True, status="ENABLED",
        ))
        db.commit()
        term_id = term.id
        db.close()

        created = final.submit_availability(user, SimpleNamespace(
            termId=str(term_id), weekday=1, slotNo=2, reason="固定教研活动",
        ))
        assert created["status"] == "PENDING"

        with pytest.raises(AppException) as exc:
            final.submit_availability(user, SimpleNamespace(
                termId=str(term_id), weekday=1, slotNo=9, reason="不存在节次",
            ))
        assert "未在学校作息中启用" in exc.value.message
    finally:
        set_current_user(None)
        set_tenant(None)

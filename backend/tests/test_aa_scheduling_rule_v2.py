"""V2-03 排课规则中心业务化回归。"""
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException


EXPECTED_KEYS = {
    "AUTO_DEFAULT_WEEKS",
    "AUTO_WEEKDAYS",
    "AUTO_SLOTS",
    "AUTO_FORBIDDEN",
    "AUTO_CLASS_MAX_PER_DAY",
    "AUTO_TEACHER_MAX_PER_DAY",
    "AUTO_ROOM_TYPE_MATCH",
    "AUTO_CAPACITY_CHECK",
    "AUTO_RESPECT_TEACHER_AVAIL",
}


def test_rule_catalog_matches_real_auto_schedule_consumers_only():
    from app.modules.academic_affairs.services import academic_affairs_autoschedule_service as auto
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import RULE_CATALOG

    assert set(RULE_CATALOG) == EXPECTED_KEYS
    assert set(auto.RULE_KEYS) == EXPECTED_KEYS
    assert all(item["label"] and item["group"] and item["control"] for item in RULE_CATALOG.values())
    assert not any("连排" in item["label"] or "跨校区" in item["label"] for item in RULE_CATALOG.values())


def test_rule_catalog_returns_business_metadata_not_raw_description_only():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import rule_catalog

    result = rule_catalog({})
    by_key = {item["ruleKey"]: item for item in result["items"]}

    assert len(by_key) == 9
    assert by_key["AUTO_DEFAULT_WEEKS"]["control"] == "WEEK_RANGE"
    assert by_key["AUTO_WEEKDAYS"]["options"][0] == {"value": 1, "label": "周一"}
    assert by_key["AUTO_CLASS_MAX_PER_DAY"]["unit"] == "节"
    assert by_key["AUTO_CAPACITY_CHECK"]["defaultValue"] is True


def test_week_range_is_normalized_and_limited_by_term_weeks():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import normalize_rule_value

    assert normalize_rule_value(
        "AUTO_DEFAULT_WEEKS", {"startWeek": 2, "endWeek": 16}, teaching_weeks=18,
    ) == {"startWeek": 2, "endWeek": 16}

    with pytest.raises(AppException):
        normalize_rule_value("AUTO_DEFAULT_WEEKS", {"startWeek": 8, "endWeek": 4})
    with pytest.raises(AppException):
        normalize_rule_value("AUTO_DEFAULT_WEEKS", {"startWeek": 1, "endWeek": 19}, teaching_weeks=18)


def test_weekdays_and_slots_are_sorted_deduplicated_and_fail_closed():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import normalize_rule_value

    assert normalize_rule_value("AUTO_WEEKDAYS", [5, 1, 3, 3]) == [1, 3, 5]
    assert normalize_rule_value("AUTO_SLOTS", [4, 2, 2], enabled_slots=[1, 2, 3, 4]) == [2, 4]

    with pytest.raises(AppException):
        normalize_rule_value("AUTO_WEEKDAYS", [])
    with pytest.raises(AppException):
        normalize_rule_value("AUTO_WEEKDAYS", [0, 1])
    with pytest.raises(AppException):
        normalize_rule_value("AUTO_SLOTS", [9], enabled_slots=[1, 2, 3, 4])


def test_forbidden_grid_supports_whole_day_and_deduplicates():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import normalize_rule_value

    result = normalize_rule_value(
        "AUTO_FORBIDDEN",
        [
            {"weekday": 3, "slotNo": 6},
            {"weekday": 3, "slotNo": 6},
            {"weekday": 5},
            {"weekday": 1, "slotNo": 2},
        ],
        enabled_slots=[1, 2, 3, 4, 5, 6, 7, 8],
    )
    assert result == [
        {"weekday": 1, "slotNo": 2},
        {"weekday": 3, "slotNo": 6},
        {"weekday": 5},
    ]

    with pytest.raises(AppException):
        normalize_rule_value("AUTO_FORBIDDEN", [{"weekday": 2, "slotNo": 12}], enabled_slots=[1, 2, 3])


def test_integer_boolean_and_unknown_rules_are_strict():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import normalize_rule_value

    assert normalize_rule_value("AUTO_TEACHER_MAX_PER_DAY", 6) == 6
    assert normalize_rule_value("AUTO_ROOM_TYPE_MATCH", False) is False

    with pytest.raises(AppException):
        normalize_rule_value("AUTO_TEACHER_MAX_PER_DAY", True)
    with pytest.raises(AppException):
        normalize_rule_value("AUTO_ROOM_TYPE_MATCH", "true")
    with pytest.raises(AppException):
        normalize_rule_value("AUTO_CONTINUOUS_SLOTS", 2)


def test_legacy_bad_json_is_visible_as_invalid_instead_of_crashing_list():
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_policy import _rule_dto

    row = SimpleNamespace(
        id=7,
        term_id=2,
        batch_id=None,
        rule_key="AUTO_WEEKDAYS",
        rule_value_json="{broken-json",
        remark=None,
        status="ENABLED",
    )
    result = _rule_dto(row)

    assert result["ruleId"] == "7"
    assert result["ruleLabel"] == "允许排课星期"
    assert result["invalidValue"] is True
    assert "重新保存" in result["validationMessage"]
    assert result["valueSummary"] == "配置异常"


def test_legacy_dict_transport_and_real_scalar_route_body_are_both_supported():
    from app.modules.academic_affairs.routers.scheduling_rule_router import SchedulingRuleBody
    from app.modules.academic_affairs.services.academic_affairs_scheduling_rule_transport import (
        _RuleBodyProxy, unwrap_transport_value,
    )

    scalar_body = SchedulingRuleBody(ruleKey="AUTO_WEEKDAYS", termId=1, ruleValue=[1, 2, 3])
    boolean_body = SchedulingRuleBody(ruleKey="AUTO_CAPACITY_CHECK", termId=1, ruleValue=True)
    wrapped = SimpleNamespace(ruleValue={"value": [1, 2, 3]}, ruleKey="AUTO_WEEKDAYS", termId=1)

    assert scalar_body.ruleValue == [1, 2, 3]
    assert boolean_body.ruleValue is True
    assert unwrap_transport_value({"value": 6}) == 6
    assert _RuleBodyProxy(wrapped).ruleValue == [1, 2, 3]


def test_services_package_loads_final_rule_policy_before_router_consumers():
    from app.modules.academic_affairs.services import academic_affairs_autoschedule_service as auto
    from app.modules.academic_affairs.services import academic_affairs_scheduling_service as scheduling

    assert auto.rule_catalog.__module__.endswith("academic_affairs_scheduling_rule_policy")
    assert scheduling._rule_dto.__module__.endswith("academic_affairs_scheduling_rule_policy")
    assert scheduling.delete_rule.__module__.endswith("academic_affairs_scheduling_rule_policy")
    assert scheduling.save_rule.__module__.endswith("academic_affairs_scheduling_rule_transport")


def test_aggregated_router_contains_one_correct_rule_route_per_method():
    from app.modules.academic_affairs.routers import academic_affairs

    routes = academic_affairs.router.routes

    def count(path, method):
        return sum(
            1 for route in routes
            if getattr(route, "path", "") == path and method in set(getattr(route, "methods", set()) or set())
        )

    assert count("/academic-affairs/scheduling/rules", "GET") == 1
    assert count("/academic-affairs/scheduling/rules", "PUT") == 1
    assert count("/academic-affairs/scheduling/rules/{rule_id}", "DELETE") == 1
    assert count("/academic-affairs/scheduling/rules/{ruleId}", "DELETE") == 0

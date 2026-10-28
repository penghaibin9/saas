"""岗位实习批次参与人 API schema 契约回归。"""


def test_preview_rule_can_round_trip_into_freeze_schema():
    """公共 resolver 规范化出的整数 ID 规则必须能原样提交 freeze。"""
    from app.modules.internship.routers.internship_participant import FreezeBody
    from app.services.student_scope_resolver import ScopeRule

    preview_rule = ScopeRule(
        college_ids={11},
        major_ids={22},
        class_ids={33},
        student_ids={44},
        exclude_student_ids={55},
    ).to_dict()

    body = FreezeBody.model_validate({"rule": preview_rule})
    dumped = body.rule.model_dump()

    assert dumped["collegeIds"] == [11]
    assert dumped["majorIds"] == [22]
    assert dumped["classIds"] == [33]
    assert dumped["studentIds"] == [44]
    assert dumped["excludeStudentIds"] == [55]


def test_freeze_schema_keeps_legacy_string_ids_compatible():
    """原有前端/历史调用传字符串 ID 仍必须兼容。"""
    from app.modules.internship.routers.internship_participant import FreezeBody

    body = FreezeBody.model_validate({"rule": {"studentIds": ["44"]}})
    assert body.rule.model_dump()["studentIds"] == ["44"]

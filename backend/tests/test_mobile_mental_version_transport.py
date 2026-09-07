import pytest

from app.api.v1 import mobile
from app.services import _mobile_teacher_service_impl as teacher
from app.services import affairs_mental_service as mental


@pytest.mark.parametrize(
    "route_name,service_name,field",
    [
        ("teacher_mental_follow", "follow_referral", "content"),
        ("teacher_mental_escalate", "escalate_crisis", "content"),
        ("teacher_mental_close", "close_referral", "conclusion"),
    ],
)
@pytest.mark.parametrize("version", [None, 0, 7])
def test_mobile_mental_routes_forward_exact_version(
    monkeypatch, route_name, service_name, field, version
):
    seen = []
    user = {"userType": "TEACHER", "realName": "联调心理老师"}
    monkeypatch.setattr(teacher, "_require_teacher", lambda value: value)

    def authority(actor, referral_id, text, expected_version=None):
        seen.append((actor, referral_id, text, expected_version))
        return {"referralId": referral_id, "version": 8}

    monkeypatch.setattr(mental, service_name, authority)
    getattr(mobile, route_name)(
        "9007199254740993",
        body={field: "已完成本次心理跟进记录", "version": version},
        user=user,
    )

    assert seen == [
        (user, "9007199254740993", "已完成本次心理跟进记录", version)
    ]

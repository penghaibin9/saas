"""教师移动端处分申诉变更字段透传合同。"""


def test_mobile_discipline_revision_forwards_target_type(monkeypatch):
    from app.api.v1 import affairs_appeal_mobile as mobile
    from app.services import affairs_discipline_service as discipline

    captured = {}

    def fake_review(appeal_id, body, user):
        captured.update({
            "appealId": appeal_id,
            "result": body.result,
            "opinion": body.opinion,
            "version": body.version,
            "revisedDiscType": body.revisedDiscType,
            "user": user,
        })
        return {"appealId": str(appeal_id), "status": "REVISED"}

    monkeypatch.setattr(mobile, "_require_any", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(discipline, "review_appeal", fake_review)

    response = mobile.appeal_review(
        "DISCIPLINE_APPEAL",
        91,
        {
            "result": "REVISED",
            "opinion": "核验材料后变更处分类型",
            "version": 4,
            "revisedDiscType": "DEMERIT",
        },
        user={"userId": "teacher-1"},
    )

    assert response["code"] == 0
    assert captured == {
        "appealId": 91,
        "result": "REVISED",
        "opinion": "核验材料后变更处分类型",
        "version": 4,
        "revisedDiscType": "DEMERIT",
        "user": {"userId": "teacher-1"},
    }

from app.services import affairs_four_end_contract as contract
from app.services import mobile_affairs_service as aff


def test_four_end_patch_preserves_aid_draft_resubmit_actions(monkeypatch):
    """核心困难认定状态机退回后落 DRAFT，四端加固层不得把学生重提动作抹掉。"""
    original = lambda _user: {
        "currentLevel": None,
        "items": [
            {
                "applyId": "draft-contract-test",
                "status": "DRAFT",
                "statusLabel": "已退回待修改",
                "returnReason": "请补充材料",
                "allowedActions": ["EDIT_RETURNED", "RESUBMIT"],
                "hasPendingObjection": False,
            }
        ],
    }
    monkeypatch.setattr(aff, "aid_my", original)

    contract._patch_student_views()
    item = aff.aid_my({})["items"][0]

    assert item["status"] == "DRAFT"
    assert item["allowedActions"] == ["EDIT_RETURNED", "RESUBMIT"]

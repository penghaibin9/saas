"""Real account control: school visibility is not permission to approve another person's task."""
from test_affairs_leave import _apply, _leave_action, _leave_detail, _real_hdr, _seed


def test_real_counselor_and_college_complete_their_own_leave_nodes(client, db_mode):
    ids = _seed(db_mode)
    school = _real_hdr(client, "school_admin01")
    counselor = _real_hdr(client, "counselor01")
    college = _real_hdr(client, "leave_college01")
    response = _apply(client, school, ids["sa"], "2026-03-01", "2026-03-06")
    assert response.status_code == 200, response.text
    record = response.json()["data"]
    denied = _leave_action(client, school, record["id"], "approve")
    assert denied.status_code == 403, denied.text
    assert _leave_detail(client, counselor, record["id"])["version"] == record["version"]
    first = _leave_action(client, counselor, record["id"], "approve")
    assert first.status_code == 200, first.text
    assert first.json()["data"]["affairsStatus"] == "COLLEGE_REVIEW"
    second = _leave_action(client, college, record["id"], "approve")
    assert second.status_code == 200, second.text
    assert second.json()["data"]["affairsStatus"] == "APPROVED"


def test_real_counselor_can_confirm_cancel_but_school_admin_cannot_take_over(client, db_mode):
    ids = _seed(db_mode)
    school = _real_hdr(client, "school_admin01")
    counselor = _real_hdr(client, "counselor01")
    record = _apply(client, school, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]
    approved = _leave_action(client, counselor, record["id"], "approve")
    assert approved.status_code == 200, approved.text
    submitted = _leave_action(client, school, record["id"], "cancel", {"proofNote": "已联系确认返校"})
    assert submitted.status_code == 200, submitted.text
    denied = _leave_action(client, school, record["id"], "cancel-confirm", {"note": "已经核实返校情况"})
    assert denied.status_code == 403, denied.text
    confirmed = _leave_action(client, counselor, record["id"], "cancel-confirm", {"note": "已经核实返校情况"})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["affairsStatus"] == "CLOSED"

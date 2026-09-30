"""秘书答辩确认页：评分列表附带答辩组全部评委及各自评分状态，能看到“还差谁未评”。

MySQL 真库（db_mode）。口径与“确认本轮成绩”相同：只按稳定评委身份判断是否已评。
"""
from __future__ import annotations

from test_graduation_defense_grade import GD_SCORE, _gd_student, _judge_headers


def _panel(graduation_client, h, gid):
    body = graduation_client.get(GD_SCORE, headers=h, params={"gdStudentId": gid}).json()
    assert body["code"] == 0, body
    return body["data"]["panel"]


def test_panel_lists_unscored_judges_until_all_scored_then_confirmed(graduation_client, auth_headers, db_mode):
    h = auth_headers
    no = "DSP01"
    gid = _gd_student(graduation_client, h, no, "评分进度生")
    mid_a = graduation_client._defense_judges[(str(gid), "评委甲")]
    mid_b = graduation_client._defense_judges[(str(gid), "评委乙")]

    # 还没人评分：两位都在“未评”名单里，主席排第一。
    panel = _panel(graduation_client, h, gid)
    assert panel["roundNo"] == 1
    assert panel["total"] == 2 and panel["scoredCount"] == 0
    assert [m["name"] for m in panel["members"]] == ["评委甲", "评委乙"]
    assert panel["members"][0]["role"] == "主席"
    assert panel["pendingNames"] == ["评委甲", "评委乙"]
    assert all(m["status"] == "NOT_SCORED" for m in panel["members"])

    # 评委甲评分后，只剩评委乙；评分列表本身仍只有已评的那条。
    r = graduation_client.post(f"{GD_SCORE}/entry", headers=_judge_headers(no, "评委甲"), json={
        "gdStudentId": gid, "judgeName": "评委甲", "judgeMentorId": mid_a, "score": 86})
    assert r.json()["code"] == 0, r.json()
    body = graduation_client.get(GD_SCORE, headers=h, params={"gdStudentId": gid}).json()["data"]
    assert len(body["items"]) == 1
    panel = body["panel"]
    assert panel["pendingNames"] == ["评委乙"]
    assert "还差 1 位评委未评分：评委乙" == panel["hint"]
    assert panel["members"][0]["status"] == "SCORED" and panel["members"][0]["score"] == 86

    # 此时秘书确认会被拦，拦截信息里的名单与进度一致。
    blocked = graduation_client.post(f"{GD_SCORE}/{gid}/confirm", headers=h).json()
    assert blocked["code"] != 0
    assert "评委乙" in blocked["message"]

    # 评委乙缺席也算完成；全部完成后可确认，确认后状态变为已确认。
    r = graduation_client.post(f"{GD_SCORE}/entry", headers=_judge_headers(no, "评委乙"), json={
        "gdStudentId": gid, "judgeName": "评委乙", "judgeMentorId": mid_b, "absent": True, "absentReason": "临时公务"})
    assert r.json()["code"] == 0, r.json()
    panel = _panel(graduation_client, h, gid)
    assert panel["pendingNames"] == []
    assert panel["members"][1]["status"] == "ABSENT"
    assert panel["hint"] == "全部评委已评分，可以确认本轮成绩"

    assert graduation_client.post(f"{GD_SCORE}/{gid}/confirm", headers=h).json()["code"] == 0
    panel = _panel(graduation_client, h, gid)
    assert all(m["status"] == "CONFIRMED" for m in panel["members"])
    assert panel["hint"] == "本轮成绩已确认"


def test_panel_is_absent_without_student_filter_and_hidden_out_of_scope(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "DSP02", "范围外生")
    # 不带 gdStudentId 的普通列表不附带 panel。
    body = graduation_client.get(GD_SCORE, headers=h).json()
    assert body["code"] == 0 and "panel" not in body["data"]

    # 与该生无关的评委看不到答辩组名单（不在数据范围时 panel 为空或请求被拒）。
    from app.core.security import create_access_token
    outsider = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-outsider", "realName": "无关评委", "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "GD_DEFENSE_EXPERT", "clientType": "PC", "loginName": "outsider",
    })}
    resp = graduation_client.get(GD_SCORE, headers=outsider, params={"gdStudentId": gid}).json()
    assert resp["code"] != 0 or not resp["data"].get("panel")

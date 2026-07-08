"""毕业设计中心 · 答辩评分 + 成绩评定测试：多评委录入→确认→二次答辩 + 核算→复核→发布→撤回。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_SCORE = "/api/v1/graduation/gd-defense-scores"
GD_GRADE = "/api/v1/graduation/gd-grades"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_defense_score_entry_absent_and_confirm(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "DS001", "答辩测试生")

    bad = client.post(f"{GD_SCORE}/entry", headers=h, json={"gdStudentId": gid, "judgeName": "评委甲"})
    assert bad.json()["code"] != 0  # 未缺席须评分

    e1 = client.post(f"{GD_SCORE}/entry", headers=h, json={"gdStudentId": gid, "judgeName": "评委甲", "score": 88})
    assert e1.json()["data"]["status"] == "SCORED"
    e2 = client.post(f"{GD_SCORE}/entry", headers=h, json={
        "gdStudentId": gid, "judgeName": "评委乙", "absent": True, "absentReason": "临时公务"})
    assert e2.json()["data"]["absent"] is True

    confirm = client.post(f"{GD_SCORE}/{gid}/confirm", headers=h)
    assert confirm.json()["data"]["judgeCount"] == 2
    assert confirm.json()["data"]["average"] == 88

    lst = client.get(GD_SCORE, headers=h, params={"gdStudentId": gid}).json()["data"]["items"]
    assert all(x["status"] == "CONFIRMED" for x in lst)

    dup_update = client.post(f"{GD_SCORE}/entry", headers=h, json={"gdStudentId": gid, "judgeName": "评委甲", "score": 90})
    assert dup_update.json()["code"] != 0  # 已确认不可修改

    stats = client.get(f"{GD_SCORE}/stats", headers=h).json()["data"]
    assert stats["confirmed"] >= 2


def test_second_defense_requires_first_round_confirmed(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "DS101", "二辩测试生")
    client.post(f"{GD_SCORE}/entry", headers=h, json={"gdStudentId": gid, "judgeName": "评委甲", "score": 55})

    too_early = client.post(f"{GD_SCORE}/{gid}/second-defense", headers=h, json={"reason": "分数不理想需二辩"})
    assert too_early.json()["code"] != 0

    client.post(f"{GD_SCORE}/{gid}/confirm", headers=h)
    ok = client.post(f"{GD_SCORE}/{gid}/second-defense", headers=h, json={"reason": "分数不理想需二辩"})
    assert ok.json()["data"]["newRound"] == 2


def test_grade_calculate_review_publish_withdraw(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "GR001", "成绩测试生")

    detail = client.get(f"{GD_GRADE}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "DRAFT"

    calc = client.post(f"{GD_GRADE}/{gid}/calculate", headers=h, json={
        "advisorScore": 95, "reviewerScore": 90, "defenseScore": 90})
    body = calc.json()["data"]
    assert body["status"] == "CALCULATED"
    assert body["totalScore"] == round(95 * 0.4 + 90 * 0.3 + 90 * 0.3)
    assert body["gradeLevel"] == "优秀"

    publish_before_review = client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert publish_before_review.json()["code"] != 0  # 未复核不可发布

    return_short = client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "RETURN", "comment": "x"})
    assert return_short.json()["code"] != 0
    ret = client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "RETURN", "comment": "答辩分需核实原始记录"})
    assert ret.json()["data"]["status"] == "DRAFT"

    client.post(f"{GD_GRADE}/{gid}/calculate", headers=h, json={"advisorScore": 90, "defenseScore": 88})
    approve = client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "APPROVE"})
    assert approve.json()["data"]["reviewedBy"]

    publish = client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert publish.json()["data"]["status"] == "PUBLISHED"

    withdraw_short = client.post(f"{GD_GRADE}/{gid}/withdraw", headers=h, json={"reason": "x"})
    assert withdraw_short.json()["code"] != 0
    withdraw = client.post(f"{GD_GRADE}/{gid}/withdraw", headers=h, json={"reason": "发现导师分录入错误需重新核算"})
    assert withdraw.json()["data"]["status"] == "WITHDRAWN"

    stats = client.get(f"{GD_GRADE}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

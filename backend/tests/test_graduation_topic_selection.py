"""毕业设计中心 · 选题管理 Batch 3 闭环测试：
容量冲突人工复核（过热题目派生）+ 选题统计 + 退选（管理端代退）+ 选题归档（仅关闭/匹配可归档）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
RD = "/api/v1/graduation/gd-topic-rounds"


def _student(graduation_client, h, no, name):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    graduation_client.post(f"{GD_STU}/{gid}/eligibility", headers=h, json={
        "status": "QUALIFIED", "reason": "E2E测试认定合格",
    })
    return gid


def _pool_topic(graduation_client, h, title, capacity):
    tid = graduation_client.post(GD_TOPIC, headers=h, json={
        "title": title, "sourceType": "TEACHER", "advisorName": "选题李老师",
        "capacity": capacity, "submitReview": True}).json()["data"]["id"]
    graduation_client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    return tid


def _open_round(graduation_client, h, name):
    rid = graduation_client.post(RD, headers=h, json={"roundName": name, "roundNo": 1, "maxChoices": 3}).json()["data"]["id"]
    graduation_client.post(f"{RD}/{rid}/open", headers=h)
    return rid


def test_capacity_conflict_and_stats(graduation_client, auth_headers, db_mode):
    h = auth_headers
    rid = _open_round(graduation_client, h, "冲突轮次")
    tid = _pool_topic(graduation_client, h, "过热课题（容量1）", 1)
    g1 = _student(graduation_client, h, "TS001", "选题甲")
    g2 = _student(graduation_client, h, "TS002", "选题乙")
    graduation_client.post(f"{RD}/{rid}/choices", headers=h, json={"gdStudentId": g1, "choices": [{"topicId": tid, "choiceOrder": 1}]})
    graduation_client.post(f"{RD}/{rid}/choices", headers=h, json={"gdStudentId": g2, "choices": [{"topicId": tid, "choiceOrder": 1}]})

    conflicts = graduation_client.get(f"{RD}/{rid}/capacity-conflicts", headers=h).json()["data"]["items"]
    hot = next(c for c in conflicts if c["topicId"] == str(tid))
    assert hot["pendingCount"] == 2 and hot["remaining"] == 1 and hot["overBy"] == 1
    assert len(hot["students"]) == 2

    stats = graduation_client.get(f"{RD}/{rid}/stats", headers=h).json()["data"]
    assert stats["studentCount"] == 2
    assert stats["conflictTopicCount"] >= 1
    assert stats["totalChoices"] == 2


def test_withdraw_choices(graduation_client, auth_headers, db_mode):
    h = auth_headers
    rid = _open_round(graduation_client, h, "退选轮次")
    tid = _pool_topic(graduation_client, h, "普通课题", 5)
    g1 = _student(graduation_client, h, "TS101", "退选甲")
    graduation_client.post(f"{RD}/{rid}/choices", headers=h, json={"gdStudentId": g1, "choices": [{"topicId": tid, "choiceOrder": 1}]})

    before = graduation_client.get(f"{RD}/{rid}/choices", headers=h, params={"gdStudentId": g1}).json()["data"]
    assert len(before) == 1

    wd = graduation_client.post(f"{RD}/{rid}/choices/withdraw", headers=h, params={"gdStudentId": g1})
    assert wd.json()["code"] == 0 and wd.json()["data"]["withdrawn"] == 1

    after = graduation_client.get(f"{RD}/{rid}/choices", headers=h, params={"gdStudentId": g1}).json()["data"]
    assert len(after) == 0

    # 无志愿再退选 → 报错
    again = graduation_client.post(f"{RD}/{rid}/choices/withdraw", headers=h, params={"gdStudentId": g1})
    assert again.json()["code"] != 0


def test_archive_round(graduation_client, auth_headers, db_mode):
    h = auth_headers
    rid = _open_round(graduation_client, h, "归档轮次")

    # OPEN 不可直接归档
    early = graduation_client.post(f"{RD}/{rid}/archive", headers=h)
    assert early.json()["code"] != 0

    graduation_client.post(f"{RD}/{rid}/close", headers=h)
    ok = graduation_client.post(f"{RD}/{rid}/archive", headers=h)
    assert ok.json()["code"] == 0 and ok.json()["data"]["status"] == "ARCHIVED"

"""毕业设计中心 · 选题轮次/志愿测试。"""
from __future__ import annotations

GD_ROUND = "/api/v1/graduation/gd-topic-rounds"
GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_BATCH = "/api/v1/graduation/batches"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _batch(client, h, no="GD-RND-B1"):
    return client.post(GD_BATCH, headers=h, json={
        "batchName": "2026届毕设", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _approved_topic(client, h, title="轮次测试题"):
    r = client.post(GD_TOPIC, headers=h, json={
        "title": title, "sourceType": "TEACHER", "advisorName": "王老师", "capacity": 2, "submitReview": True
    }).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    return tid


def _gd_student(client, h, no="S-GD-RND-01"):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": "轮次测"}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_round_create_open_submit_match(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-RND-F1")
    tid = _approved_topic(client, auth_headers)
    gid = _gd_student(client, auth_headers)
    cr = client.post(GD_ROUND, headers=auth_headers, json={
        "roundName": "第一轮选题", "batchId": bid, "maxChoices": 2
    }).json()
    assert cr["code"] == 0
    rid = cr["data"]["id"]
    assert client.post(f"{GD_ROUND}/{rid}/open", headers=auth_headers).json()["data"]["status"] == "OPEN"
    sub = client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers, json={
        "gdStudentId": gid, "choices": [{"topicId": tid, "choiceOrder": 1}]
    }).json()
    assert sub["code"] == 0
    ch = client.get(f"{GD_ROUND}/{rid}/choices", headers=auth_headers).json()
    assert len(ch["data"]) == 1
    m = client.post(f"{GD_ROUND}/{rid}/match", headers=auth_headers).json()
    assert m["code"] == 0 and m["data"]["matched"] == 1
    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()
    assert stu["data"]["topicId"] == tid


def test_submit_requires_open_round(client, auth_headers, db_mode):
    cr = client.post(GD_ROUND, headers=auth_headers, json={"roundName": "草稿轮次"}).json()
    rid = cr["data"]["id"]
    gid = _gd_student(client, auth_headers, "S-GD-RND-02")
    tid = _approved_topic(client, auth_headers, "题B")
    bad = client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers, json={
        "gdStudentId": gid, "choices": [{"topicId": tid, "choiceOrder": 1}]
    }).json()
    assert bad["code"] != 0


def test_plan_matches_unit():
    from app.modules.graduation.services.graduation_topic_round_service import plan_topic_matches
    choices = [
        {"id": 1, "gd_student_id": 10, "topic_id": 100, "choice_order": 1},
        {"id": 2, "gd_student_id": 10, "topic_id": 101, "choice_order": 2},
        {"id": 3, "gd_student_id": 11, "topic_id": 100, "choice_order": 1},
    ]
    winners = plan_topic_matches(choices, {100: 2, 101: 1})
    assert len(winners) == 2
    assert winners[0]["gd_student_id"] == 10 and winners[0]["topic_id"] == 100


def test_round_export_and_choice_import(client, auth_headers, db_mode):
    import base64
    bid = _batch(client, auth_headers, "GD-RND-X1")
    tid = _approved_topic(client, auth_headers, "导出导入题")
    gid = _gd_student(client, auth_headers, "S-GD-RND-X1")
    cr = client.post(GD_ROUND, headers=auth_headers, json={"roundName": "Excel轮次", "batchId": bid}).json()
    rid = cr["data"]["id"]
    client.post(f"{GD_ROUND}/{rid}/open", headers=auth_headers)
    ex = client.post(f"{GD_ROUND}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"
    tpl = client.get(f"{GD_ROUND}/{rid}/choices/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"
    topic = client.get(f"{GD_TOPIC}/{tid}", headers=auth_headers).json()["data"]
    rows = [{"studentNo": "S-GD-RND-X1", "topicTitle": topic["title"], "choiceOrder": "1"}]
    imp = client.post(f"{GD_ROUND}/{rid}/choices/import/confirm", headers=auth_headers, json={"rows": rows}).json()
    assert imp["code"] == 0 and imp["data"].get("created", 0) >= 1, imp
    ch = client.get(f"{GD_ROUND}/{rid}/choices", headers=auth_headers).json()
    assert len(ch["data"]) >= 1
    cex = client.post(f"{GD_ROUND}/{rid}/choices/export", headers=auth_headers).json()
    assert cex["code"] == 0 and cex["data"]["rowCount"] >= 1

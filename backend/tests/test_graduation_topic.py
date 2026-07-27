"""毕业设计中心 · 题目库测试（MySQL 真库 via db_mode）。"""
from __future__ import annotations

import base64

GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_BATCH = "/api/v1/graduation/batches"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _batch(client, h, no="GD-TOP-B1"):
    return client.post(GD_BATCH, headers=h, json={
        "batchName": "2026届毕设", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _topic_body(**over):
    body = {"title": "智慧校园选题测试", "sourceType": "TEACHER", "advisorName": "王老师",
            "majorName": "软件技术", "capacity": 2, "requirements": "完成系统设计"}
    body.update(over)
    return body


def test_create_submit_approve(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-TOP-CR1")
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(batchId=bid)).json()
    assert r["code"] == 0 and r["data"]["reviewStatus"] == "DRAFT"
    tid = r["data"]["id"]
    assert client.post(f"{GD_TOPIC}/{tid}/submit-review", headers=auth_headers).json()["data"]["reviewStatus"] == "PENDING_REVIEW"
    a = client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"}).json()
    assert a["code"] == 0 and a["data"]["reviewStatus"] == "APPROVED" and a["data"]["status"] == "CONFIRMED"
    assert a["data"]["assignable"] is True


def test_reject_requires_comment(client, auth_headers, db_mode):
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="待驳回题", submitReview=True)).json()
    tid = r["data"]["id"]
    bad = client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "REJECT", "comment": "短"}).json()
    assert bad["code"] != 0
    ok = client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={
        "action": "REJECT", "comment": "题目范围过大需缩小"
    }).json()
    assert ok["code"] == 0 and ok["data"]["reviewStatus"] == "REJECTED"


def test_disable_enable_archive(client, auth_headers, db_mode):
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="停用归档题", submitReview=True)).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"})
    d = client.post(f"{GD_TOPIC}/{tid}/disable", headers=auth_headers, json={"reason": "导师调岗暂停招生"}).json()
    assert d["code"] == 0 and d["data"]["status"] == "DISABLED"
    e = client.post(f"{GD_TOPIC}/{tid}/enable", headers=auth_headers).json()
    assert e["code"] == 0 and e["data"]["status"] == "CONFIRMED"
    ar = client.post(f"{GD_TOPIC}/{tid}/archive", headers=auth_headers, json={"reason": "届次结束"}).json()
    assert ar["code"] == 0 and ar["data"]["status"] == "ARCHIVED"


def test_assign_student_requires_approved(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    MAIN_TID = 1000000000000000001
    db = get_sessionmaker()()
    try:
        t = GraduationTopic(tenant_id=MAIN_TID, title="未审核题", source="教师申报", source_type="TEACHER",
                            advisor_name="李老师", major_name="软件技术", capacity=2, selected=0,
                            review_status="DRAFT", status="PENDING_CONFIRM")
        db.add(t)
        db.commit()
        db.refresh(t)
        draft_id = str(t.id)
    finally:
        db.close()
    sid = client.post(STU, headers=auth_headers, json={"studentNo": "S-GDT-001", "realName": "选题测"}).json()["data"]["id"]
    rid = client.post(GD_STU, headers=auth_headers, json={"studentId": sid}).json()["data"]["id"]
    assert client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": draft_id}).json()["code"] != 0
    # 审核后可分配
    ap = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="可分配题", submitReview=True)).json()
    tid = ap["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"})
    ok = client.post(f"{GD_STU}/{rid}/assign-topic", headers=auth_headers, json={"topicId": tid}).json()
    assert ok["code"] == 0
    assigned = client.get(f"{GD_TOPIC}/{tid}/assigned-students", headers=auth_headers).json()
    assert assigned["code"] == 0 and len(assigned["data"]) == 1


def test_import_and_export(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-TOP-IMP1")
    batch_no = client.get(f"{GD_BATCH}/{bid}", headers=auth_headers).json()["data"]["batchNo"]
    rows = [
        {"title": "Excel导入题目A", "batchNo": batch_no, "topicNo": "T-IMP-001",
         "sourceType": "教师申报", "advisorName": "王老师", "capacity": "2", "submitReview": "否"},
        {"title": "", "topicNo": "T-IMP-002"},
        {"title": "企业题缺名", "sourceType": "企业题目", "topicNo": "T-IMP-003"},
    ]
    dry = client.post(f"{GD_TOPIC}/import/dry-run", headers=auth_headers, json={"rows": rows}).json()
    assert dry["code"] == 0 and dry["data"]["invalidRows"] >= 2
    ok_rows = [rows[0]]
    dry2 = client.post(f"{GD_TOPIC}/import/dry-run", headers=auth_headers, json={"rows": ok_rows}).json()
    assert dry2["data"]["validRows"] == 1
    imp = client.post(f"{GD_TOPIC}/import/confirm", headers=auth_headers, json={"rows": ok_rows}).json()
    assert imp["code"] == 0 and imp["data"]["created"] == 1
    tpl = client.get(f"{GD_TOPIC}/import/template", headers=auth_headers)
    assert tpl.status_code == 200 and tpl.content[:2] == b"PK"
    ex = client.post(f"{GD_TOPIC}/export", headers=auth_headers).json()
    assert ex["code"] == 0 and ex["data"]["rowCount"] >= 1
    raw = base64.b64decode(ex["data"]["contentBase64"])
    assert raw[:2] == b"PK"


def test_list_filter_by_source(client, auth_headers, db_mode):
    client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="企业题A", sourceType="ENTERPRISE", enterpriseName="某科技公司"))
    lst = client.get(GD_TOPIC, headers=auth_headers, params={"sourceType": "ENTERPRISE"}).json()
    assert lst["code"] == 0 and any("企业题" in x["title"] for x in lst["data"]["items"])


def test_stats_category_and_gaps(client, auth_headers, db_mode):
    client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="无分类题", category="", requirements=""))
    st = client.get(f"{GD_TOPIC}/stats", headers=auth_headers).json()
    assert st["code"] == 0
    assert "categoryStats" in st["data"] and "requirementsGap" in st["data"]
    cats = client.get(f"{GD_TOPIC}/category-stats", headers=auth_headers).json()
    assert cats["code"] == 0 and isinstance(cats["data"], list)
    gap = client.get(GD_TOPIC, headers=auth_headers, params={"hasRequirements": False}).json()
    assert gap["code"] == 0


def test_capacity_and_attachments(client, auth_headers, db_mode):
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="容量附件题", submitReview=True)).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"})
    cap = client.put(f"{GD_TOPIC}/{tid}/capacity", headers=auth_headers, json={"capacity": 3}).json()
    assert cap["code"] == 0 and cap["data"]["capacity"] == 3
    att = client.put(f"{GD_TOPIC}/{tid}/attachments", headers=auth_headers, json={
        "attachments": [{"name": "任务书.pdf", "url": "/files/task.pdf", "size": 1024}]
    }).json()
    assert att["code"] == 0 and att["data"]["attachmentCount"] == 1
    lst = client.get(GD_TOPIC, headers=auth_headers, params={"hasAttachments": True}).json()
    assert lst["code"] == 0 and any(x["id"] == tid for x in lst["data"]["items"])


def test_topic_history(client, auth_headers, db_mode):
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="历史审计题", submitReview=True)).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"})
    hist = client.get(f"{GD_TOPIC}/history", headers=auth_headers, params={"topicId": tid}).json()
    assert hist["code"] == 0 and hist["data"]["total"] >= 1
    assert any(h["topicId"] == tid for h in hist["data"]["items"])


def test_history_export(client, auth_headers, db_mode):
    import base64
    r = client.post(GD_TOPIC, headers=auth_headers, json=_topic_body(title="历史导出题", submitReview=True)).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=auth_headers, json={"action": "APPROVE"})
    ex = client.post(f"{GD_TOPIC}/history/export", headers=auth_headers, params={"topicId": tid}).json()
    assert ex["code"] == 0 and ex["data"]["rowCount"] >= 1
    assert base64.b64decode(ex["data"]["contentBase64"])[:2] == b"PK"

"""毕业设计中心 · 选题管理业务闭环测试：
教师人工确认/驳回志愿（一对一，自动关闭同轮次其余待处理志愿）+ 课题变更申请（发起→审核通过迁移分配/驳回）
+ 学生/教师 mobile 自服务端点（浏览题目、提交志愿、发起变更、教师确认/驳回、审核变更）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_ROUND = "/api/v1/graduation/gd-topic-rounds"
GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_BATCH = "/api/v1/graduation/batches"
GD_STU = "/api/v1/graduation/gd-students"
GD_CHANGE = "/api/v1/graduation/gd-topic-change-requests"
STU = "/api/v1/students"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name="王老师"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "GD_MENTOR", "clientType": "MP"})}


def _batch(client, h, no):
    return client.post(GD_BATCH, headers=h, json={
        "batchName": "变更测试批次", "batchNo": no, "gradeYear": "2026届", "plannedCount": 50
    }).json()["data"]["id"]


def _approved_topic(client, h, title, advisor="王老师", capacity=1):
    r = client.post(GD_TOPIC, headers=h, json={
        "title": title, "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": capacity, "submitReview": True
    }).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    return tid


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def _round_open(client, h, batch_id, name):
    rid = client.post(GD_ROUND, headers=h, json={"roundName": name, "batchId": batch_id, "maxChoices": 3}).json()["data"]["id"]
    client.post(f"{GD_ROUND}/{rid}/open", headers=h)
    return rid


# ═══════════ 教师人工确认/驳回志愿 ═══════════

def test_confirm_choice_locks_assignment_and_closes_other_pending(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B1")
    t1 = _approved_topic(client, auth_headers, "确认测试题1")
    t2 = _approved_topic(client, auth_headers, "确认测试题2")
    gid = _gd_student(client, auth_headers, "S-CHG-01", "确认测A")
    rid = _round_open(client, auth_headers, bid, "确认轮次")
    client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers, json={
        "gdStudentId": gid, "choices": [{"topicId": t1, "choiceOrder": 1}, {"topicId": t2, "choiceOrder": 2}]
    })
    choices = client.get(f"{GD_ROUND}/{rid}/choices", headers=auth_headers).json()["data"]
    assert len(choices) == 2 and all(c["status"] == "PENDING" for c in choices)
    first_choice_id = [c for c in choices if c["topicId"] == t1][0]["id"]

    r = client.post(f"{GD_ROUND}/choices/{first_choice_id}/confirm", headers=auth_headers).json()
    assert r["code"] == 0 and r["data"]["status"] == "CONFIRMED"

    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()["data"]
    assert stu["topicId"] == t1

    choices2 = client.get(f"{GD_ROUND}/{rid}/choices", headers=auth_headers).json()["data"]
    other = [c for c in choices2 if c["topicId"] == t2][0]
    assert other["status"] == "REJECTED"  # 自动关闭

    # 已确认志愿不能重复确认
    again = client.post(f"{GD_ROUND}/choices/{first_choice_id}/confirm", headers=auth_headers).json()
    assert again["code"] != 0


def test_reject_choice_does_not_consume_capacity(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B2")
    t1 = _approved_topic(client, auth_headers, "驳回测试题")
    gid = _gd_student(client, auth_headers, "S-CHG-02", "驳回测B")
    rid = _round_open(client, auth_headers, bid, "驳回轮次")
    client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers, json={
        "gdStudentId": gid, "choices": [{"topicId": t1, "choiceOrder": 1}]
    })
    choice_id = client.get(f"{GD_ROUND}/{rid}/choices", headers=auth_headers).json()["data"][0]["id"]
    r = client.post(f"{GD_ROUND}/choices/{choice_id}/reject", headers=auth_headers,
                    json={"reason": "与选题范围不符"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "REJECTED"
    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()["data"]
    assert not stu["topicId"]
    topic = client.get(f"{GD_TOPIC}/{t1}", headers=auth_headers).json()["data"]
    assert topic["selected"] == 0


def test_pending_choices_endpoint_and_match_round_still_works(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B3")
    t1 = _approved_topic(client, auth_headers, "混合流程题1", capacity=1)
    t2 = _approved_topic(client, auth_headers, "混合流程题2", capacity=1)
    g1 = _gd_student(client, auth_headers, "S-CHG-03", "混合A")
    g2 = _gd_student(client, auth_headers, "S-CHG-04", "混合B")
    rid = _round_open(client, auth_headers, bid, "混合轮次")
    client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers,
               json={"gdStudentId": g1, "choices": [{"topicId": t1, "choiceOrder": 1}]})
    client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers,
               json={"gdStudentId": g2, "choices": [{"topicId": t2, "choiceOrder": 1}]})
    pend = client.get(f"{GD_ROUND}/{rid}/choices/pending", headers=auth_headers).json()
    assert pend["code"] == 0 and len(pend["data"]) == 2
    g1_choice_id = [c for c in pend["data"] if c["gdStudentId"] == g1][0]["id"]
    client.post(f"{GD_ROUND}/choices/{g1_choice_id}/confirm", headers=auth_headers)
    # g2 仍 PENDING，match_round 应只处理 g2
    m = client.post(f"{GD_ROUND}/{rid}/match", headers=auth_headers).json()
    assert m["code"] == 0 and m["data"]["matched"] == 1
    stu2 = client.get(f"{GD_STU}/{g2}", headers=auth_headers).json()["data"]
    assert stu2["topicId"] == t2


# ═══════════ 课题变更申请 ═══════════

def _assigned_student(client, h, batch_id, no, name, topic_title, capacity=1):
    tid = _approved_topic(client, h, topic_title, capacity=capacity)
    gid = _gd_student(client, h, no, name)
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid, tid


def test_change_request_approve_migrates_assignment(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B4")
    gid, old_tid = _assigned_student(client, auth_headers, bid, "S-CHG-05", "变更测C", "变更旧题")
    new_tid = _approved_topic(client, auth_headers, "变更新题", capacity=1)

    cr = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": new_tid, "reason": "研究方向调整，原题目不再适合"
    }).json()
    assert cr["code"] == 0 and cr["data"]["status"] == "PENDING"
    rid = cr["data"]["id"]

    # 有未决申请时不能重复发起
    dup = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": new_tid, "reason": "再次尝试"
    }).json()
    assert dup["code"] != 0

    detail = client.get(f"{GD_CHANGE}/{rid}", headers=auth_headers).json()
    assert detail["code"] == 0 and detail["data"]["oldTopicTitle"] == "变更旧题"

    rev = client.post(f"{GD_CHANGE}/{rid}/review", headers=auth_headers,
                      json={"action": "APPROVE", "comment": "同意变更"}).json()
    assert rev["code"] == 0 and rev["data"]["status"] == "APPROVED"

    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()["data"]
    assert stu["topicId"] == new_tid

    old_topic = client.get(f"{GD_TOPIC}/{old_tid}", headers=auth_headers).json()["data"]
    new_topic = client.get(f"{GD_TOPIC}/{new_tid}", headers=auth_headers).json()["data"]
    assert old_topic["selected"] == 0 and new_topic["selected"] == 1

    # 已处理的申请不能重复审核
    again = client.post(f"{GD_CHANGE}/{rid}/review", headers=auth_headers,
                        json={"action": "APPROVE"}).json()
    assert again["code"] != 0


def test_change_request_reject_requires_reason_and_keeps_old_topic(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B5")
    gid, old_tid = _assigned_student(client, auth_headers, bid, "S-CHG-06", "变更测D", "驳回旧题")
    new_tid = _approved_topic(client, auth_headers, "驳回新题", capacity=1)
    rid = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": new_tid, "reason": "希望更换研究方向"
    }).json()["data"]["id"]

    too_short = client.post(f"{GD_CHANGE}/{rid}/review", headers=auth_headers,
                            json={"action": "REJECT", "comment": "不行"}).json()
    assert too_short["code"] != 0  # 驳回理由不足5字

    rev = client.post(f"{GD_CHANGE}/{rid}/review", headers=auth_headers,
                      json={"action": "REJECT", "comment": "现阶段不建议更换课题"}).json()
    assert rev["code"] == 0 and rev["data"]["status"] == "REJECTED"

    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()["data"]
    assert stu["topicId"] == old_tid  # 题目未变


def test_change_request_rejects_full_or_unapproved_target(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B6")
    gid, _old_tid = _assigned_student(client, auth_headers, bid, "S-CHG-07", "变更测E", "满员场景旧题")
    full_topic = _approved_topic(client, auth_headers, "已满员新题", capacity=1)
    other_gid, _ = _assigned_student(client, auth_headers, bid, "S-CHG-08", "占位学生", "占位旧题")
    # 手动把 full_topic 占满：让占位学生变更过去
    client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": other_gid, "newTopicId": full_topic, "reason": "占位以测试满员校验"
    })
    pending_id = client.get(GD_CHANGE, headers=auth_headers, params={"gdStudentId": other_gid}).json()["data"]["items"][0]["id"]
    client.post(f"{GD_CHANGE}/{pending_id}/review", headers=auth_headers, json={"action": "APPROVE"})

    bad = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": full_topic, "reason": "尝试申请已满员题目"
    }).json()
    assert bad["code"] != 0


def test_change_request_needs_existing_topic(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-B7")
    tid = _approved_topic(client, auth_headers, "无题学生场景题")
    gid = _gd_student(client, auth_headers, "S-CHG-09", "无题测F")
    r = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": tid, "reason": "尚未选题就申请变更"
    }).json()
    assert r["code"] != 0


# ═══════════ Mobile 学生自服务 ═══════════

def test_mobile_student_browse_submit_and_request_change(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-M1")
    t1 = _approved_topic(client, auth_headers, "学生浏览题1", advisor="张导师")
    t2 = _approved_topic(client, auth_headers, "学生浏览题2", advisor="张导师")
    sid = client.post(STU, headers=auth_headers, json={"studentNo": "S-CHG-M1", "realName": "移动测学生"}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=auth_headers, json={"studentId": sid}).json()["data"]["id"]
    rid = _round_open(client, auth_headers, bid, "移动端轮次")

    tok = _stu_token("移动测学生")

    topics = client.get("/api/v1/mobile/graduation/topics", headers=tok).json()
    assert topics["code"] == 0 and len(topics["data"]) >= 2

    active = client.get("/api/v1/mobile/graduation/active-round", headers=tok).json()
    assert active["code"] == 0 and active["data"]["id"] == str(rid)
    assert active["data"]["myChoices"] == []

    sub = client.post("/api/v1/mobile/graduation/choices", headers=tok, json={
        "roundId": rid, "choices": [{"topicId": t1, "choiceOrder": 1}, {"topicId": t2, "choiceOrder": 2}]
    }).json()
    assert sub["code"] == 0 and sub["data"]["submitted"] == 2

    active2 = client.get("/api/v1/mobile/graduation/active-round", headers=tok).json()
    assert len(active2["data"]["myChoices"]) == 2

    # 教师确认其中一个志愿后，学生已有题目，可发起变更申请
    choice_id = [c for c in active2["data"]["myChoices"] if c["topicId"] == t1][0]["id"]
    client.post(f"{GD_ROUND}/choices/{choice_id}/confirm", headers=auth_headers)

    t3 = _approved_topic(client, auth_headers, "学生变更目标题", advisor="张导师")
    chg = client.post("/api/v1/mobile/graduation/change-request", headers=tok, json={
        "newTopicId": t3, "reason": "希望调整到更契合方向的题目"
    }).json()
    assert chg["code"] == 0 and chg["data"]["status"] == "PENDING"

    mine = client.get("/api/v1/mobile/graduation/change-requests/my", headers=tok).json()
    assert mine["code"] == 0 and len(mine["data"]) == 1


def test_mobile_student_cannot_submit_without_gd_record(client, auth_headers, db_mode):
    tok = _stu_token("查无此人的学生")
    r = client.post("/api/v1/mobile/graduation/choices", headers=tok,
                    json={"roundId": "1", "choices": [{"topicId": "1", "choiceOrder": 1}]}).json()
    assert r["code"] != 0


# ═══════════ Mobile 教师自服务 ═══════════

def test_mobile_teacher_confirm_reject_and_change_review(client, auth_headers, db_mode):
    bid = _batch(client, auth_headers, "GD-CHG-M2")
    t1 = _approved_topic(client, auth_headers, "教师范围题1", advisor="李导师")
    other_topic = _approved_topic(client, auth_headers, "非本人题目", advisor="别的老师")
    gid = _gd_student(client, auth_headers, "S-CHG-M2", "教师测学生")
    rid = _round_open(client, auth_headers, bid, "教师端轮次")
    client.post(f"{GD_ROUND}/{rid}/choices", headers=auth_headers,
               json={"gdStudentId": gid, "choices": [{"topicId": t1, "choiceOrder": 1}]})

    teacher_tok = _teacher_token("李导师")
    pending = client.get("/api/v1/mobile/teacher/graduation/choices/pending", headers=teacher_tok).json()
    assert pending["code"] == 0 and len(pending["data"]) == 1
    choice_id = pending["data"][0]["id"]

    # 越权：其他老师不能审核不属于自己的题目志愿
    other_teacher_tok = _teacher_token("路人甲")
    forbid = client.post(f"/api/v1/mobile/teacher/graduation/choices/{choice_id}/review",
                         headers=other_teacher_tok, json={"action": "CONFIRM"}).json()
    assert forbid["code"] != 0

    ok = client.post(f"/api/v1/mobile/teacher/graduation/choices/{choice_id}/review",
                     headers=teacher_tok, json={"action": "CONFIRM"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "CONFIRMED"

    # 变更申请审核（新题导师=李导师）
    new_topic = _approved_topic(client, auth_headers, "教师范围新题", advisor="李导师")
    cr = client.post(GD_CHANGE, headers=auth_headers, json={
        "gdStudentId": gid, "newTopicId": new_topic, "reason": "教师端审核变更测试场景"
    }).json()["data"]

    pending_cr = client.get("/api/v1/mobile/teacher/graduation/change-requests/pending",
                            headers=teacher_tok).json()
    assert pending_cr["code"] == 0 and any(x["id"] == cr["id"] for x in pending_cr["data"])

    rev = client.post(f"/api/v1/mobile/teacher/graduation/change-requests/{cr['id']}/review",
                      headers=teacher_tok, json={"action": "APPROVE"}).json()
    assert rev["code"] == 0 and rev["data"]["status"] == "APPROVED"

    stu = client.get(f"{GD_STU}/{gid}", headers=auth_headers).json()["data"]
    assert stu["topicId"] == new_topic

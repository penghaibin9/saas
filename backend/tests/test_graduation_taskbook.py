"""毕业设计中心 · 任务书测试：下达→确认（推进阶段GUIDING）→变更→重新确认 + 版本历史 + 统计 + 导出。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_TASKBOOK = "/api/v1/graduation/gd-taskbooks"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_ASSIGN = "/api/v1/graduation/gd-mentor-assignments"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"


def _gd_student_with_mentor(client, h, no, name, mentor_no):
    """建档 + 分配导师（不涉及选题，stage 保持 TOPIC_SELECTING）。"""
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    mid = client.post(GD_MENTOR, headers=h, json={"teacherNo": mentor_no, "teacherName": f"导师{mentor_no}"}).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid})
    return gid


def _gd_student_with_topic_and_mentor(client, h, no, name, mentor_no):
    """建档 + 选题确认（stage→TASKBOOK_CONFIRM）+ 分配导师，模拟任务书下达的真实前置条件。"""
    gid = _gd_student_with_mentor(client, h, no, name, mentor_no)
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": f"导师{mentor_no}",
        "capacity": 1, "submitReview": True
    }).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def test_issue_requires_mentor_and_no_duplicate(client, auth_headers, db_mode):
    h = auth_headers
    sid = client.post(STU, headers=h, json={"studentNo": "TB001", "realName": "无导师生"}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]

    no_mentor = client.post(f"{GD_TASKBOOK}/{gid}/issue", headers=h, json={"objective": "完成毕设选题相关设计", "content": "系统设计与实现"})
    assert no_mentor.json()["code"] != 0

    gid2 = _gd_student_with_mentor(client, h, "TB002", "有导师生", "MTB1")
    ok = client.post(f"{GD_TASKBOOK}/{gid2}/issue", headers=h, json={"objective": "完成系统设计文档", "content": "完成系统详细设计"})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["status"] == "PENDING_CONFIRM"
    assert ok.json()["data"]["taskbookVersion"] == 1

    dup = client.post(f"{GD_TASKBOOK}/{gid2}/issue", headers=h, json={"objective": "重复下达", "content": "重复"})
    assert dup.json()["code"] != 0


def test_confirm_advances_student_stage_to_guiding(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student_with_topic_and_mentor(client, h, "TB101", "小明", "MTB2")
    stu_before = client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu_before["stage"] == "TASKBOOK_CONFIRM"

    client.post(f"{GD_TASKBOOK}/{gid}/issue", headers=h, json={"objective": "完成系统设计文档", "content": "完成系统详细设计"})
    confirm = client.post(f"{GD_TASKBOOK}/{gid}/confirm", headers=h)
    assert confirm.json()["data"]["status"] == "CONFIRMED"

    stu_after = client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu_after["stage"] == "GUIDING"

    again = client.post(f"{GD_TASKBOOK}/{gid}/confirm", headers=h)
    assert again.json()["code"] != 0  # 已确认无需再确认


def test_change_requires_confirmed_and_reason_keeps_history(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student_with_mentor(client, h, "TB201", "小红", "MTB3")
    client.post(f"{GD_TASKBOOK}/{gid}/issue", headers=h, json={"objective": "完成系统设计文档", "content": "完成系统详细设计"})

    too_early = client.post(f"{GD_TASKBOOK}/{gid}/change", headers=h, json={"objective": "调整目标", "reason": "范围收窄"})
    assert too_early.json()["code"] != 0  # 尚未确认不可变更

    client.post(f"{GD_TASKBOOK}/{gid}/confirm", headers=h)

    short_reason = client.post(f"{GD_TASKBOOK}/{gid}/change", headers=h, json={"objective": "调整目标", "reason": "x"})
    assert short_reason.json()["code"] != 0

    chg = client.post(f"{GD_TASKBOOK}/{gid}/change", headers=h, json={"objective": "调整为移动端方向", "reason": "选题范围调整为移动端"})
    body = chg.json()["data"]
    assert body["status"] == "CHANGE_PENDING"
    assert body["taskbookVersion"] == 2
    assert len(body["history"]) == 1
    assert body["history"][0]["version"] == 1

    reconfirm = client.post(f"{GD_TASKBOOK}/{gid}/confirm", headers=h)
    assert reconfirm.json()["data"]["status"] == "CONFIRMED"


def test_stats_and_export(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student_with_mentor(client, h, "TB301", "小刚", "MTB4")
    client.post(f"{GD_TASKBOOK}/{gid}/issue", headers=h, json={"objective": "完成系统设计文档", "content": "完成系统详细设计"})

    stats = client.get(f"{GD_TASKBOOK}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

    exp = client.post(f"{GD_TASKBOOK}/export", headers=h)
    body = exp.json()
    assert body["code"] == 0
    assert body["data"]["rowCount"] >= 1

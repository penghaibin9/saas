"""毕业设计中心 · 答辩安排闭环测试：
答辩组新建（同名拒绝）→ 可分配学生 → 分配（评委回避导师自动检测）→ 冲突拦截发布 →
编辑解除冲突 → 完整后发布（须组长/地点/学生齐全）→ Excel 导出 → 学生端查看（发布后可见时间地点）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
DG = "/api/v1/graduation/defense-groups"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _student_with_advisor(client, h, no, name, advisor):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": f"{name}的毕设题目", "sourceType": "TEACHER", "advisorName": advisor,
        "capacity": 1, "submitReview": True}).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    return gid


def test_create_and_duplicate(client, auth_headers, db_mode):
    h = auth_headers
    ok = client.post(DG, headers=h, json={"groupName": "答辩组甲", "chair": "组长A", "location": "A301",
                                          "members": ["评委1", "评委2"], "secretary": "秘书A"})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["groupName"] == "答辩组甲"

    dup = client.post(DG, headers=h, json={"groupName": "答辩组甲"})
    assert dup.json()["code"] != 0


def test_assign_conflict_then_resolve_and_publish(client, auth_headers, db_mode):
    h = auth_headers
    # 组的评委里含"张导师"，学生导师也是"张导师" → 回避冲突
    grp = client.post(DG, headers=h, json={"groupName": "答辩组乙", "chair": "组长B", "location": "B201",
                                           "members": ["张导师", "评委X"], "secretary": "秘书B"}).json()["data"]
    gid = grp["id"]
    _student_with_advisor(client, h, "DF001", "答辩甲", "张导师")

    elig = client.get(f"{DG}/eligible-students", headers=h, params={"gid": gid}).json()["data"]["items"]
    sid = next(s["id"] for s in elig if s["name"] == "答辩甲")

    assigned = client.post(f"{DG}/{gid}/assign", headers=h, json={"studentIds": [sid]}).json()["data"]
    assert assigned["studentCount"] == 1
    assert assigned["conflict"]  # 评委与导师冲突已检出

    blocked = client.post(f"{DG}/{gid}/publish", headers=h)
    assert blocked.json()["code"] != 0  # 冲突拦截发布

    # 编辑：把冲突评委换掉，冲突解除（学生保持分配）
    fixed = client.put(f"{DG}/{gid}", headers=h, json={"groupName": "答辩组乙", "chair": "组长B",
                       "location": "B201", "members": ["评委Y", "评委X"], "secretary": "秘书B"}).json()["data"]
    assert fixed["conflict"] == ""
    assert fixed["studentCount"] == 1

    pub = client.post(f"{DG}/{gid}/publish", headers=h)
    assert pub.json()["code"] == 0
    assert pub.json()["data"]["published"] is True


def test_publish_requires_students(client, auth_headers, db_mode):
    h = auth_headers
    grp = client.post(DG, headers=h, json={"groupName": "答辩组丙", "chair": "组长C", "location": "C101",
                                           "members": ["评委M"], "secretary": "秘书C"}).json()["data"]
    no_stu = client.post(f"{DG}/{grp['id']}/publish", headers=h)
    assert no_stu.json()["code"] != 0  # 无学生不可发布


def test_export_and_student_view(client, auth_headers, db_mode):
    h = auth_headers
    grp = client.post(DG, headers=h, json={"groupName": "答辩组丁", "chair": "组长D", "location": "D505",
                                           "members": ["评委甲", "评委乙"], "secretary": "秘书D"}).json()["data"]
    gid = grp["id"]
    _student_with_advisor(client, h, "DF401", "答辩戊", "王导师")  # 导师不在评委名单，无冲突
    elig = client.get(f"{DG}/eligible-students", headers=h, params={"gid": gid}).json()["data"]["items"]
    sid = next(s["id"] for s in elig if s["name"] == "答辩戊")
    client.post(f"{DG}/{gid}/assign", headers=h, json={"studentIds": [sid]})

    sh = _stu_token("答辩戊")
    before = client.get(f"{MOBILE}/graduation/defense", headers=sh).json()["data"]
    assert before["assigned"] is True and before["published"] is False  # 未发布不展示时间地点

    client.post(f"{DG}/{gid}/publish", headers=h)
    after = client.get(f"{MOBILE}/graduation/defense", headers=sh).json()["data"]
    assert after["published"] is True
    assert after["location"] == "D505"

    exp = client.post(f"{DG}/export", headers=h)
    assert exp.json()["code"] == 0
    assert exp.json()["data"]["rowCount"] >= 1

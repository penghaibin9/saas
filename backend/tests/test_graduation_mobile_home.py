"""毕业设计中心 · 移动端学生主页真实化测试：graduation_my 返回真实批次名、阶段标签、
按 stage 派生的节点进度、以及真实指导记录（不再用 mock 假记录/假入口）。
教师新增一条指导记录后，学生主页 guideLogs 必须出现该条真实内容。全部走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_ASSIGN = "/api/v1/graduation/gd-mentor-assignments"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"
MOBILE = "/api/v1/mobile"


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "GD_MENTOR", "clientType": "MP"})}


def test_graduation_my_real_nodes_stage_and_guide_logs(graduation_client, auth_headers, db_mode):
    h = auth_headers
    student_no, student_name = "HM001", "主页测试生"
    sid = graduation_client.post(STU, headers=h, json={"studentNo": student_no, "realName": student_name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    mid = graduation_client.post(GD_MENTOR, headers=h, json={"teacherNo": "HMT1", "teacherName": "主页导师"}).json()["data"]["id"]
    graduation_client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid})

    sh = _stu_token(student_name)
    g0 = graduation_client.get(f"{MOBILE}/graduation/my", headers=sh).json()["data"]
    assert g0["hasData"] is True
    # 真实派生节点：8 个阶段节点（含 DEFENSE 与 ARCHIVED 之间新增的 COMPLETED），且恰有一个 current
    assert isinstance(g0["nodes"], list) and len(g0["nodes"]) == 8
    assert sum(1 for n in g0["nodes"] if n.get("current")) == 1
    assert g0["stageLabel"]  # 非空阶段标签
    # 尚无指导记录 → guideLogs 为空（前端展示空态，不再塞 mock 假记录）
    assert g0["guideLogs"] == []

    # 教师新增一条真实指导记录
    th = _teacher_token("主页导师")
    add = graduation_client.post(f"{MOBILE}/teacher/graduation/{gid}/guidance", headers=th,
                      json={"content": "主页指导记录真实内容", "method": "ONLINE", "issues": "注意进度"})
    assert add.json()["code"] == 0

    # 学生主页 guideLogs 必须出现该真实记录（内容、from=导师、issues 透出）
    g1 = graduation_client.get(f"{MOBILE}/graduation/my", headers=sh).json()["data"]
    assert len(g1["guideLogs"]) == 1
    log = g1["guideLogs"][0]
    assert log["text"] == "主页指导记录真实内容"
    assert log["from"] == "主页导师"
    assert log["issues"] == "注意进度"

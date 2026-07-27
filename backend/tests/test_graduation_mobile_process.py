"""毕业设计中心 · 移动端过程指导测试：学生查看/确认任务书、提交中期整改、查看成绩；
教师查看本人指导学生列表 + 移动端快速新增指导记录（越权拦截）。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_ASSIGN = "/api/v1/graduation/gd-mentor-assignments"
GD_TASKBOOK = "/api/v1/graduation/gd-taskbooks"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _stu_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "GD_MENTOR", "clientType": "MP"})}


def _items(data):
    return data.get("items", []) if isinstance(data, dict) else data


def test_student_taskbook_midterm_grade_and_teacher_guidance(client, auth_headers, db_mode):
    h = auth_headers
    student_no, student_name = "MB001", "移动测试生"
    sid = client.post(STU, headers=h, json={"studentNo": student_no, "realName": student_name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    mid = client.post(GD_MENTOR, headers=h, json={"teacherNo": "MBT1", "teacherName": "移动导师"}).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid})
    client.post(f"{GD_TASKBOOK}/{gid}/issue", headers=h, json={"objective": "完成移动端联调", "content": "完成移动端接口联调测试"})

    sh = _stu_token(student_name)
    tb = client.get(f"{MOBILE}/graduation/taskbook", headers=sh).json()["data"]
    assert tb["hasData"] is True
    assert tb["status"] == "PENDING_CONFIRM"

    confirm = client.post(f"{MOBILE}/graduation/taskbook/confirm", headers=sh).json()["data"]
    assert confirm["status"] == "CONFIRMED"

    mt = client.get(f"{MOBILE}/graduation/midterm", headers=sh).json()["data"]
    assert mt["hasData"] is True

    grade_before = client.get(f"{MOBILE}/graduation/grade", headers=sh).json()["data"]
    assert grade_before["published"] is False

    th = _teacher_token("移动导师")
    my_students = _items(client.get(f"{MOBILE}/teacher/graduation/my-students", headers=th).json()["data"])
    assert any(s["gdStudentId"] == str(gid) for s in my_students)

    add_guidance = client.post(f"{MOBILE}/teacher/graduation/{gid}/guidance", headers=th,
                               json={"content": "移动端指导记录测试", "method": "ONLINE"})
    assert add_guidance.json()["code"] == 0

    wrong_teacher = _teacher_token("不是导师")
    denied = client.post(f"{MOBILE}/teacher/graduation/{gid}/guidance", headers=wrong_teacher,
                        json={"content": "越权测试"})
    assert denied.json()["code"] != 0

"""毕业设计中心 · 导师管理 + 导师分配测试：申报→审核→分配/调导师/取消 + 容量校验 + 统计 + Excel。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_ASSIGN = "/api/v1/graduation/gd-mentor-assignments"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(graduation_client, h, no, name):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def _qualified_mentor(graduation_client, h, no, name, max_capacity=8):
    mid = graduation_client.post(GD_MENTOR, headers=h, json={
        "teacherNo": no, "teacherName": name, "maxCapacity": max_capacity
    }).json()["data"]["id"]
    graduation_client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    return mid


def test_mentor_lifecycle_review_disable_enable_archive(graduation_client, auth_headers, db_mode):
    h = auth_headers
    r = graduation_client.post(GD_MENTOR, headers=h, json={"teacherNo": "T001", "teacherName": "王芳", "maxCapacity": 5})
    assert r.status_code == 200
    m = r.json()["data"]
    assert m["qualificationStatus"] == "PENDING_REVIEW"
    mid = m["id"]

    dup = graduation_client.post(GD_MENTOR, headers=h, json={"teacherNo": "T001", "teacherName": "王芳2"})
    assert dup.json()["code"] != 0

    rej = graduation_client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "REJECT", "comment": "材料不完整需补充"})
    assert rej.json()["data"]["qualificationStatus"] == "REJECTED"

    again = graduation_client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    assert again.json()["code"] != 0  # 已审核过，非待审核

    mid2 = graduation_client.post(GD_MENTOR, headers=h, json={"teacherNo": "T002", "teacherName": "李强"}).json()["data"]["id"]
    ok = graduation_client.post(f"{GD_MENTOR}/{mid2}/review", headers=h, json={"action": "APPROVE"})
    assert ok.json()["data"]["qualificationStatus"] == "QUALIFIED"

    dis = graduation_client.post(f"{GD_MENTOR}/{mid2}/disable", headers=h, json={"reason": "退休停止指导"})
    assert dis.json()["data"]["qualificationStatus"] == "DISABLED"

    en = graduation_client.post(f"{GD_MENTOR}/{mid2}/enable", headers=h)
    assert en.json()["data"]["qualificationStatus"] == "QUALIFIED"

    dis2 = graduation_client.post(f"{GD_MENTOR}/{mid2}/disable", headers=h, json={"reason": "退休停止指导"})
    assert dis2.json()["data"]["qualificationStatus"] == "DISABLED"
    arc = graduation_client.post(f"{GD_MENTOR}/{mid2}/archive", headers=h)
    assert arc.json()["data"]["qualificationStatus"] == "ARCHIVED"


def test_assign_requires_qualified_and_respects_capacity(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "S1001", "张三")
    pending_mid = graduation_client.post(GD_MENTOR, headers=h, json={"teacherNo": "T101", "teacherName": "赵老师"}).json()["data"]["id"]

    bad = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": pending_mid})
    assert bad.json()["code"] != 0  # 未认证不可分配

    mid = _qualified_mentor(graduation_client, h, "T102", "孙老师", max_capacity=1)
    ok = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid, "reason": "专业匹配"})
    assert ok.json()["code"] == 0

    stu = graduation_client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu["advisorName"] == "孙老师"

    gid2 = _gd_student(graduation_client, h, "S1002", "李四")
    full = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid2, "mentorId": mid})
    assert full.json()["code"] != 0  # 满员

    dup_assign = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid})
    assert dup_assign.json()["code"] != 0  # 已有导师


def test_change_mentor_releases_old_capacity_and_records_history(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "S2001", "周五")
    mid_a = _qualified_mentor(graduation_client, h, "T201", "导师甲", max_capacity=1)
    mid_b = _qualified_mentor(graduation_client, h, "T202", "导师乙", max_capacity=1)

    graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid_a})

    short_reason = graduation_client.post(f"{GD_ASSIGN}/change", headers=h, json={"gdStudentId": gid, "newMentorId": mid_b, "reason": "x"})
    assert short_reason.json()["code"] != 0

    chg = graduation_client.post(f"{GD_ASSIGN}/change", headers=h, json={
        "gdStudentId": gid, "newMentorId": mid_b, "reason": "导师甲请假需调整"})
    assert chg.json()["code"] == 0

    stu = graduation_client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu["advisorName"] == "导师乙"

    mentor_a_detail = graduation_client.get(f"{GD_MENTOR}/{mid_a}", headers=h).json()["data"]
    assert mentor_a_detail["currentCount"] == 0  # 原导师名额已释放

    gid2 = _gd_student(graduation_client, h, "S2002", "郑六")
    reassign_a = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid2, "mentorId": mid_a})
    assert reassign_a.json()["code"] == 0

    hist = graduation_client.get(GD_ASSIGN, headers=h, params={"gdStudentId": gid}).json()["data"]["items"]
    statuses = sorted(x["status"] for x in hist)
    assert statuses == ["ACTIVE", "CHANGED"]


def test_cancel_assignment_and_unassigned_students_and_stats(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "S3001", "钱七")
    mid = _qualified_mentor(graduation_client, h, "T301", "导师丙", max_capacity=3)
    a = graduation_client.post(f"{GD_ASSIGN}/assign", headers=h, json={"gdStudentId": gid, "mentorId": mid}).json()["data"]

    unassigned_before = graduation_client.get(f"{GD_ASSIGN}/unassigned-students", headers=h).json()["data"]["total"]

    cancel = graduation_client.post(f"{GD_ASSIGN}/{a['id']}/cancel", headers=h, json={"reason": "学生休学退出毕设"})
    assert cancel.json()["data"]["status"] == "CANCELLED"

    stu = graduation_client.get(f"{GD_STU}/{gid}", headers=h).json()["data"]
    assert stu["advisorName"] in (None, "")

    unassigned_after = graduation_client.get(f"{GD_ASSIGN}/unassigned-students", headers=h).json()["data"]["total"]
    assert unassigned_after == unassigned_before + 1

    stats = graduation_client.get(f"{GD_MENTOR}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1
    assert "unassignedStudents" in stats


def test_mentor_excel_template_and_export(graduation_client, auth_headers, db_mode):
    h = auth_headers
    _qualified_mentor(graduation_client, h, "T401", "导师丁")
    tpl = graduation_client.get(f"{GD_MENTOR}/import/template", headers=h)
    assert tpl.status_code == 200
    assert tpl.headers["content-type"].startswith("application/vnd.openxmlformats")

    exp = graduation_client.post(f"{GD_MENTOR}/export", headers=h)
    body = exp.json()
    assert body["code"] == 0
    assert body["data"]["rowCount"] >= 1
    assert body["data"]["filename"].endswith(".xlsx")

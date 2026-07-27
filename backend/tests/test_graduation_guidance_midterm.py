"""毕业设计中心 · 指导过程记录 + 中期检查测试：新增/撤销指导记录 + 频次统计 + 三档结论/整改闭环 + 阶段推进。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_GUIDANCE = "/api/v1/graduation/gd-guidances"
GD_MIDTERM = "/api/v1/graduation/gd-midterms"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent

    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gid))
        stu.stage = "MIDTERM"
        db.commit()
    finally:
        db.close()
    return gid


def test_guidance_create_stats_void(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "GU001", "指导测试生")

    r1 = client.post(f"{GD_GUIDANCE}/{gid}", headers=h, json={"content": "讨论选题方向", "method": "ONLINE"})
    assert r1.json()["code"] == 0
    r2 = client.post(f"{GD_GUIDANCE}/{gid}", headers=h, json={"content": "检查代码进度", "issues": "进度偏慢"})
    assert r2.json()["code"] == 0

    lst = client.get(GD_GUIDANCE, headers=h, params={"gdStudentId": gid}).json()["data"]
    assert lst["total"] == 2

    stats = client.get(f"{GD_GUIDANCE}/stats", headers=h, params={"threshold": 3}).json()["data"]
    assert stats["threshold"] == 3

    gid_record = r1.json()["data"]["id"]
    short = client.post(f"{GD_GUIDANCE}/records/{gid_record}/void", headers=h, json={"reason": "x"})
    assert short.json()["code"] != 0
    voided = client.post(f"{GD_GUIDANCE}/records/{gid_record}/void", headers=h, json={"reason": "记录重复录入需撤销"})
    assert voided.json()["data"]["voided"] is True

    lst2 = client.get(GD_GUIDANCE, headers=h, params={"gdStudentId": gid}).json()["data"]
    assert lst2["total"] == 1


def test_midterm_pass_advances_stage(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "GU101", "中期通过生")
    detail = client.get(f"{GD_MIDTERM}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "PENDING"

    ck = client.post(f"{GD_MIDTERM}/{gid}/check", headers=h, json={"conclusion": "PASS", "comment": "进度正常"})
    assert ck.json()["data"]["status"] == "CHECKED_PASS"

    again = client.post(f"{GD_MIDTERM}/{gid}/check", headers=h, json={"conclusion": "PASS"})
    assert again.json()["code"] != 0  # 非可重新检查状态


def test_midterm_rectify_flow_and_repeat_failure(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "GU201", "整改测试生")

    ck = client.post(f"{GD_MIDTERM}/{gid}/check", headers=h, json={
        "conclusion": "RECTIFY", "comment": "进度滞后", "rectifyDeadline": "2026-08-01"})
    assert ck.json()["data"]["status"] == "RECTIFYING"

    too_early_review = client.post(f"{GD_MIDTERM}/{gid}/rectify/review", headers=h, json={"action": "PASS"})
    assert too_early_review.json()["code"] != 0

    submit = client.post(f"{GD_MIDTERM}/{gid}/rectify", headers=h, json={"content": "已补齐进度并完成阶段目标"})
    assert submit.json()["data"]["status"] == "RECTIFY_SUBMITTED"

    fail_review = client.post(f"{GD_MIDTERM}/{gid}/rectify/review", headers=h, json={"action": "FAIL", "comment": "仍未达标"})
    assert fail_review.json()["data"]["status"] == "RECTIFYING"
    assert fail_review.json()["data"]["rectifyAttempts"] == 1

    submit2 = client.post(f"{GD_MIDTERM}/{gid}/rectify", headers=h, json={"content": "二次整改完成"})
    assert submit2.json()["data"]["status"] == "RECTIFY_SUBMITTED"
    pass_review = client.post(f"{GD_MIDTERM}/{gid}/rectify/review", headers=h, json={"action": "PASS"})
    assert pass_review.json()["data"]["status"] == "RECTIFIED_PASS"

    stats = client.get(f"{GD_MIDTERM}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

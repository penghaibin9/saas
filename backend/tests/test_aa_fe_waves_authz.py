"""13B-FE W3-W5 前端接入波 · 越权红线补齐（每波≥1 越权用例入 CI）。

课程库 / 培养方案 / 教学任务 / 课表 / 成绩 / 毕业预审 写读端点：学生令牌一律 403（require_staff）。
403 发生在鉴权依赖层（早于任何 DB 访问），故与库无关、稳定。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_w3_course_program_student_403(client, db_mode):
    """W3 课程库 / 培养方案：学生令牌 403。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/courses", headers=hdr,
                       json={"courseCode": "X", "courseName": "X"}).status_code == 403
    assert client.get(f"{BASE}/courses", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/programs", headers=hdr,
                       json={"programName": "X"}).status_code == 403
    assert client.get(f"{BASE}/programs", headers=hdr).status_code == 403


def test_w4_task_schedule_student_403(client, db_mode):
    """W4 教学任务 / 课表：学生令牌 403。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/teaching-task-batches/generate", headers=hdr,
                       json={"termId": "1"}).status_code == 403
    assert client.get(f"{BASE}/teaching-task-batches", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/schedule-batches", headers=hdr,
                       json={"termId": "1"}).status_code == 403
    assert client.get(f"{BASE}/schedule-batches", headers=hdr).status_code == 403


def test_w5_grade_graduation_student_403(client, db_mode):
    """W5 成绩 / 预警 / 毕业预审：学生令牌 403。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/grade-tasks", headers=hdr,
                       json={"courseName": "X"}).status_code == 403
    assert client.get(f"{BASE}/grade-views/analysis", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/warnings/scan", headers=hdr).status_code == 403
    assert client.get(f"{BASE}/warnings", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/graduation-audit-batches", headers=hdr,
                       json={"batchName": "X"}).status_code == 403

"""毕业设计 P2：导师对学生评价 + 指导计划签到。

覆盖：happy-path 创建评价/计划/签到；越权导师对非本人指导学生 403。
"""
from __future__ import annotations

from conftest import make_org_class

from app.core.security import create_access_token

GD_EVAL = "/api/v1/graduation/gd-student-evals"
GD_PLAN = "/api/v1/graduation/gd-guidance-plans"
GD_STU = "/api/v1/graduation/gd-students"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
STU = "/api/v1/students"
MAIN = 1000000000000000001


def _gd_student(client, h, no, name, advisor_name=None):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    body = {"studentId": sid}
    if advisor_name:
        body["advisorName"] = advisor_name
    return client.post(GD_STU, headers=h, json=body).json()["data"]["id"]


def _mentor_headers(name="越权导师甲"):
    token = create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "GD_MENTOR",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_student_eval_and_plan_checkin_happy_path(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "P2E001", "评价签到生")

    ev = client.post(f"{GD_EVAL}/{gid}", headers=h, json={
        "period": "中期", "score": 88, "level": "良好", "content": "态度认真，进度正常", "status": "SUBMITTED",
    })
    assert ev.json()["code"] == 0, ev.json()
    assert ev.json()["data"]["status"] == "SUBMITTED"
    assert ev.json()["data"]["score"] == 88

    lst = client.get(GD_EVAL, headers=h, params={"gdStudentId": gid}).json()["data"]
    assert lst["total"] >= 1

    plan = client.post(f"{GD_PLAN}/{gid}", headers=h, json={
        "title": "第3次进度汇报", "content": "提交开题修改稿",
    })
    assert plan.json()["code"] == 0, plan.json()
    plan_id = plan.json()["data"]["id"]
    assert plan.json()["data"]["status"] == "PLANNED"

    ck = client.post(f"{GD_PLAN}/{plan_id}/checkin", headers=h, json={"method": "MANUAL", "note": "现场已完成"})
    assert ck.json()["code"] == 0, ck.json()
    assert ck.json()["data"]["status"] == "CHECKED_IN"
    assert ck.json()["data"]["checkedInBy"]

    dup = client.post(f"{GD_PLAN}/{plan_id}/checkin", headers=h, json={})
    assert dup.json()["code"] != 0


def test_mentor_cannot_eval_out_of_scope_student(client, auth_headers, db_mode):
    """GD_MENTOR 仅能操作 advisor_name=本人 的学生；对他人指导生应 403。"""
    h = auth_headers
    gid = _gd_student(client, h, "P2S403", "他导学生", advisor_name="正式导师乙")
    mh = _mentor_headers("越权导师甲")

    ev = client.post(f"{GD_EVAL}/{gid}", headers=mh, json={
        "score": 70, "level": "合格", "content": "越权评价应被拦",
    })
    assert ev.status_code == 403 or ev.json().get("code") in (403001, 403), ev.text

    plan = client.post(f"{GD_PLAN}/{gid}", headers=mh, json={"title": "越权计划"})
    assert plan.status_code == 403 or plan.json().get("code") in (403001, 403), plan.text


def test_permission_codes_for_p2_guide_paths():
    from app.core.graduation_permissions import graduation_permission_for
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-student-evals/12"
    ) == "graduationDesign.guide.manage"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-guidance-plans/9/checkin"
    ) == "graduationDesign.guide.manage"
    assert graduation_permission_for(
        "GET", "/api/v1/graduation/gd-guidance-plans"
    ) == "graduationDesign.view"

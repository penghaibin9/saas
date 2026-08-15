"""毕业设计 P2：导师对学生评价 + 指导计划签到。

覆盖：happy-path 创建评价/计划/签到；越权导师对非本人指导学生 403；学校端批次上下文显式传递。
"""
from __future__ import annotations

import uuid

from conftest import make_org_class

from app.core.security import create_access_token

GD_EVAL = "/api/v1/graduation/gd-student-evals"
GD_PLAN = "/api/v1/graduation/gd-guidance-plans"
GD_STU = "/api/v1/graduation/gd-students"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_BATCH = "/api/v1/graduation/batches"
STU = "/api/v1/students"
MAIN = 1000000000000000001


def _batch(graduation_client, h):
    suffix = uuid.uuid4().hex[:8]
    r = graduation_client.post(GD_BATCH, headers=h, json={
        "batchName": f"P2评价批次-{suffix}",
        "batchNo": f"P2-EVAL-{suffix}",
        "gradeYear": "2026届",
        "plannedCount": 20,
    }).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _gd_student(graduation_client, h, no, name, batch_id, advisor_name=None):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    body = {"studentId": sid, "batchId": batch_id}
    if advisor_name:
        body["advisorName"] = advisor_name
    return graduation_client.post(GD_STU, headers=h, json=body).json()["data"]["id"]


def _mentor_headers(name="越权导师甲"):
    token = create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "GD_MENTOR",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_student_eval_and_plan_checkin_happy_path(graduation_client, auth_headers, db_mode):
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    gid = _gd_student(graduation_client, h, f"P2E{uuid.uuid4().hex[:6]}", "评价签到生", batch_id)

    ev = graduation_client.post(f"{GD_EVAL}/{gid}", headers=h, params={"batchId": batch_id}, json={
        "period": "中期", "score": 88, "level": "良好", "content": "态度认真，进度正常", "status": "SUBMITTED",
    })
    assert ev.json()["code"] == 0, ev.json()
    assert ev.json()["data"]["status"] == "SUBMITTED"
    assert ev.json()["data"]["score"] == 88

    lst = graduation_client.get(GD_EVAL, headers=h, params={"gdStudentId": gid, "batchId": batch_id}).json()["data"]
    assert lst["total"] >= 1

    plan = graduation_client.post(f"{GD_PLAN}/{gid}", headers=h, params={"batchId": batch_id}, json={
        "title": "第3次进度汇报", "content": "提交开题修改稿",
    })
    assert plan.json()["code"] == 0, plan.json()
    plan_id = plan.json()["data"]["id"]
    assert plan.json()["data"]["status"] == "PLANNED"

    ck = graduation_client.post(f"{GD_PLAN}/{plan_id}/checkin", headers=h, params={"batchId": batch_id}, json={"method": "MANUAL", "note": "现场已完成"})
    assert ck.json()["code"] == 0, ck.json()
    assert ck.json()["data"]["status"] == "CHECKED_IN"
    assert ck.json()["data"]["checkedInBy"]

    dup = graduation_client.post(f"{GD_PLAN}/{plan_id}/checkin", headers=h, params={"batchId": batch_id}, json={})
    assert dup.json()["code"] != 0


def test_mentor_cannot_eval_out_of_scope_student(graduation_client, auth_headers, db_mode):
    """GD_MENTOR 仅能操作 advisor_name=本人 的学生；对他人指导生应 403。"""
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    gid = _gd_student(graduation_client, h, f"P2S{uuid.uuid4().hex[:6]}", "他导学生", batch_id, advisor_name="正式导师乙")
    mh = _mentor_headers("越权导师甲")

    ev = graduation_client.post(f"{GD_EVAL}/{gid}", headers=mh, params={"batchId": batch_id}, json={
        "score": 70, "level": "合格", "content": "越权评价应被拦",
    })
    assert ev.status_code == 403 or ev.json().get("code") in (403001, 403), ev.text

    plan = graduation_client.post(f"{GD_PLAN}/{gid}", headers=mh, params={"batchId": batch_id}, json={"title": "越权计划"})
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

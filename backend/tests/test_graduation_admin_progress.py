"""管理员开工检查（首次使用向导）与“中期检查按导师看”（真库）。"""
from __future__ import annotations

from datetime import datetime, timezone

from test_graduation_auto_identity import MAIN, _batch, _headers, _mentor, _ok, _set_batch_status, _student, _uniq
from test_graduation_teacher_workbench import _db_add, _update_student

from app.models import GraduationMidterm

SETUP = "/api/v1/graduation/setup-check"
BY_MENTOR = "/api/v1/graduation/midterm-by-mentor"


def _user(login, name):
    from app.models import User
    return User(tenant_id=MAIN, login_name=login, real_name=name, password_hash="x" * 20,
                user_type="TEACHER", status="ACTIVE")


def _steps(data):
    return {step["key"]: step for step in data["steps"]}


def test_setup_check_walks_admin_through_first_use(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h, status="DRAFT")
    data = graduation_client.get(SETUP, headers=h, params={"batchId": bid}).json()["data"]
    steps = _steps(data)
    assert [s["key"] for s in data["steps"]] == ["timeline", "students", "mentors", "accounts", "publish", "materials"]
    # 草稿批次：要么已有覆盖全流程的规则（done），要么提示发布时自动生成；绝不能出现「缺少：。」这种空提示
    assert steps["materials"]["detail"] and "缺少：。" not in steps["materials"]["detail"]
    assert steps["materials"]["done"] is True or "发布批次时系统会自动生成" in steps["materials"]["detail"]
    assert steps["students"]["done"] is False and steps["publish"]["done"] is False

    login_a, login_b = _uniq("SA"), _uniq("SB")
    mid_a = _mentor(graduation_client, h, login_a, "开工导师甲")
    mid_b = _mentor(graduation_client, h, login_b, "开工导师乙")
    _db_add(_user(login_a, "开工导师甲"))  # 乙还没有登录账号
    _student(graduation_client, h, bid, mid_a, "开工生一")
    _student(graduation_client, h, bid, mid_b, "开工生二")
    s3 = _student(graduation_client, h, bid, None, "开工生三")

    data = graduation_client.get(SETUP, headers=h, params={"batchId": bid}).json()["data"]
    steps = _steps(data)
    assert steps["students"]["done"] is True and data["counts"]["students"] == 3
    assert steps["mentors"]["done"] is False and "1 名学生没有导师" in steps["mentors"]["detail"]
    assert steps["accounts"]["done"] is False
    assert any("开工导师乙" in name for name in steps["accounts"]["names"])
    assert not any("开工导师甲" in name for name in steps["accounts"]["names"])

    _update_student(s3, mentor_id=mid_a)
    _db_add(_user(login_b, "开工导师乙"))
    _set_batch_status(bid, "RUNNING")
    data = graduation_client.get(SETUP, headers=h, params={"batchId": bid}).json()["data"]
    steps = _steps(data)
    assert steps["mentors"]["done"] and steps["accounts"]["done"] and steps["publish"]["done"]
    assert data["doneCount"] >= 4

    # 普通老师没有学生管理权限，看不到开工检查
    assert not _ok(graduation_client.get(SETUP, headers=_headers(login_a), params={"batchId": bid}))


def test_midterm_by_mentor_counts_and_teacher_sees_only_self(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("MA"), _uniq("MB")
    mid_a = _mentor(graduation_client, h, login_a, "中期导师甲")
    mid_b = _mentor(graduation_client, h, login_b, "中期导师乙")
    s1 = _student(graduation_client, h, bid, mid_a, "未检查生")
    s4 = _student(graduation_client, h, bid, mid_a, "已检查生")
    s2 = _student(graduation_client, h, bid, mid_b, "整改生")
    _update_student(s1, stage="MIDTERM")
    _update_student(s4, stage="MIDTERM")
    _update_student(s2, stage="MIDTERM")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _db_add(
        GraduationMidterm(tenant_id=MAIN, gd_student_id=s4, batch_id=bid, status="CHECKED_PASS", checked_at=now),
        GraduationMidterm(tenant_id=MAIN, gd_student_id=s2, batch_id=bid, status="RECTIFY_SUBMITTED", checked_at=now),
    )

    resp = graduation_client.get(BY_MENTOR, headers=h, params={"batchId": bid})
    assert _ok(resp), resp.json()
    data = resp.json()["data"]
    rows = {row["mentorName"]: row for row in data["rows"]}
    a, b = rows["中期导师甲"], rows["中期导师乙"]
    assert (a["total"], a["checked"], a["pendingCheck"], a["pendingReview"]) == (2, 1, 1, 0)
    assert (b["total"], b["checked"], b["pendingCheck"], b["pendingReview"]) == (1, 1, 0, 1)
    assert [s["gdStudentId"] for s in a["pendingStudents"]] == [str(s1)]
    assert b["pendingStudents"][0]["statusLabel"] == "整改待复核"
    assert data["summary"]["pendingCheck"] == 1 and data["summary"]["pendingReview"] == 1
    assert data["summary"]["mentorsWithPending"] == 2

    # 普通老师（自动导师身份）只看到自己这一行
    mine = graduation_client.get(BY_MENTOR, headers=_headers(login_a), params={"batchId": bid})
    assert _ok(mine), mine.json()
    assert [row["mentorName"] for row in mine.json()["data"]["rows"]] == ["中期导师甲"]

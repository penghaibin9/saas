"""老师毕设身份按业务关系自动生效：普通老师账号无需手工授予/切换毕设角色。

全部走真库（db_mode）。覆盖：
- 导师台账（工号 = 登录名）+ 进行中批次 → 普通老师可看自己指导的学生，看不到别人的；
- 同时是导师和评阅人时，按与目标学生的关系选身份；
- 关系撤销（导师台账停用、批次归档）→ 下一次请求立即失效；
- 管理员、学生永远不被替换身份；自动权限不进入基础权限、不能再授权；
- 教师小程序毕设接口同样生效。
"""
from __future__ import annotations

import uuid

import pytest
from conftest import make_org_class

from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import GraduationBatch, GraduationMentor, GraduationStudent
from app.modules.graduation.services import graduation_auto_identity as auto

GD_STU = "/api/v1/graduation/gd-students"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_REVIEW = "/api/v1/graduation/gd-reviews"
STU = "/api/v1/students"
BATCH = "/api/v1/graduation/batches"
MOBILE = "/api/v1/mobile"
MAIN = 1000000000000000001


def _uniq(prefix="AI"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _ok(resp):
    body = resp.json()
    return resp.status_code < 400 and body.get("code") == 0


def _batch(client, h, status="RUNNING"):
    bid = client.post(BATCH, headers=h, json={
        "batchName": _uniq("批"), "batchNo": _uniq("BN"), "gradeYear": "2026届", "plannedCount": 20,
    }).json()["data"]["id"]
    _set_batch_status(bid, status)
    return bid


def _set_batch_status(bid, status):
    db = get_sessionmaker()()
    try:
        db.get(GraduationBatch, int(bid)).status = status
        db.commit()
    finally:
        db.close()


def _mentor(client, h, teacher_no, name):
    mid = client.post(GD_MENTOR, headers=h, json={
        "teacherNo": teacher_no, "teacherName": name, "maxCapacity": 8,
    }).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    return int(mid)


def _set_mentor_status(mid, status):
    db = get_sessionmaker()()
    try:
        db.get(GraduationMentor, int(mid)).qualification_status = status
        db.commit()
    finally:
        db.close()


def _student(client, h, bid, mentor_id=None, name="自动身份生"):
    sid = client.post(STU, headers=h, json={
        "studentNo": _uniq("S"), "realName": name, "classId": make_org_class(),
    }).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    if mentor_id is not None:
        db = get_sessionmaker()()
        try:
            db.get(GraduationStudent, int(gid)).mentor_id = int(mentor_id)
            db.commit()
        finally:
            db.close()
    return int(gid)


def _teacher_user(login, role="TEACHER", user_type="TEACHER", real_name="普通老师"):
    return {
        "userId": f"u-{login}", "realName": real_name, "loginName": login, "userType": user_type,
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": role,
    }


def _headers(login, role="TEACHER", client_type="WEB", real_name="普通老师"):
    claims = {**_teacher_user(login, role, real_name=real_name), "clientType": client_type}
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _ids(data):
    items = data.get("items", data.get("records", [])) if isinstance(data, dict) else data
    return {str(x.get("gdStudentId") or x.get("id")) for x in items or []}


def test_plain_teacher_with_mentor_ledger_sees_only_own_students(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("TA"), _uniq("TB")
    mid_a = _mentor(graduation_client, h, login_a, "导师甲")
    mid_b = _mentor(graduation_client, h, login_b, "导师乙")
    own = _student(graduation_client, h, bid, mid_a, "甲的学生")
    other = _student(graduation_client, h, bid, mid_b, "乙的学生")

    th = _headers(login_a)  # 普通老师岗位，没有任何毕设角色
    assert _ok(graduation_client.get(f"{GD_STU}/{own}", headers=th))
    assert not _ok(graduation_client.get(f"{GD_STU}/{other}", headers=th))
    listed = graduation_client.get(GD_STU, headers=th, params={"batchId": bid, "page": 1, "pageSize": 50})
    assert _ok(listed), listed.json()
    ids = _ids(listed.json()["data"])
    assert str(own) in ids and str(other) not in ids

    # 没有导师台账的普通老师：什么毕设数据都看不到
    stranger = _headers(_uniq("TX"))
    assert not _ok(graduation_client.get(f"{GD_STU}/{own}", headers=stranger))


def test_mentor_and_reviewer_identity_chosen_by_relation(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("RA"), _uniq("RB")
    mid_a = _mentor(graduation_client, h, login_a, "导师丙")
    mid_b = _mentor(graduation_client, h, login_b, "导师丁")
    reviewed = _student(graduation_client, h, bid, mid_a, "被评阅生")
    unrelated = _student(graduation_client, h, bid, mid_a, "无关生")
    own_b = _student(graduation_client, h, bid, mid_b, "丁的学生")

    assigned = graduation_client.post(f"{GD_REVIEW}/assign", headers=h, json={
        "gdStudentId": str(reviewed), "reviewerMentorId": mid_b,
    })
    assert _ok(assigned), assigned.json()

    th = _headers(login_b)
    assert _ok(graduation_client.get(f"{GD_STU}/{own_b}", headers=th))       # 以指导教师身份
    assert _ok(graduation_client.get(f"{GD_STU}/{reviewed}", headers=th))    # 以评阅教师身份
    assert not _ok(graduation_client.get(f"{GD_STU}/{unrelated}", headers=th))

    user = _teacher_user(login_b)
    assert auto.held_identities(user) == frozenset({"GD_MENTOR", "GD_REVIEWER"})
    chosen = auto.overlay_for_request(
        dict(user), "graduationDesign.student.view",
        path_params={"record_id": str(reviewed), "__path__": f"{GD_STU}/{reviewed}"},
    )
    assert chosen == "GD_REVIEWER"
    chosen = auto.overlay_for_request(
        dict(user), "graduationDesign.student.view",
        path_params={"record_id": str(own_b), "__path__": f"{GD_STU}/{own_b}"},
    )
    assert chosen == "GD_MENTOR"
    # 评阅提交只有评阅身份能做
    assert auto.overlay_for_request(dict(user), "graduationDesign.review.submit") == "GD_REVIEWER"

    # 批次归档后评阅关系失效（导师身份因台账已认定仍在，但看不到非本人指导的学生）
    _set_batch_status(bid, "ARCHIVED")
    assert auto.held_identities(_teacher_user(login_b)) == frozenset({"GD_MENTOR"})
    assert not _ok(graduation_client.get(f"{GD_STU}/{reviewed}", headers=th))


def test_identity_revoked_on_next_request(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login = _uniq("TR")
    mid = _mentor(graduation_client, h, login, "导师戊")
    own = _student(graduation_client, h, bid, mid, "戊的学生")
    th = _headers(login)
    assert _ok(graduation_client.get(f"{GD_STU}/{own}", headers=th))

    _set_mentor_status(mid, "DISABLED")
    assert auto.held_identities(_teacher_user(login)) == frozenset()
    assert not _ok(graduation_client.get(f"{GD_STU}/{own}", headers=th))

    # 台账未认定、但在进行中批次里被分配了学生 → 仍是指导教师
    _set_mentor_status(mid, "PENDING_REVIEW")
    assert auto.held_identities(_teacher_user(login)) == frozenset({"GD_MENTOR"})
    assert _ok(graduation_client.get(f"{GD_STU}/{own}", headers=th))
    # 学生改派给别人后，未认定的老师不再有指导身份
    db = get_sessionmaker()()
    try:
        db.get(GraduationStudent, int(own)).mentor_id = None
        db.commit()
    finally:
        db.close()
    assert auto.held_identities(_teacher_user(login)) == frozenset()
    assert not _ok(graduation_client.get(f"{GD_STU}/{own}", headers=th))


@pytest.mark.parametrize("role,user_type", [
    ("GRADUATION_ADMIN", "TEACHER"), ("GD_COLLEGE_ADMIN", "TEACHER"), ("GD_MAJOR_ADMIN", "TEACHER"),
    ("SCHOOL_ADMIN", "ADMIN"), ("STUDENT", "STUDENT"), ("PLATFORM_OPS", "ADMIN"),
])
def test_admins_students_and_platform_never_overlaid(graduation_client, auth_headers, db_mode, role, user_type):
    h = auth_headers
    login = _uniq("NV")
    _mentor(graduation_client, h, login, "兼任导师")
    user = _teacher_user(login, role=role, user_type=user_type)
    assert auto.is_eligible(user) is False
    assert auto.auto_permission_patterns(user) == set()
    assert auto.overlay_for_request(user, "graduationDesign.student.view") is None
    assert user["currentRoleCode"] == role and "gdAutoIdentity" not in user


def test_auto_permissions_are_effective_but_not_base_or_delegable(graduation_client, auth_headers, db_mode):
    from app.core.exceptions import AppException
    from app.core.permissions import (
        assert_delegable_permission_codes, get_base_permission_patterns, get_effective_permission_patterns,
    )
    h = auth_headers
    login = _uniq("TD")
    _mentor(graduation_client, h, login, "导师己")
    user = _teacher_user(login)
    effective = set(get_effective_permission_patterns(user))
    base = set(get_base_permission_patterns(user))
    assert "graduationDesign.proposal.review" in effective
    assert not any(p.startswith("graduationDesign.") for p in base)
    extra = auto.auto_permission_patterns(user)
    assert extra and all(p.startswith("graduationDesign.") for p in extra)  # 不带出工作台等其它模块权限
    with pytest.raises(AppException):
        assert_delegable_permission_codes(user, ["graduationDesign.proposal.review"])
    assert auto.describe(user)["labels"] == ["指导教师"]


def test_mobile_teacher_graduation_works_without_manual_role(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("MA"), _uniq("MB")
    mid_a = _mentor(graduation_client, h, login_a, "导师庚")
    mid_b = _mentor(graduation_client, h, login_b, "导师辛")
    own = _student(graduation_client, h, bid, mid_a, "庚的学生")
    other = _student(graduation_client, h, bid, mid_b, "辛的学生")
    db = get_sessionmaker()()
    try:
        for gid, advisor in ((own, "导师庚"), (other, "导师辛")):
            row = db.get(GraduationStudent, gid)
            row.stage = "MIDTERM"
            row.advisor_name = advisor  # 中期详情沿用历史的指导范围核对（按导师姓名）
        db.commit()
    finally:
        db.close()
    th = _headers(login_a, client_type="MP", real_name="导师庚")

    queue = graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/queue", headers=th)
    assert _ok(queue), queue.json()
    queued = _ids(queue.json()["data"])
    assert str(own) in queued and str(other) not in queued
    assert _ok(graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/{own}", headers=th))
    assert not _ok(graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/{other}", headers=th))
    stranger = _headers(_uniq("MX"), client_type="MP")
    assert not _ok(graduation_client.get(f"{MOBILE}/teacher/graduation/midterm/queue", headers=stranger))


def test_mentor_who_is_also_judge_defense_queue_uses_judge_identity(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(graduation_client, h)
    login = _uniq("DJ")
    mid = _mentor(graduation_client, h, login, "导师壬")
    _student(graduation_client, h, bid, mid, "壬的学生")
    grp = graduation_client.post("/api/v1/graduation/defense-groups", headers=h, params={"batchId": bid}, json={
        "groupName": _uniq("组"), "batchId": bid, "location": "C301",
        "chairMentorId": mid, "memberMentorIds": [], "secretary": "秘书",
    })
    assert _ok(grp), grp.json()
    user = _teacher_user(login)
    assert auto.held_identities(user) == frozenset({"GD_MENTOR", "GD_DEFENSE_EXPERT"})
    # 没有目标学生：答辩类动作优先评委身份，否则待评分只剩自己指导的学生
    assert auto.overlay_for_request(dict(user), "graduationDesign.defense.view") == "GD_DEFENSE_EXPERT"
    # 前端明确说明身份（老师工作台/小程序）时按说明，且必须真的持有
    assert auto.overlay_for_request(dict(user), "graduationDesign.defense.view", hint="GD_MENTOR") == "GD_MENTOR"
    assert auto.overlay_for_request(dict(user), "graduationDesign.defense.view", hint="GD_REVIEWER") == "GD_DEFENSE_EXPERT"
    # 指导类动作不受影响
    assert auto.overlay_for_request(dict(user), "graduationDesign.proposal.review") == "GD_MENTOR"
    pending = graduation_client.get(f"{MOBILE}/teacher/graduation/defense/pending",
                                    headers=_headers(login, client_type="MP"))
    assert _ok(pending), pending.json()


def test_mobile_midterm_scope_uses_mentor_id_not_same_name(graduation_client, auth_headers, db_mode):
    """两位同名导师：小程序中期检查只能看/检查自己 mentor_id 名下的学生。

    注意：测试客户端包装器会按姓名把小程序教师令牌改写成同名导师的工号（历史用例的便利），
    这里必须绕过它（直接用底层 TestClient），才能真实验证“按工号/ID 而不是按姓名”。
    """
    h = auth_headers
    raw = graduation_client._wrapped
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("SNA"), _uniq("SNB")
    mid_a = _mentor(graduation_client, h, login_a, "张同名")
    mid_b = _mentor(graduation_client, h, login_b, "张同名")
    own_a = _student(graduation_client, h, bid, mid_a, "同名甲的学生")
    own_b = _student(graduation_client, h, bid, mid_b, "同名乙的学生")
    db = get_sessionmaker()()
    try:
        for gid in (own_a, own_b):
            row = db.get(GraduationStudent, gid)
            row.stage = "MIDTERM"
            row.advisor_name = "张同名"  # 快照姓名相同，只有 mentor_id 不同
        db.commit()
    finally:
        db.close()
    ha = _headers(login_a, client_type="MP", real_name="张同名")
    params = {"batchId": bid}
    queue = raw.get(f"{MOBILE}/teacher/graduation/midterm/queue", headers=ha, params=params)
    assert _ok(queue), queue.json()
    assert _ids(queue.json()["data"]) == {str(own_a)}
    mine = raw.get(f"{MOBILE}/teacher/graduation/midterm/{own_a}", headers=ha, params=params)
    assert _ok(mine), mine.json()
    denied = raw.get(f"{MOBILE}/teacher/graduation/midterm/{own_b}", headers=ha, params=params)
    assert not _ok(denied), denied.json()
    check = raw.post(f"{MOBILE}/teacher/graduation/midterm/{own_b}/check", headers=ha, params=params,
                     json={"conclusion": "PASS", "comment": "越权检查应被拒绝"})
    assert not _ok(check), check.json()
    ok_check = raw.post(f"{MOBILE}/teacher/graduation/midterm/{own_a}/check", headers=ha, params=params,
                        json={"conclusion": "PASS", "comment": "本人学生检查通过"})
    assert _ok(ok_check), ok_check.json()


def test_material_record_paths_pick_identity_of_the_students_relation(graduation_client, auth_headers, db_mode):
    """文件/成果/开题/材料记录的路径里只有记录号：既是导师又是评阅人的老师，应按记录所属学生选身份。

    否则评阅老师点开自己评阅的论文时，被默认当成指导教师，被数据范围拒绝（走查中发现的真实问题）。
    """
    from datetime import datetime, timezone

    from app.models import GraduationFinal

    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("FA"), _uniq("FB")
    mid_a = _mentor(graduation_client, h, login_a, "导师癸")
    mid_b = _mentor(graduation_client, h, login_b, "导师子")
    reviewed = _student(graduation_client, h, bid, mid_a, "被评阅生2")
    own_b = _student(graduation_client, h, bid, mid_b, "子的学生")
    assert _ok(graduation_client.post(f"{GD_REVIEW}/assign", headers=h, json={
        "gdStudentId": str(reviewed), "reviewerMentorId": mid_b,
    }))

    finals = {}
    db = get_sessionmaker()()
    try:
        for gid in (reviewed, own_b):
            row = GraduationFinal(
                tenant_id=MAIN, gd_student_id=int(gid), final_type="定稿", version="v1",
                submit_at=datetime.now(timezone.utc), plagiarism_rate=None, plagiarism_status="未检测",
                attachments_json=[], status="PENDING_REVIEW", active_key=f"pending:{gid}", created_by=1,
            )
            db.add(row)
            db.flush()
            finals[gid] = int(row.id)
        db.commit()
    finally:
        db.close()

    user = _teacher_user(login_b)
    base = "/api/v1/graduation/material-center/finals"
    # 评阅的那个学生：按评阅教师身份；自己指导的学生：按指导教师身份
    assert auto.overlay_for_request(
        dict(user), "graduationDesign.student.view",
        path_params={"final_id": str(finals[reviewed]), "__path__": f"{base}/{finals[reviewed]}/versions"},
    ) == "GD_REVIEWER"
    assert auto.overlay_for_request(
        dict(user), "graduationDesign.student.view",
        path_params={"final_id": str(finals[own_b]), "__path__": f"{base}/{finals[own_b]}/versions"},
    ) == "GD_MENTOR"
    # 查不到记录时不报错，退回默认顺序
    assert auto.overlay_for_request(
        dict(user), "graduationDesign.student.view",
        path_params={"final_id": "999999999", "__path__": f"{base}/999999999/versions"},
    ) == "GD_MENTOR"

"""答辩组部分 ID 回填修复：update 保留姓名快照；ID∪姓名双通道；confirm 兼容；stats 传 batchId。"""
from __future__ import annotations

import uuid

from app.core.context import set_current_user
from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.models import GraduationDefenseGroup, GraduationDefenseScore, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import can_access_student
from app.modules.graduation.services import graduation_identity as gid

DG = "/api/v1/graduation/defense-groups"
GD_STU = "/api/v1/graduation/gd-students"
GD_MENTOR = "/api/v1/graduation/gd-mentors"
GD_SCORE = "/api/v1/graduation/gd-defense-scores"
STU = "/api/v1/students"
BATCH = "/api/v1/graduation/batches"
MAIN = 1000000000000000001


def _uniq(prefix="FIX"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(client, h):
    return client.post(BATCH, headers=h, json={
        "batchName": _uniq("批"), "batchNo": _uniq("BN"),
        "gradeYear": "2026届", "plannedCount": 20,
    }).json()["data"]["id"]


def _mentor(client, h, teacher_no, teacher_name):
    mid = client.post(GD_MENTOR, headers=h, json={
        "teacherNo": teacher_no, "teacherName": teacher_name, "maxCapacity": 8,
    }).json()["data"]["id"]
    client.post(f"{GD_MENTOR}/{mid}/review", headers=h, json={"action": "APPROVE"})
    return mid


def test_update_without_ids_preserves_name_snapshots(client, auth_headers, db_mode):
    """编辑时未传 mentorId：保留原姓名快照，不清空。"""
    h = auth_headers
    bid = _batch(client, h)
    created = client.post(DG, headers=h, json={
        "groupName": _uniq("名组"), "batchId": bid, "location": "C101",
        "chair": "历史主席", "secretary": "历史秘书", "members": ["历史评委甲", "历史评委乙"],
    }).json()
    assert created["code"] == 0, created
    gid_ = created["data"]["id"]
    assert created["data"]["chair"] == "历史主席"
    assert created["data"]["secretary"] == "历史秘书"

    # 仅改地点 / 组名；不传 ID、不传姓名字段（或传 null ID）
    updated = client.put(f"{DG}/{gid_}", headers=h, json={
        "groupName": created["data"]["groupName"],
        "location": "C202",
        "chairMentorId": None,
        "secretaryMentorId": None,
    }).json()
    assert updated["code"] == 0, updated
    assert updated["data"]["chair"] == "历史主席"
    assert updated["data"]["secretary"] == "历史秘书"
    names = {m.get("name") if isinstance(m, dict) else m for m in (updated["data"]["members"] or [])}
    assert "历史评委甲" in names and "历史评委乙" in names


def test_partial_id_panel_name_only_chair_can_access(client, auth_headers, db_mode):
    """组内部分席位有 ID、主席仅姓名：姓名主席可访问；不得冒充有 ID 席位。"""
    h = auth_headers
    bid = _batch(client, h)
    no_m = _uniq("TM")
    mid = _mentor(client, h, no_m, "有ID评委")
    grp = client.post(DG, headers=h, json={
        "groupName": _uniq("混组"), "batchId": bid, "location": "D1",
        "chair": "仅姓名主席", "memberMentorIds": [int(mid)],
        "secretary": "秘书快照",
    }).json()["data"]
    assert grp["chair"] == "仅姓名主席"
    assert grp["chairMentorId"] in (None, "")
    assert any(str(m.get("mentorId")) == str(mid) for m in grp["members"])

    sid = client.post(STU, headers=h, json={"studentNo": _uniq("S"), "realName": "混组生"}).json()["data"]["id"]
    gsid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gsid))
        stu.defense_group_id = int(grp["id"])
        stu.stage = "DEFENSE"
        db.commit()

        set_current_user({
            "currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER",
            "realName": "仅姓名主席", "loginName": _uniq("chair-no"), "tenantId": MAIN,
        })
        assert can_access_student(db, stu) is True

        # 同名冒充有 ID 评委：无对应 mentor 工号 → 拒绝
        set_current_user({
            "currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER",
            "realName": "有ID评委", "loginName": _uniq("fake"), "tenantId": MAIN,
        })
        assert can_access_student(db, stu) is False

        # 真正 ID 评委
        set_current_user({
            "currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER",
            "realName": "有ID评委", "loginName": no_m, "tenantId": MAIN,
        })
        assert can_access_student(db, stu) is True
    finally:
        set_current_user(None)
        db.close()


def test_confirm_accepts_name_only_score_rows_on_partial_id_panel(client, auth_headers, db_mode):
    """部分席位有 ID 时：历史仅姓名评分行仍可确认（name/id 任一齐）。"""
    h = auth_headers
    bid = _batch(client, h)
    mid = _mentor(client, h, _uniq("TJ"), "ID评委")
    grp = client.post(DG, headers=h, json={
        "groupName": _uniq("确认组"), "batchId": bid,
        "chair": "姓名主席", "memberMentorIds": [int(mid)],
    }).json()["data"]
    sid = client.post(STU, headers=h, json={"studentNo": _uniq("S"), "realName": "确认生"}).json()["data"]["id"]
    gsid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]

    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(gsid))
        stu.defense_group_id = int(grp["id"])
        stu.stage = "DEFENSE"
        db.add(GraduationDefenseScore(
            tenant_id=MAIN, gd_student_id=int(gsid), defense_group_id=int(grp["id"]),
            judge_name="姓名主席", score=88, round_no=1, status="SCORED",
            judge_mentor_id=None,
        ))
        db.add(GraduationDefenseScore(
            tenant_id=MAIN, gd_student_id=int(gsid), defense_group_id=int(grp["id"]),
            judge_name="ID评委", score=90, round_no=1, status="SCORED",
            judge_mentor_id=int(mid),
        ))
        db.commit()
    finally:
        db.close()

    ok = client.post(f"{GD_SCORE}/{gsid}/confirm", headers=h).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["judgeCount"] == 2


def test_mixed_panel_update_keeps_name_only_members(client, auth_headers, db_mode):
    """部分评委已绑 ID、部分仅姓名：再保存（只带 memberMentorIds）不得丢掉姓名席位。"""
    h = auth_headers
    bid = _batch(client, h)
    mid = _mentor(client, h, _uniq("TMIX"), "ID评委")
    created = client.post(DG, headers=h, json={
        "groupName": _uniq("混存组"), "batchId": bid,
        "chair": "混存主席",
        "members": ["仅姓名评委", {"mentorId": int(mid), "name": "ID评委"}],
    }).json()
    assert created["code"] == 0, created
    gid_ = created["data"]["id"]
    # 模拟前端只传已选 ID（旧行为会清空仅姓名评委）
    updated = client.put(f"{DG}/{gid_}", headers=h, json={
        "groupName": created["data"]["groupName"],
        "location": "E101",
        "memberMentorIds": [int(mid)],
    }).json()
    assert updated["code"] == 0, updated
    names = set()
    ids = set()
    for m in (updated["data"]["members"] or []):
        if isinstance(m, dict):
            if m.get("name"):
                names.add(m["name"])
            if m.get("mentorId"):
                ids.add(str(m["mentorId"]))
        elif m:
            names.add(str(m))
    assert "仅姓名评委" in names
    assert str(mid) in ids


def test_stats_endpoints_accept_batch_id(client, auth_headers, db_mode):
    h = auth_headers
    bid = _batch(client, h)
    paths = [
        "/api/v1/graduation/gd-guidances/stats",
        "/api/v1/graduation/gd-midterms/stats",
        "/api/v1/graduation/gd-plagiarism/stats",
        "/api/v1/graduation/gd-reviews/stats",
        "/api/v1/graduation/gd-defense-scores/stats",
        "/api/v1/graduation/gd-grades/stats",
        "/api/v1/graduation/gd-peer-reviews/stats",
    ]
    for path in paths:
        r = client.get(path, headers=h, params={"batchId": bid}).json()
        assert r["code"] == 0, (path, r)
        assert r["data"].get("batchId") == str(bid), (path, r["data"])


def test_score_row_covers_seat_helpers():
    class Row:
        def __init__(self, status, name, mid=None):
            self.status = status
            self.judge_name = name
            self.judge_mentor_id = mid

    seat_id = {"mentorId": 7, "name": "甲"}
    seat_name = {"mentorId": None, "name": "乙"}
    assert gid.score_row_covers_seat(Row("SCORED", "甲", 7), seat_id)
    assert gid.score_row_covers_seat(Row("SCORED", "甲", None), seat_id)  # 历史姓名行覆盖有 ID 席
    assert gid.score_row_covers_seat(Row("SCORED", "乙", None), seat_name)
    assert not gid.score_row_covers_seat(Row("PENDING", "乙", None), seat_name)
    assert gid.user_matches_judge_seat(seat_name, mentor=None, real_name="乙")
    assert not gid.user_matches_judge_seat(seat_id, mentor=None, real_name="甲")

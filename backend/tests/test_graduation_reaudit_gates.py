"""毕业设计复审缺口回归：任务书/阶段门禁、答辩确认权限、资格归档锁。"""
from __future__ import annotations

from app.core.graduation_permissions import graduation_permission_for


GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"


def test_defense_confirm_and_second_require_manage_permission():
    assert graduation_permission_for("POST", "/api/v1/graduation/gd-defense-scores/1/confirm") == "graduationDesign.defense.manage"
    assert graduation_permission_for("POST", "/api/v1/graduation/gd-defense-scores/1/second-defense") == "graduationDesign.defense.manage"
    assert graduation_permission_for("POST", "/api/v1/graduation/gd-defense-scores/entry") == "graduationDesign.defense.score"


def test_midterm_allows_final_submit_ignores_lone_conclusion():
    from types import SimpleNamespace
    from app.modules.graduation.services.graduation_service import midterm_allows_final_submit

    assert midterm_allows_final_submit(None) is False
    assert midterm_allows_final_submit(SimpleNamespace(status="RECTIFYING", conclusion="PASS")) is False
    assert midterm_allows_final_submit(SimpleNamespace(status="CHECKED_PASS", conclusion="PASS")) is True
    assert midterm_allows_final_submit(SimpleNamespace(status="RECTIFIED_PASS", conclusion="RECTIFY")) is True


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_proposal_approve_does_not_skip_taskbook(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationProposal, GraduationStudent, GraduationTaskBook

    h = auth_headers
    gid = _gd_student(client, h, "RV-TB-01", "任务书门禁生")
    # 直接造：选题已定、任务书未确认、开题待审
    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        s.topic_id = 1
        s.topic_title = "测试题"
        s.stage = "TASKBOOK_CONFIRM"
        s.advisor_name = "导师甲"
        prop = GraduationProposal(
            tenant_id=s.tenant_id, gd_student_id=s.id, version="v1",
            background="背景" * 3, plan="方案" * 3, outcome="成果",
            status="PENDING_REVIEW",
        )
        db.add(prop)
        db.add(GraduationTaskBook(
            tenant_id=s.tenant_id, gd_student_id=s.id, taskbook_version=1,
            status="PENDING_CONFIRM", objective="目标", content="内容", history_json=[],
        ))
        db.commit()
        pid = str(prop.id)
    finally:
        db.close()

    ok = client.post(f"/api/v1/graduation/proposals/{pid}/review", headers=h,
                     json={"action": "APPROVE", "comment": ""}).json()
    assert ok["code"] == 0

    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        assert s.stage == "TASKBOOK_CONFIRM"
    finally:
        db.close()


def test_advance_taskbook_requires_confirmed(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent

    h = auth_headers
    gid = _gd_student(client, h, "RV-ADV-01", "推进门禁生")
    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        s.stage = "TASKBOOK_CONFIRM"
        s.advisor_name = "导师甲"
        db.commit()
    finally:
        db.close()

    bad = client.post(f"{GD_STU}/{gid}/stage", headers=h, json={"action": "ADVANCE", "reason": "跳过确认"}).json()
    assert bad["code"] != 0


def test_midterm_blocked_in_guiding(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent

    h = auth_headers
    gid = _gd_student(client, h, "RV-MID-01", "中期门禁生")
    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        s.stage = "GUIDING"
        s.advisor_name = "导师甲"
        db.commit()
    finally:
        db.close()

    bad = client.post(f"/api/v1/graduation/gd-midterms/{gid}/check", headers=h,
                      json={"conclusion": "PASS", "comment": "提前中期"}).json()
    assert bad["code"] != 0


def test_grad_qual_blocked_when_archived(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent

    h = auth_headers
    gid = _gd_student(client, h, "RV-GQ-01", "资格归档生")
    db = get_sessionmaker()()
    try:
        s = db.get(GraduationStudent, int(gid))
        s.stage = "ARCHIVED"
        db.commit()
    finally:
        db.close()

    bad = client.post(f"{GD_STU}/{gid}/grad-qual", headers=h,
                      json={"status": "PASS", "note": "归档后改", "reason": "不应允许"}).json()
    assert bad["code"] != 0

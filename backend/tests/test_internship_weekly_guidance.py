"""P1-Stage2 · 周报 owner 批阅 + 指导记录 + 教师巡访（数据范围 + owner 写校验 + 整改跟进 + 审计 + 导出权限）。

- 周报：导师只能批阅本人指导学生的周报（跨导师 → 403）。
- 指导记录/巡访：list 按数据范围收敛；create/void/rectify 需 owner；学生一律 403（require_staff 门禁）。
- 巡访整改：有安全隐患 → rectify_status=PENDING，可跟进 PENDING→DONE，说明必填并写审计。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-STU", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """记录 A(刘强) / B(王芳) 各挂 1 条待批周报；返回 {record_id, report_id}。"""
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile, User, WeeklyReport
    db = get_sessionmaker()()
    ids = {}
    try:
        b = InternshipBatch(tenant_id=TID, batch_name="周报指导测试批次",
                            batch_no=f"WGB-{uuid4().hex[:8]}", status="RUNNING", planned_count=5)
        db.add(b); db.flush()
        ids["batch"] = b.id
        for no, name, adv, key in [("WG-A", "甲", "刘强", "a"), ("WG-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            db.add(User(tenant_id=TID, login_name=no, real_name=name, password_hash="test",
                        user_type="STUDENT", status="ACTIVE"))
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE", batch_id=b.id)
            db.add(r); db.flush()
            w = WeeklyReport(tenant_id=TID, internship_id=r.id, week_number=3, word_count=800,
                             report_version=1, submitted_at=datetime.utcnow(), status="PENDING_REVIEW")
            db.add(w); db.flush()
            ids[f"rec_{key}"] = r.id
            ids[f"rep_{key}"] = w.id
        db.commit()
        return ids
    finally:
        db.close()


# ══════════════ 周报 owner 批阅 ══════════════

def test_weekly_review_cross_mentor_403(client, db_mode):
    ids = _seed(db_mode)
    # 刘强 批阅 王芳 学生的周报 → 403
    r = client.post(f"{INT}/reports/{ids['rep_b']}/review",
                    json={"action": "APPROVE", "comment": ""}, headers=_mentor("刘强"))
    assert r.status_code == 403


def test_weekly_review_own_ok(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(f"{INT}/reports/{ids['rep_a']}/review",
                    json={"action": "APPROVE", "comment": "", "expectedVersion": 0}, headers=_mentor("刘强"))
    assert r.status_code == 200 and r.json()["code"] == 0, r.json()
    assert r.json()["data"]["status"] == "APPROVED"


def test_weekly_export_and_remind_are_real(client, db_mode):
    ids = _seed(db_mode)
    exported = client.post(f"{INT}/reports/export", headers=_mentor("刘强"),
                           params={"batchId": ids["batch"]}).json()["data"]
    assert exported["rowCount"] == 1
    reminded = client.post(f"{INT}/reports/{ids['rep_a']}/remind",
                           json={"channel": "站内消息"}, headers=_mentor("刘强"))
    assert reminded.status_code == 200 and reminded.json()["data"]["reminded"] is True
    duplicate = client.post(f"{INT}/reports/{ids['rep_a']}/remind",
                            json={"channel": "站内消息"}, headers=_mentor("刘强"))
    assert duplicate.json()["code"] != 0
    from app.db.session import get_sessionmaker
    from app.models import UnifiedMessage
    db = get_sessionmaker()()
    try:
        assert db.query(UnifiedMessage).filter_by(source_module="internship",
                                                   source_biz_id=ids["rep_a"]).count() == 1
    finally:
        db.close()


# ══════════════ 指导记录 ══════════════

def test_guidance_create_owner_and_scope(client, db_mode):
    ids = _seed(db_mode)
    # 刘强 对本人学生（rec_a）新增 → 200
    ok = client.post(f"{INT}/guidances",
                     json={"internshipId": str(ids["rec_a"]), "method": "ONSITE",
                           "content": "已到岗指导，岗位匹配良好"}, headers=_mentor("刘强"))
    assert ok.status_code == 200 and ok.json()["code"] == 0
    # 刘强 对 王芳 学生（rec_b）新增 → 403（owner）
    no = client.post(f"{INT}/guidances",
                     json={"internshipId": str(ids["rec_b"]), "content": "越权"}, headers=_mentor("刘强"))
    assert no.status_code == 403
    # 王芳 也建一条到 rec_b
    client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_b"]), "content": "王芳指导"},
                headers=_mentor("王芳"))
    # 数据范围：管理员看 2、刘强看 1
    assert client.get(f"{INT}/guidances", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["total"] == 2
    assert client.get(f"{INT}/guidances", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 1
    stats = client.get(f"{INT}/guidances/stats", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]
    assert stats["studentCount"] == 1 and stats["totalCount"] == 1
    plans = client.get(f"{INT}/guidance-plans", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]
    assert plans["total"] == 1 and plans["items"][0]["studentNo"] == "WG-A"
    exported = client.post(f"{INT}/guidance-plans/export", headers=_mentor("刘强"),
                           params={"batchId": ids["batch"]}).json()["data"]
    assert exported["rowCount"] == 1


def test_guidance_content_required(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "  "},
                    headers=_mentor("刘强"))
    assert r.status_code == 400  # AppException VALIDATION_ERROR → 400


def test_guidance_void_and_audit(client, db_mode):
    ids = _seed(db_mode)
    gid = client.post(f"{INT}/guidances",
                      json={"internshipId": str(ids["rec_a"]), "content": "待撤销"},
                      headers=_mentor("刘强")).json()["data"]["id"]
    # 详情含审计 CREATE
    detail = client.get(f"{INT}/guidances/{gid}", headers=_mentor("刘强")).json()["data"]
    assert any(t["action"] == "CREATE" for t in detail["auditTrail"])
    # 撤销 → VOID；撤销后 list 不再可见
    v = client.post(f"{INT}/guidances/{gid}/void", json={"reason": "误填"}, headers=_mentor("刘强"))
    assert v.status_code == 200 and v.json()["data"]["status"] == "VOIDED"
    assert client.get(f"{INT}/guidances", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 0


def test_guidance_student_forbidden(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/guidances", headers=_student()).status_code == 403
    assert client.post(f"{INT}/guidances/export", headers=_student()).status_code == 403


# ══════════════ 教师巡访 + 整改跟进 ══════════════

def test_visit_create_scope_and_rectify(client, db_mode):
    ids = _seed(db_mode)
    # 刘强 对本人学生新增巡访（带安全隐患 → 整改中）
    ok = client.post(f"{INT}/visits",
                     json={"internshipId": str(ids["rec_a"]), "method": "ONSITE",
                           "enterpriseFeedback": "表现良好", "safetyIssue": "夜班无陪同",
                           "rectifyRequire": "安排陪同", "rectifyDeadline": "2026-07-20"},
                     headers=_mentor("刘强"))
    assert ok.status_code == 200
    vid = ok.json()["data"]["id"]
    assert ok.json()["data"]["rectifyStatus"] == "PENDING"
    # 越权：刘强 对 王芳 学生新增 → 403
    no = client.post(f"{INT}/visits", json={"internshipId": str(ids["rec_b"])}, headers=_mentor("刘强"))
    assert no.status_code == 403
    # 整改跟进：说明必填
    bad = client.post(f"{INT}/visits/{vid}/rectify", json={"status": "DONE", "note": ""},
                      headers=_mentor("刘强"))
    assert bad.status_code == 400  # 说明必填 → VALIDATION_ERROR → 400
    # 正常跟进 → DONE + 审计
    good = client.post(f"{INT}/visits/{vid}/rectify",
                       json={"status": "DONE", "note": "已安排夜班陪同并确认"}, headers=_mentor("刘强"))
    assert good.status_code == 200 and good.json()["data"]["rectifyStatus"] == "DONE"
    detail = client.get(f"{INT}/visits/{vid}", headers=_mentor("刘强")).json()["data"]
    assert any(t["action"].startswith("RECTIFY_") for t in detail["auditTrail"])
    stats = client.get(f"{INT}/visits/stats", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]
    assert stats["totalVisits"] == 1 and stats["doneRectify"] == 1


def test_visit_rectify_cross_mentor_403(client, db_mode):
    ids = _seed(db_mode)
    vid = client.post(f"{INT}/visits",
                      json={"internshipId": str(ids["rec_a"]), "safetyIssue": "x", "rectifyRequire": "y"},
                      headers=_mentor("刘强")).json()["data"]["id"]
    # 王芳 跟进刘强学生的巡访整改 → 403
    r = client.post(f"{INT}/visits/{vid}/rectify", json={"status": "DONE", "note": "越权跟进"},
                    headers=_mentor("王芳"))
    assert r.status_code == 403


def test_visit_list_scope_and_student_403(client, db_mode):
    ids = _seed(db_mode)
    client.post(f"{INT}/visits", json={"internshipId": str(ids["rec_a"])}, headers=_mentor("刘强"))
    client.post(f"{INT}/visits", json={"internshipId": str(ids["rec_b"])}, headers=_mentor("王芳"))
    assert client.get(f"{INT}/visits", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["total"] == 2
    assert client.get(f"{INT}/visits", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 1
    assert client.get(f"{INT}/visits", headers=_student(), params={"batchId": ids["batch"]}).status_code == 403

"""P3-A · 实习归档中心（材料完整性 / 缺失提醒 / 归档动作 force / 撤销 / 聚合 / 数据范围 / 学生403 / 导出）。"""
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


def _student(sno, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(tid), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode, full_a=True):
    """A(刘强) 材料齐全(7项)；B(王芳) 仅打卡（缺 6 项）。返回 rec ids。"""
    from app.db.session import get_sessionmaker
    from app.models import (InternshipAgreement, InternshipCheckin, InternshipEnterpriseEval,
                            InternshipFinalScore, InternshipGuidance, InternshipRecord,
                            InternshipStudentEval, StudentProfile, WeeklyReport)
    db = get_sessionmaker()()
    ids = {}
    try:
        for no, name, adv, key in [("AR-A", "甲", "刘强", "a"), ("AR-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ASSESSING", risk_level="NONE")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
            ids[f"stu_{key}"] = s.id
        # B：只有打卡
        db.add(InternshipCheckin(tenant_id=TID, internship_id=ids["rec_b"], checkin_date="2026-07-01",
                                 checkin_at=datetime.utcnow(), result="NORMAL"))
        if full_a:
            a = ids["rec_a"]; sa = ids["stu_a"]
            db.add(InternshipAgreement(tenant_id=TID, internship_id=a, student_id=sa, status="EFFECTIVE"))
            db.add(InternshipCheckin(tenant_id=TID, internship_id=a, checkin_date="2026-07-01",
                                     checkin_at=datetime.utcnow(), result="NORMAL"))
            db.add(WeeklyReport(tenant_id=TID, internship_id=a, week_number=1, word_count=800,
                                report_version=1, submitted_at=datetime.utcnow(), status="APPROVED"))
            ev = InternshipEnterpriseEval(tenant_id=TID, internship_id=a, student_id=sa, mentor_name="导师",
                                          attendance_score=90, skill_score=90, attitude_score=90,
                                          collaboration_score=90, safety_score=90,
                                          school_review_status="APPROVED")
            db.add(ev)
            db.add(InternshipStudentEval(tenant_id=TID, internship_id=a, student_id=sa,
                                         self_summary="总结", submit_status="SUBMITTED"))
            db.add(InternshipFinalScore(tenant_id=TID, internship_id=a, student_id=sa,
                                        total_score=90, status="PUBLISHED", incomplete=False, is_pass=True))
            db.add(InternshipGuidance(tenant_id=TID, internship_id=a, student_id=sa,
                                      content="指导", status="NORMAL"))
        db.commit()
        return ids
    finally:
        db.close()


def _find(items, name):
    return next(it for it in items if it["studentName"] == name)


def test_completeness_and_missing(client, db_mode):
    _seed(db_mode)
    items = client.get(f"{INT}/archive", headers=_admin(client)).json()["data"]["items"]
    a = _find(items, "甲")
    b = _find(items, "乙")
    assert a["completeness"] == 100 and a["missing"] == []
    # B 仅打卡：7 项中 1 项 → 14%（round(1/7*100)=14）
    assert b["completeness"] == 14 and "三方协议" in b["missing"] and "实习成绩" in b["missing"]


def test_archive_requires_complete_or_force(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    hw = _mentor("王芳")
    # A 完整 → 直接归档
    ok = client.post(f"{INT}/archive/{ids['rec_a']}/archive", headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["completeness"] == 100
    # B 不完整 → 409（未 force）
    assert client.post(f"{INT}/archive/{ids['rec_b']}/archive", headers=hw).status_code == 409
    # force 归档 B → 200，记 missing
    f = client.post(f"{INT}/archive/{ids['rec_b']}/archive", json={"force": True}, headers=hw)
    assert f.status_code == 200 and f.json()["data"]["archived"] is True and f.json()["data"]["missing"]


def test_archive_package(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    client.post(f"{INT}/archive/{ids['rec_a']}/archive", headers=h)
    # 未归档不能打包
    assert client.post(f"{INT}/archive/{ids['rec_b']}/package", headers=_mentor("王芳")).status_code == 409
    pkg = client.post(f"{INT}/archive/{ids['rec_a']}/package", headers=h)
    assert pkg.status_code == 200
    data = pkg.json()["data"]
    assert data["packageReady"] is True and data["fileId"] and data["fileName"].endswith(".zip")
    detail = client.get(f"{INT}/archive/{ids['rec_a']}", headers=h).json()["data"]
    assert detail["packageReady"] is True


def test_revoke(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    client.post(f"{INT}/archive/{ids['rec_a']}/archive", headers=h)
    # 撤销需原因
    assert client.post(f"{INT}/archive/{ids['rec_a']}/revoke", json={"reason": "x"}, headers=h).status_code == 400
    rv = client.post(f"{INT}/archive/{ids['rec_a']}/revoke", json={"reason": "材料需重新核对"}, headers=h)
    assert rv.status_code == 200 and rv.json()["data"]["archived"] is False
    # 未归档再撤销 → 409
    assert client.post(f"{INT}/archive/{ids['rec_a']}/revoke", json={"reason": "重复撤销测试"}, headers=h).status_code == 409


def test_detail_material_labels(client, db_mode):
    ids = _seed(db_mode)
    d = client.get(f"{INT}/archive/{ids['rec_b']}", headers=_admin(client)).json()["data"]
    labels = {m["label"]: m["present"] for m in d["materialLabels"]}
    assert labels["打卡记录"] is True and labels["三方协议"] is False


def test_by_enterprise_aggregate(client, db_mode):
    _seed(db_mode)
    agg = client.get(f"{INT}/archive/by-enterprise", headers=_admin(client)).json()["data"]
    ent = next(g for g in agg if g["group"] == "测试企业")
    assert ent["total"] == 2 and ent["complete"] == 1  # 甲完整，乙不完整


def test_scope_and_student_forbidden(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/archive", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/archive", headers=_mentor("刘强")).json()["data"]["total"] == 1
    assert client.get(f"{INT}/archive", headers=_student("AR-A")).status_code == 403


def test_export(client, db_mode):
    _seed(db_mode)
    res = client.post(f"{INT}/archive/export", headers=_admin(client))
    assert res.status_code == 200 and res.json()["data"]["filename"].endswith(".xlsx")
    assert res.json()["data"]["rowCount"] == 2

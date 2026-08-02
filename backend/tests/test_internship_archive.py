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
    """A(刘强) 材料齐全 + 合规达标(资格/企业/岗位/保险/协议/评价/成绩全通过)；
    B(王芳) 仅打卡（资格/企业/岗位/保险/协议/评价材料全缺，合规评估会拦下）。返回 rec ids。

    归档合规现走统一评估 evaluate_internship_compliance("ARCHIVE")（见
    internship_compliance_service.py），不再是旧版 7 项静态材料清单；批次显式关闭
    监护人知情确认分支（无 birth_date 时永远 PENDING，同 test_internship_student.py
    批注），且不设起止日期让打卡/周报/巡访/指导「应有数量」按自然日历推算为 0，
    因此不必再单独造这些数量材料。
    """
    from datetime import date
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import (EmpCompany, InternshipAgreement, InternshipBatch, InternshipCheckin,
                            InternshipEnterpriseEval, InternshipFinalScore, InternshipGuidance,
                            InternshipInsurance, InternshipPosition, InternshipRecord,
                            InternshipStudentEval, StudentProfile, WeeklyReport)
    db = get_sessionmaker()()
    ids = {}
    try:
        b = InternshipBatch(
            tenant_id=TID, batch_name="归档测试批次", batch_no=f"ARB-{uuid4().hex[:8]}",
            status="RUNNING", planned_count=5, end_date=date.today(),
            rules_config={"compliance": {"studentConsent": {"requireGuardianConsentForMinor": False}}})
        db.add(b); db.flush()
        ids["batch"] = b.id
        company = EmpCompany(tenant_id=TID, name="归档测试企业",
                             credit_code=f"91310000AR{uuid4().hex[:6].upper()}", coop_status="ACTIVE")
        db.add(company); db.flush()
        position = InternshipPosition(tenant_id=TID, company_id=company.id, title="实习生",
                                      batch_id=b.id, status="PUBLISHED", headcount=5)
        db.add(position); db.flush()
        for no, name, adv, key in [("AR-A", "甲", "刘强", "a"), ("AR-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="归档测试企业", position_name="实习生",
                                 status="ASSESSING", risk_level="NONE", batch_id=b.id)
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
            ids[f"stu_{key}"] = s.id
        # B：只有打卡，资格/企业/岗位/保险/协议/评价材料全缺 → 合规评估拦下
        db.add(InternshipCheckin(tenant_id=TID, internship_id=ids["rec_b"], checkin_date="2026-07-01",
                                 checkin_at=datetime.utcnow(), result="NORMAL"))
        if full_a:
            a = ids["rec_a"]; sa = ids["stu_a"]
            ra = db.get(InternshipRecord, a)
            ra.eligibility_status = "QUALIFIED"
            ra.enterprise_id = company.id
            ra.position_id = position.id
            db.add(InternshipInsurance(tenant_id=TID, internship_id=a, student_id=sa, status="VERIFIED"))
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
    ids = _seed(db_mode)
    items = client.get(f"{INT}/archive", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["items"]
    a = _find(items, "甲")
    b = _find(items, "乙")
    assert a["completeness"] == 100 and a["missing"] == []
    # B 仅打卡：资格/企业/岗位/保险/协议/企业评价/学生自评/成绩 8 项合规缺失
    assert b["completeness"] < 100 and "三方协议" in b["missing"] and "实习成绩" in b["missing"]


def test_archive_requires_complete_or_force(client, db_mode):
    ids = _seed(db_mode)
    # 归档/强制归档为 internship.archive.execute/.force，导师无此权限，仅学校管理员可执行
    h = _admin(client)
    # A 完整 → 直接归档
    ok = client.post(f"{INT}/archive/{ids['rec_a']}/archive", json={"expectedVersion": 0}, headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["completeness"] == 100, ok.json()
    # B 不完整 → 409（未 force）
    assert client.post(f"{INT}/archive/{ids['rec_b']}/archive",
                       json={"expectedVersion": 0}, headers=h).status_code == 409
    # force 归档 B → 200，记 missing（强制归档必须提供理由与依据文件）
    import io
    up = client.post("/api/v1/files", headers=h,
                     files={"file": ("evidence.txt", io.BytesIO(b"force-archive-evidence"), "text/plain")},
                     data={"bizType": "ATTACHMENT"})
    fid = up.json()["data"]["fileId"]
    f = client.post(f"{INT}/archive/{ids['rec_b']}/archive",
                    json={"force": True, "expectedVersion": 0,
                          "forceReason": "材料不全但业务急需先行归档留痕",
                          "evidenceFileIds": [fid]}, headers=h)
    assert f.status_code == 200 and f.json()["data"]["archived"] is True and f.json()["data"]["missing"], f.json()


def test_archive_package(client, db_mode):
    ids = _seed(db_mode)
    h = _admin(client)
    client.post(f"{INT}/archive/{ids['rec_a']}/archive", json={"expectedVersion": 0}, headers=h)
    # 未归档不能打包
    assert client.post(f"{INT}/archive/{ids['rec_b']}/package", headers=h).status_code == 409
    pkg = client.post(f"{INT}/archive/{ids['rec_a']}/package", headers=h)
    assert pkg.status_code == 200, pkg.json()
    data = pkg.json()["data"]
    assert data["packageReady"] is True and data["fileId"] and data["fileName"].endswith(".zip")
    detail = client.get(f"{INT}/archive/{ids['rec_a']}", headers=h).json()["data"]
    assert detail["packageReady"] is True


def test_revoke(client, db_mode):
    ids = _seed(db_mode)
    h = _admin(client)
    arch = client.post(f"{INT}/archive/{ids['rec_a']}/archive", json={"expectedVersion": 0}, headers=h).json()["data"]
    ver, rver = arch["version"], arch["recordVersion"]
    # 撤销需原因（≥10 个汉字）
    assert client.post(f"{INT}/archive/{ids['rec_a']}/revoke",
                       json={"reason": "x", "expectedVersion": ver, "recordExpectedVersion": rver},
                       headers=h).status_code == 400
    rv = client.post(f"{INT}/archive/{ids['rec_a']}/revoke",
                     json={"reason": "材料信息有误需要重新核对确认",
                           "expectedVersion": ver, "recordExpectedVersion": rver}, headers=h)
    assert rv.status_code == 200 and rv.json()["data"]["archived"] is False, rv.json()
    # 未归档再撤销 → 409
    assert client.post(f"{INT}/archive/{ids['rec_a']}/revoke",
                       json={"reason": "重复撤销测试重复撤销测试",
                             "expectedVersion": rv.json()["data"]["version"],
                             "recordExpectedVersion": rv.json()["data"]["recordVersion"]},
                       headers=h).status_code == 409


def test_detail_material_labels(client, db_mode):
    ids = _seed(db_mode)
    d = client.get(f"{INT}/archive/{ids['rec_b']}", headers=_admin(client)).json()["data"]
    labels = {m["label"]: m["present"] for m in d["materialLabels"]}
    assert labels["打卡记录"] is True and labels["三方协议"] is False


def test_by_enterprise_aggregate(client, db_mode):
    ids = _seed(db_mode)
    agg = client.get(f"{INT}/archive/by-enterprise", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]
    ent = next(g for g in agg if g["group"] == "归档测试企业")
    assert ent["total"] == 2 and ent["complete"] == 1  # 甲完整，乙不完整


def test_scope_and_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    assert client.get(f"{INT}/archive", headers=_admin(client), params={"batchId": ids["batch"]}).json()["data"]["total"] == 2
    assert client.get(f"{INT}/archive", headers=_mentor("刘强"), params={"batchId": ids["batch"]}).json()["data"]["total"] == 1
    assert client.get(f"{INT}/archive", headers=_student("AR-A"), params={"batchId": ids["batch"]}).status_code == 403


def test_export(client, db_mode):
    ids = _seed(db_mode)
    res = client.post(f"{INT}/archive/export", headers=_admin(client), params={"batchId": ids["batch"]})
    assert res.status_code == 200 and res.json()["data"]["filename"].endswith(".xlsx")
    assert res.json()["data"]["rowCount"] == 2

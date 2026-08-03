"""毕业设计域测试：学生/选题/开题批阅闭环/成果批阅/答辩发布（冲突拒绝）+ 看板 + 审计。"""
from __future__ import annotations

from conftest import make_org_class

from datetime import datetime

MAIN_TID = 1000000000000000001


def _seed(_db_mode, stage="FINAL_CHECK", taskbook=False, final_status="PENDING_REVIEW"):
    from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (FileObject, GraduationBatch, GraduationDefenseGroup, GraduationFinal, GraduationMentor,
                            GraduationPlagiarismCheck, GraduationProposal, GraduationStudent, GraduationTopic)
    from app.models import GraduationTaskBook
    from app.modules.graduation.materials.command_service import adopt_legacy_file_in_session
    from app.modules.graduation.materials.rule_service import initialize_default_rule_in_session

    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    actor = {
        "userId": "school-admin-test", "realName": "测试管理员", "userType": "TEACHER",
        "currentRoleCode": "SCHOOL_ADMIN", "tenantId": str(MAIN_TID), "tid": "demo",
    }
    set_tenant({"tenantId": str(MAIN_TID), "tenantCode": "demo"})
    set_current_user(actor)
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(tenant_id=MAIN_TID, batch_name="种子批次", batch_no="GD-SEED-1",
                                grade_year="2026届", planned_count=10, status="IN_PROGRESS")
        db.add(batch)
        db.flush()
        s = GraduationStudent(tenant_id=MAIN_TID, batch_id=batch.id, name="毕设甲", student_no="S2026-999001",
                              class_id=make_org_class(), class_name="软件2301", topic_title="课题A",
                              advisor_name="王芳", stage=stage, risk_level="LOW",
                              phone_encrypted="13612349999")
        db.add(s)
        db.flush()
        if taskbook:
            db.add(GraduationTaskBook(
                tenant_id=MAIN_TID, gd_student_id=s.id, objective="完成毕业设计",
                content="完成任务书要求", status="CONFIRMED", confirmed_at=datetime.utcnow(),
            ))
        proposal_file = FileObject(
            tenant_id=MAIN_TID, file_key=f"test/graduation/proposal-{s.id}.pdf",
            file_name="proposal.pdf", ext="pdf", mime_type="application/pdf", size_bytes=128,
            sha256=f"{int(s.id) * 2:064x}"[-64:], biz_type="GRADUATION_MATERIAL", biz_id=str(s.id),
            visibility="BIZ_SCOPED", status="AVAILABLE", scan_status="CLEAN",
        )
        final_file = FileObject(
            tenant_id=MAIN_TID, file_key=f"test/graduation/final-{s.id}.pdf",
            file_name="final.pdf", ext="pdf", mime_type="application/pdf", size_bytes=256,
            sha256=f"{int(s.id) * 2 + 1:064x}"[-64:], biz_type="GRADUATION_MATERIAL", biz_id=str(s.id),
            visibility="BIZ_SCOPED", status="AVAILABLE", scan_status="CLEAN",
        )
        db.add_all([proposal_file, final_file])
        db.flush()
        p = GraduationProposal(tenant_id=MAIN_TID, gd_student_id=s.id, version="v1", submit_at=datetime.utcnow(),
                               background="bg", plan="plan", outcome="out", status="PENDING_REVIEW",
                               attachments_json=[str(proposal_file.id)])
        f = GraduationFinal(tenant_id=MAIN_TID, gd_student_id=s.id, final_type="定稿", version="v3",
                            submit_at=datetime.utcnow(), plagiarism_rate="12.6%", plagiarism_status="达标",
                            status=final_status, attachments_json=[str(final_file.id)])
        db.add(GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title="选题A", source="教师申报",
                               source_type="TEACHER", advisor_name="王芳", major_name="软件技术", capacity=2,
                               selected=1, review_status="APPROVED", status="CONFIRMED"))
        chair_ok = GraduationMentor(tenant_id=MAIN_TID, teacher_no="DP-CHAIR-OK", teacher_name="周正邦（教授）",
                                    qualification_status="QUALIFIED")
        member_ok = GraduationMentor(tenant_id=MAIN_TID, teacher_no="DP-MEMBER-OK", teacher_name="孙晓梅",
                                     qualification_status="QUALIFIED")
        secretary_ok = GraduationMentor(tenant_id=MAIN_TID, teacher_no="DP-SEC-OK", teacher_name="林小婉",
                                        qualification_status="QUALIFIED")
        advisor_bad = GraduationMentor(tenant_id=MAIN_TID, teacher_no="DP-ADVISOR-BAD", teacher_name="王芳",
                                       qualification_status="QUALIFIED")
        secretary_bad = GraduationMentor(tenant_id=MAIN_TID, teacher_no="DP-SEC-BAD", teacher_name="孙晓梅B",
                                         qualification_status="QUALIFIED")
        db.add_all([chair_ok, member_ok, secretary_ok, advisor_bad, secretary_bad])
        db.flush()
        gok = GraduationDefenseGroup(tenant_id=MAIN_TID, batch_id=batch.id, group_name="第1组",
                                     defense_date="2026-07-08 09:00",
                                     location="B401", chair="周正邦（教授）", chair_mentor_id=chair_ok.id,
                                     members_json=[{"mentorId": member_ok.id, "name": "孙晓梅", "teacherNo": "DP-MEMBER-OK"}],
                                     secretary="林小婉", secretary_mentor_id=secretary_ok.id,
                                     student_count=0, conflict=None, published=False)
        gbad = GraduationDefenseGroup(tenant_id=MAIN_TID, batch_id=batch.id, group_name="第2组",
                                      defense_date="2026-07-08 14:00",
                                      location="B402", chair="王芳", chair_mentor_id=advisor_bad.id,
                                      members_json=[{"mentorId": advisor_bad.id, "name": "王芳", "teacherNo": "DP-ADVISOR-BAD"}],
                                      secretary="孙晓梅B", secretary_mentor_id=secretary_bad.id,
                                      student_count=0, conflict="评委含指导教师本人", published=False)
        db.add_all([p, f, gok, gbad])
        db.flush()
        # File readiness is verified through the production file service, which
        # intentionally opens its own transaction.  Persist the authoritative
        # rows before adopting them into immutable material file versions.
        db.commit()
        initialize_default_rule_in_session(db, int(batch.id), actor)
        adopt_legacy_file_in_session(
            db, s, "PROPOSAL_REPORT", int(proposal_file.id), source_record_type="PROPOSAL",
            source_record_id=str(p.id), user=actor, approved=False,
        )
        adopt_legacy_file_in_session(
            db, s, "THESIS_FINAL", int(final_file.id), source_record_type="FINAL",
            source_record_id=str(f.id), user=actor, approved=final_status == "APPROVED",
        )
        db.add(GraduationPlagiarismCheck(
            tenant_id=MAIN_TID, gd_student_id=s.id, gd_final_id=f.id,
            submit_at=datetime.utcnow(), status="DONE", rate="12.6%", threshold=30,
            over_threshold=False,
        ))
        db.commit()
        return {"student": s.id, "proposal": p.id, "final": f.id, "gok": gok.id, "gbad": gbad.id,
                "batch": batch.id}
    finally:
        db.close()
        set_current_user(previous_user)
        set_tenant(previous_tenant)


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/graduation/students", headers=auth_headers,
                     params={"batchId": ids["batch"]}).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["stageLabel"] == "成果检查"
    det = client.get(f"/api/v1/graduation/students/{ids['student']}", headers=auth_headers,
                     params={"batchId": ids["batch"]}).json()
    assert det["code"] == 0 and len(det["data"]["proposals"]) == 1 and len(det["data"]["finals"]) == 1


def test_topics(client, auth_headers, db_mode):
    _seed(db_mode)
    lst = client.get("/api/v1/graduation/topics", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["statusLabel"] == "已入池"


def test_proposal_review_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode, stage="TASKBOOK_CONFIRM", taskbook=True)
    bad = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                      params={"batchId": ids["batch"]},
                      json={"action": "REJECT", "comment": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                     params={"batchId": ids["batch"]},
                     json={"action": "APPROVE", "comment": ""}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    det = client.get(f"/api/v1/graduation/students/{ids['student']}", headers=auth_headers,
                     params={"batchId": ids["batch"]}).json()
    assert det["data"]["student"]["stage"] == "GUIDING"
    dup = client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                      params={"batchId": ids["batch"]},
                      json={"action": "APPROVE"}).json()
    assert dup["code"] == 409001


def test_final_review(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    ok = client.post(f"/api/v1/graduation/finals/{ids['final']}/review", headers=auth_headers,
                     params={"batchId": ids["batch"]},
                     json={"action": "APPROVE"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"


def test_defense_publish_conflict(client, auth_headers, db_mode):
    """答辩发布：评委回避冲突拦截 + 完整组可发布。"""
    ids = _seed(db_mode, final_status="APPROVED")
    h = auth_headers
    client.post(f"/api/v1/graduation/defense-groups/{ids['gbad']}/assign", headers=h,
                params={"batchId": ids["batch"]},
                json={"studentIds": [str(ids["student"])]})
    bad = client.post(f"/api/v1/graduation/defense-groups/{ids['gbad']}/publish", headers=h,
                      params={"batchId": ids["batch"]}).json()
    assert bad["code"] == 422001 and "冲突" in bad["message"]
    sid = client.post("/api/v1/students", headers=h,
                      json={"studentNo": "DPOK1", "realName": "正常答辩生", "classId": make_org_class()}).json()["data"]["id"]
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal, GraduationStudent
    db = get_sessionmaker()()
    try:
        stu = GraduationStudent(
            tenant_id=MAIN_TID, batch_id=ids["batch"], student_id=int(sid), name="正常答辩生",
            student_no="DPOK1", class_id=make_org_class(), class_name="软件2301",
            topic_title="课题B", advisor_name="无冲突导师", stage="FINAL_CHECK", risk_level="LOW",
        )
        db.add(stu)
        db.flush()
        db.add(GraduationFinal(
            tenant_id=MAIN_TID, gd_student_id=stu.id, final_type="定稿", version="v1",
            submit_at=datetime.utcnow(), status="APPROVED",
        ))
        db.commit()
        g2 = str(stu.id)
    finally:
        db.close()
    client.post(f"/api/v1/graduation/defense-groups/{ids['gok']}/assign", headers=h,
                params={"batchId": ids["batch"]},
                json={"studentIds": [str(g2)]})
    ok = client.post(f"/api/v1/graduation/defense-groups/{ids['gok']}/publish", headers=h,
                     params={"batchId": ids["batch"]}).json()
    assert ok["code"] == 0 and ok["data"]["published"] is True
    lst = client.get("/api/v1/graduation/defense-groups", headers=h,
                     params={"batchId": ids["batch"]}).json()
    pub = [g for g in lst["data"]["items"] if g["id"] == str(ids["gok"])][0]
    assert pub["published"] is True


def test_dashboard_and_audit(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    dash = client.get("/api/v1/graduation/dashboard", headers=auth_headers,
                      params={"batchId": ids["batch"]}).json()
    assert dash["code"] == 0 and any(s["label"] == "毕设学生" for s in dash["data"]["stats"])
    client.post(f"/api/v1/graduation/proposals/{ids['proposal']}/review", headers=auth_headers,
                params={"batchId": ids["batch"]},
                json={"action": "APPROVE"})
    au = client.get("/api/v1/graduation/audit-logs", headers=auth_headers,
                    params={"bizType": "PROPOSAL", "batchId": ids["batch"]}).json()
    assert au["code"] == 0 and au["data"]["total"] >= 1


def test_requires_login(client):
    assert client.get("/api/v1/graduation/dashboard").json()["code"] == 401001

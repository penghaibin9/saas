"""学生 PC 门户 · 毕业设计（第2期）任务书 PC 电子确认测试（MySQL 真库 via db_mode）：

查看任务书 / 电子确认(可靠留痕contentHash+置确认态+落PortalSignRecord) /
未勾选确认拒绝 / 无任务书DATA_NOT_FOUND / 打印留痕 / 非学生拒绝。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

PORTAL = "/api/v1/portal/graduation"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M",
                          current_stage="GRADUATION", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def _seed_gd_with_taskbook(no, name):
    """建毕设学生 + 一份 PENDING_CONFIRM 任务书（直接落模型，避开服务层租户上下文）。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, GraduationTaskBook
    db = get_sessionmaker()()
    g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                          stage="TASKBOOK_CONFIRM", risk_level="LOW", eligibility_status="PENDING",
                          grad_qual_status="PENDING", record_status="ACTIVE")
    db.add(g)
    db.flush()
    db.add(GraduationTaskBook(tenant_id=TID, gd_student_id=g.id, taskbook_version=1,
                              status="PENDING_CONFIRM", objective="研究XX系统设计与实现",
                              content="完成需求分析、设计、编码、测试与论文撰写。",
                              history_json=[]))
    db.commit()
    db.close()


def test_view_and_sign_taskbook(client, db_mode):
    _seed_student("GD-P-001", "毕一")
    _seed_gd_with_taskbook("GD-P-001", "毕一")
    h = _stu_token("毕一", "GD-P-001")
    tb = client.get(f"{PORTAL}/taskbook", headers=h).json()
    assert tb["code"] == 0 and tb["data"]["hasData"] is True
    r = client.post(f"{PORTAL}/taskbook/sign", headers=h, json={"confirm": True}).json()
    assert r["code"] == 0
    d = r["data"]
    assert len(d["contentHash"]) == 64 and d["provider"] == "reliable_log" and d["legalEffect"] is False
    # 落了签署记录
    from app.db.session import get_sessionmaker
    from app.models import PortalSignRecord
    dbx = get_sessionmaker()()
    try:
        cnt = dbx.query(PortalSignRecord).filter(
            PortalSignRecord.tenant_id == TID,
            PortalSignRecord.biz_type == "GRADUATION_TASKBOOK").count()
        assert cnt == 1
    finally:
        dbx.close()


def test_sign_requires_confirm(client, db_mode):
    _seed_student("GD-P-002", "毕二")
    _seed_gd_with_taskbook("GD-P-002", "毕二")
    h = _stu_token("毕二", "GD-P-002")
    assert client.post(f"{PORTAL}/taskbook/sign", headers=h, json={"confirm": False}).json()["code"] != 0


def test_sign_without_taskbook(client, db_mode):
    _seed_student("GD-P-003", "毕三")  # 无毕设记录
    h = _stu_token("毕三", "GD-P-003")
    r = client.post(f"{PORTAL}/taskbook/sign", headers=h, json={"confirm": True}).json()
    assert r["code"] == 404001


def test_print_log(client, db_mode):
    _seed_student("GD-P-004", "毕四")
    h = _stu_token("毕四", "GD-P-004")
    r = client.post(f"{PORTAL}/taskbook/print", headers=h, json={"bizId": "TB-4"}).json()
    assert r["code"] == 0 and r["data"]["watermark"] == "毕四"


def _seed_gd_ready_for_proposal(no, name):
    """建毕设学生（选题+任务书已确认，可提交开题）。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent, GraduationTaskBook
    db = get_sessionmaker()()
    g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                             topic_id=1, topic_title="XX系统的设计与实现", stage="GUIDING",
                             risk_level="LOW", eligibility_status="PENDING",
                             grad_qual_status="PENDING", record_status="ACTIVE")
    db.add(g)
    db.flush()
    db.add(GraduationTaskBook(tenant_id=TID, gd_student_id=g.id, taskbook_version=1,
                              status="CONFIRMED", objective="研究XX系统设计与实现",
                              content="完成需求分析、设计、编码、测试与论文撰写。",
                              history_json=[]))
    db.commit()
    db.close()


def test_view_and_submit_proposal(client, db_mode):
    _seed_student("GD-P-101", "开题一")
    _seed_gd_ready_for_proposal("GD-P-101", "开题一")
    h = _stu_token("开题一", "GD-P-101")
    v = client.get(f"{PORTAL}/proposal", headers=h).json()
    assert v["code"] == 0 and v["data"]["hasData"] is True and v["data"]["canSubmit"] is True
    r = client.post(f"{PORTAL}/proposal/submit", headers=h, json={
        "background": "本课题研究XX系统，背景意义……（长文本）",
        "plan": "需求分析→设计→实现→测试", "outcome": "系统+论文", "attachments": []}).json()
    assert r["code"] == 0 and r["data"].get("id")


def test_submit_proposal_empty_rejected(client, db_mode):
    _seed_student("GD-P-102", "开题二")
    _seed_gd_ready_for_proposal("GD-P-102", "开题二")
    h = _stu_token("开题二", "GD-P-102")
    assert client.post(f"{PORTAL}/proposal/submit", headers=h,
                       json={"background": "", "plan": "", "outcome": ""}).json()["code"] != 0


def test_submit_proposal_no_gd_record(client, db_mode):
    _seed_student("GD-P-103", "开题三")  # 无毕设记录
    h = _stu_token("开题三", "GD-P-103")
    assert client.post(f"{PORTAL}/proposal/submit", headers=h,
                       json={"background": "x内容"}).json()["code"] != 0


def _seed_gd_midterm_rectifying(no, name):
    """建毕设学生 + 一条 RECTIFYING(需整改) 的中期检查。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent
    db = get_sessionmaker()()
    g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                          stage="MIDTERM", risk_level="LOW", eligibility_status="PENDING",
                          grad_qual_status="PENDING", record_status="ACTIVE")
    db.add(g)
    db.flush()
    db.add(GraduationMidterm(tenant_id=TID, gd_student_id=g.id, status="RECTIFYING",
                             rectify_attempts=0))
    db.commit()
    db.close()


def test_view_and_rectify_midterm(client, db_mode):
    _seed_student("GD-P-201", "中期一")
    _seed_gd_midterm_rectifying("GD-P-201", "中期一")
    h = _stu_token("中期一", "GD-P-201")
    v = client.get(f"{PORTAL}/midterm", headers=h).json()
    assert v["code"] == 0 and v["data"]["hasData"] is True
    r = client.post(f"{PORTAL}/midterm/rectify", headers=h,
                    json={"content": "已按导师批注补充实验数据与文献综述。"}).json()
    assert r["code"] == 0


def test_midterm_rectify_empty_rejected(client, db_mode):
    _seed_student("GD-P-202", "中期二")
    _seed_gd_midterm_rectifying("GD-P-202", "中期二")
    h = _stu_token("中期二", "GD-P-202")
    assert client.post(f"{PORTAL}/midterm/rectify", headers=h, json={"content": "  "}).json()["code"] != 0


def _seed_gd_for_final(no, name):
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent
    db = get_sessionmaker()()
    g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                             topic_id=1, topic_title="XX系统的设计与实现", stage="FINAL_CHECK",
                             risk_level="LOW", eligibility_status="PENDING",
                             grad_qual_status="PENDING", record_status="ACTIVE")
    db.add(g)
    db.flush()
    db.add(GraduationMidterm(
        tenant_id=TID, gd_student_id=g.id, status="CHECKED_PASS", conclusion="PASS",
        check_comment="中期通过", checked_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()


def _seed_pdf_file():
    """建一个真实 pdf 文件对象（论文附件校验要求真实 file_id + ext∈pdf/doc/docx/zip）。"""
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    f = FileObject(tenant_id=TID, file_key="test/thesis-1.pdf", file_name="毕业论文.pdf",
                   ext="pdf", size_bytes=1024, biz_type="GRADUATION_MATERIAL", status="CONFIRMED")
    db.add(f)
    db.commit()
    fid = str(f.id)
    db.close()
    return fid


def test_view_and_submit_final(client, db_mode):
    _seed_student("GD-P-301", "成果一")
    _seed_gd_for_final("GD-P-301", "成果一")
    fid = _seed_pdf_file()
    h = _stu_token("成果一", "GD-P-301")
    v = client.get(f"{PORTAL}/final", headers=h).json()
    assert v["code"] == 0 and v["data"]["hasData"] is True and v["data"]["canSubmitDraft"] is True
    r = client.post(f"{PORTAL}/final/submit", headers=h,
                    json={"finalType": "初稿", "attachments": [fid]}).json()
    assert r["code"] == 0 and r["data"].get("id")


def test_submit_final_requires_attachment(client, db_mode):
    _seed_student("GD-P-302", "成果二")
    _seed_gd_for_final("GD-P-302", "成果二")
    h = _stu_token("成果二", "GD-P-302")
    assert client.post(f"{PORTAL}/final/submit", headers=h,
                       json={"finalType": "初稿", "attachments": []}).json()["code"] != 0
    assert client.post(f"{PORTAL}/final/submit", headers=h,
                       json={"finalType": "xyz", "attachments": ["f1"]}).json()["code"] != 0


def _seed_gd_published_grade(no, name):
    from app.db.session import get_sessionmaker
    from app.models import GraduationGrade, GraduationStudent
    db = get_sessionmaker()()
    g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                          stage="GRADED", risk_level="LOW", eligibility_status="PENDING",
                          grad_qual_status="PENDING", record_status="ACTIVE")
    db.add(g)
    db.flush()
    db.add(GraduationGrade(tenant_id=TID, gd_student_id=g.id, status="PUBLISHED"))
    db.commit()
    db.close()


def test_defense_and_grade_view(client, db_mode):
    _seed_student("GD-P-401", "答辩一")
    _seed_gd_ready_for_proposal("GD-P-401", "答辩一")  # 有毕设记录即可
    h = _stu_token("答辩一", "GD-P-401")
    assert client.get(f"{PORTAL}/defense", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/grade", headers=h).json()["code"] == 0


def test_grade_appeal(client, db_mode):
    _seed_student("GD-P-402", "答辩二")
    _seed_gd_published_grade("GD-P-402", "答辩二")
    h = _stu_token("答辩二", "GD-P-402")
    ok = client.post(f"{PORTAL}/grade/appeal", headers=h,
                     json={"reason": "答辩表现与评分不符，申请复核成绩明细。"}).json()
    assert ok["code"] == 0
    # 空理由拒绝
    assert client.post(f"{PORTAL}/grade/appeal", headers=h, json={"reason": ""}).json()["code"] != 0


def test_grade_appeal_without_published(client, db_mode):
    _seed_student("GD-P-403", "答辩三")
    _seed_gd_ready_for_proposal("GD-P-403", "答辩三")  # 有毕设但成绩未发布
    h = _stu_token("答辩三", "GD-P-403")
    r = client.post(f"{PORTAL}/grade/appeal", headers=h,
                    json={"reason": "申请复核成绩明细内容。"}).json()
    assert r["code"] == 409001  # 成绩未发布不可申诉


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/taskbook", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/proposal", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/midterm", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/final", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/grade", headers=admin).json()["code"] == 403001

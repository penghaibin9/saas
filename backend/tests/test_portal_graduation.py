"""学生 PC 门户 · 毕业设计（第2期）任务书 PC 电子确认测试（MySQL 真库 via db_mode）：

查看任务书 / 电子确认(可靠留痕contentHash+置确认态+落PortalSignRecord) /
未勾选确认拒绝 / 无任务书DATA_NOT_FOUND / 打印留痕 / 非学生拒绝。
"""
from __future__ import annotations

import hashlib

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
    """建毕设学生（已过选题阶段，可提交开题）。"""
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    db = get_sessionmaker()()
    db.add(GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",
                             topic_id=1, topic_title="XX系统的设计与实现", stage="PROPOSAL",
                             risk_level="LOW", eligibility_status="PENDING",
                             grad_qual_status="PENDING", record_status="ACTIVE"))
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


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/taskbook", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/proposal", headers=admin).json()["code"] == 403001

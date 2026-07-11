"""P2-A · 三方协议签署实例（三方确认状态机 / owner / 数据范围 / 学生端确认 / 附件 / 导出 / 审计）。

流程：generate(DRAFT)→issue(待学生)→学生确认(待企业)→企业确认+扫描件(待学校)→学校确认(生效)→归档。
"""
from __future__ import annotations

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


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        for no, name, adv, key in [("AG-A", "甲", "刘强", "a"), ("AG-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
        db.commit()
        return ids
    finally:
        db.close()


def _file(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    try:
        f = FileObject(tenant_id=TID, file_key="20260709/ag.pdf", file_name="三方协议签署.pdf",
                       ext="pdf", size_bytes=2048, biz_type="ATTACHMENT", status="STORED")
        db.add(f); db.flush(); fid = str(f.id); db.commit()
        return fid
    finally:
        db.close()


def test_full_three_party_flow(client, db_mode):
    ids = _seed(db_mode)
    fid = _file(db_mode)
    h = _mentor("刘强")
    # 生成 DRAFT
    gen = client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=h)
    assert gen.status_code == 200
    aid = gen.json()["data"]["id"]
    # 重复生成被拒
    assert client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=h).status_code == 409
    # 下发 → 待学生确认
    assert client.post(f"{INT}/agreements/{aid}/issue", headers=h).json()["data"]["status"] == "PENDING_STUDENT"
    # 学生确认 → 待企业确认
    sc = client.post(f"/api/v1/mobile/internship/agreements/{aid}/confirm", json={"action": "CONFIRM"}, headers=_student("AG-A"))
    assert sc.status_code == 200 and sc.json()["data"]["status"] == "PENDING_ENTERPRISE"
    # 企业确认需扫描件：缺 file → 400
    assert client.post(f"{INT}/agreements/{aid}/enterprise-confirm", json={"confirmBy": "企业HR"}, headers=h).status_code == 400
    # 带扫描件 → 待学校确认
    ec = client.post(f"{INT}/agreements/{aid}/enterprise-confirm", json={"confirmBy": "企业HR", "fileId": fid}, headers=h)
    assert ec.status_code == 200 and ec.json()["data"]["status"] == "PENDING_SCHOOL"
    # 学校确认 → 生效
    assert client.post(f"{INT}/agreements/{aid}/school-confirm", headers=h).json()["data"]["status"] == "EFFECTIVE"
    # 归档
    assert client.post(f"{INT}/agreements/{aid}/archive", headers=h).json()["data"]["status"] == "ARCHIVED"
    # 详情含附件 + 全链审计
    detail = client.get(f"{INT}/agreements/{aid}", headers=h).json()["data"]
    assert detail["attachment"]["fileName"] == "三方协议签署.pdf"
    actions = {t["action"] for t in detail["auditTrail"]}
    assert {"GENERATE", "ISSUE", "STUDENT_CONFIRM", "ENTERPRISE_CONFIRM", "SCHOOL_CONFIRM", "ARCHIVE"} <= actions


def test_student_reject(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    aid = client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=h).json()["data"]["id"]
    client.post(f"{INT}/agreements/{aid}/issue", headers=h)
    r = client.post(f"/api/v1/mobile/internship/agreements/{aid}/confirm",
                    json={"action": "REJECT", "reason": "岗位与专业不符，暂不确认"}, headers=_student("AG-A"))
    assert r.status_code == 200 and r.json()["data"]["status"] == "REJECTED"


def test_owner_and_scope(client, db_mode):
    ids = _seed(db_mode)
    # 王芳 的学生 B 生成协议
    bid = client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_b"])}, headers=_mentor("王芳")).json()["data"]["id"]
    # 刘强 越权下发 → 403
    assert client.post(f"{INT}/agreements/{bid}/issue", headers=_mentor("刘强")).status_code == 403
    # 刘强 也给自己学生 A 建一个
    client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=_mentor("刘强"))
    # 数据范围：管理员看 2，刘强看 1
    assert client.get(f"{INT}/agreements", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/agreements", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_staff_reject_pending(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    aid = client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=h).json()["data"]["id"]
    client.post(f"{INT}/agreements/{aid}/issue", headers=h)
    # 驳回需原因≥5字
    assert client.post(f"{INT}/agreements/{aid}/reject", json={"reason": "no"}, headers=h).status_code == 400
    ok = client.post(f"{INT}/agreements/{aid}/reject", json={"reason": "信息有误需重新生成"}, headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "REJECTED"


def test_student_forbidden_on_pc(client, db_mode):
    ids = _seed(db_mode)
    assert client.get(f"{INT}/agreements", headers=_student("AG-A")).status_code == 403
    assert client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=_student("AG-A")).status_code == 403


def test_export(client, db_mode):
    ids = _seed(db_mode)
    client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])}, headers=_mentor("刘强"))
    res = client.post(f"{INT}/agreements/export", headers=_admin(client))
    assert res.status_code == 200
    d = res.json()["data"]
    assert d["filename"].endswith(".xlsx") and d["rowCount"] == 1 and d["contentBase64"]


def test_generate_with_template_rendered_body(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    tpl = client.post("/api/v1/internship/agreement-templates", headers=_admin(client), json={
        "name": "测试三方协议", "category": "三方协议", "version": "v1.0",
        "body": "甲方{{schoolName}} 乙方{{companyName}} 学生{{studentName}}",
        "variables": [{"key": "studentName", "label": "学生姓名", "example": "甲"}]
    }).json()
    tid = tpl["data"]["id"]
    client.post(f"/api/v1/internship/agreement-templates/{tid}/status",
                headers=_admin(client), json={"action": "ENABLE"})
    gen = client.post(f"{INT}/agreements",
                      json={"internshipId": str(ids["rec_a"]), "templateId": tid}, headers=h)
    assert gen.status_code == 200 and gen.json()["data"]["hasRenderedBody"] is True
    aid = gen.json()["data"]["id"]
    detail = client.get(f"{INT}/agreements/{aid}", headers=h).json()["data"]
    assert "甲" in detail["renderedBody"]
    assert "测试企业" in detail["renderedBody"]
    # PDF 套打
    pdf = client.post(f"{INT}/agreements/{aid}/pdf", headers=h)
    assert pdf.status_code == 200
    pd = pdf.json()["data"]
    assert pd["filename"].endswith(".pdf") and pd["contentBase64"]
    import base64
    assert base64.b64decode(pd["contentBase64"])[:4] == b"%PDF"
    # 下发后学生端可见渲染正文
    client.post(f"{INT}/agreements/{aid}/issue", headers=h)
    my = client.get("/api/v1/mobile/internship/agreements", headers=_student("AG-A")).json()["data"]
    assert my and my[0]["renderedBody"] and "甲" in my[0]["renderedBody"]
    stu_detail = client.get(f"/api/v1/mobile/internship/agreements/{aid}", headers=_student("AG-A")).json()["data"]
    assert "甲" in stu_detail["renderedBody"] and stu_detail["status"] == "PENDING_STUDENT"

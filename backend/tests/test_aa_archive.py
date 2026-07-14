"""教务归档（/academic-affairs/archive/*）端点测试（R7）。

覆盖：建归档批次(一学期一批次,重复409)→完整性检查(9数据域,有数据present)→
确认归档(学期status→ARCHIVED,D-04)→MISSING强制归档→取消→学生越权403。
MySQL-only（db_mode 夹具）。口径核对施工包 §7/§8。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode, with_data=True):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaTerm, StudentProfile
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    if with_data:
        db.add(StudentProfile(tenant_id=TID, student_no="AR2401", real_name="档甲",
                              student_status="NORMAL", status="ACTIVE"))
        db.add(AaProgram(tenant_id=TID, program_name="软件技术培养方案", status="PUBLISHED"))
    db.commit()
    ids = {"term": term.id}
    db.close()
    return ids


def test_ar1_batch_and_check(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    # 同学期重复 409
    assert client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).status_code == 409
    # 完整性检查：9 数据域
    chk = client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin).json()["data"]
    detail = client.get(f"{BASE}/archive/batches/{bid}", headers=admin).json()["data"]
    assert len(detail["items"]) == 9
    # 学籍/培养方案有数据 present
    doms = {i["domain"]: i for i in detail["items"]}
    assert doms["STUDENT_STATUS"]["present"] is True
    assert doms["PROGRAM"]["present"] is True


def test_ar2_confirm_archive_freezes_term(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    chk = client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin).json()["data"]
    # 有缺失域时非强制确认 409
    if chk["status"] == "MISSING_ITEMS":
        assert client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": False}).status_code == 409
    # 强制归档
    r = client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True}).json()
    assert r["code"] == 0 and r["data"]["status"] == "ARCHIVED"
    # 学期已封存 ARCHIVED
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(AaTerm.id == ids["term"], AaTerm.tenant_id == TID).first()
    assert term.status == "ARCHIVED"
    db.close()


def test_ar3_unfreeze_restores_term(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    # 特批解冻（school_admin01=SCHOOL_ADMIN；原因过短 400）
    assert client.post(f"{BASE}/archive/batches/{bid}/unfreeze", headers=admin, json={"reason": "x"}).status_code == 400
    r = client.post(f"{BASE}/archive/batches/{bid}/unfreeze", headers=admin, json={"reason": "发现成绩漏归档需补"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "DRAFT"
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(AaTerm.id == ids["term"], AaTerm.tenant_id == TID).first()
    assert term.status == "PUBLISHED"
    db.close()


def test_ar4_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("档甲", "AR2401")
    assert client.post(f"{BASE}/archive/batches", headers=stu, json={}).status_code == 403
    assert client.get(f"{BASE}/archive/batches", headers=stu).status_code == 403

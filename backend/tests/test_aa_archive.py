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


# ═══════════ Tier1 续工（10/11/12 三级卡）：归档缺失提醒 / 批量归档 guard / 归档导出 ═══════════

def test_ar5_precheck_realtime_no_batch(client, db_mode):
    """10 卡：归档缺失提醒——不建批次，直接实时预检；9 域齐全，已播种域 present。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/archive/precheck", headers=admin, params={"termId": str(ids["term"])}).json()
    assert r["code"] == 0
    domains = r["data"]["domains"]
    assert len(domains) == 9
    doms = {d["domain"]: d for d in domains}
    assert doms["STUDENT_STATUS"]["status"] == "OK"
    assert doms["PROGRAM"]["status"] == "OK"
    assert doms["EXAM"]["status"] == "MISSING"  # 未播种考务数据
    # 未创建任何批次（precheck 不落库）
    assert client.get(f"{BASE}/archive/batches", headers=admin).json()["data"]["total"] == 0


def test_ar6_precheck_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("档甲", "AR2401")
    assert client.get(f"{BASE}/archive/precheck", headers=stu).status_code == 403


def test_ar7_guard_term_writable_blocks_registration_after_archive(client, db_mode):
    """11 卡 §6.2：学期归档后，创建注册批次应 409 TERM_ARCHIVED（guard_term_writable 接入点）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    # 学期已 ARCHIVED：新建注册批次应 409
    r = client.post(f"{BASE}/registration-batches", headers=admin,
                    json={"batchName": "补测注册批次", "termId": str(ids["term"])})
    assert r.status_code == 409
    assert r.json()["code"] != 0
    # 重新发布该学期同样应 409
    r2 = client.post(f"{BASE}/terms/{ids['term']}/publish", headers=admin)
    assert r2.status_code == 409


def test_ar8_guard_does_not_block_other_term(client, db_mode):
    """guard 只拦截目标学期本身；新建其他学期的注册批次不受影响（避免过度拦截）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    # 无 termId 的注册批次（字典类/未关联学期）不应被拦截
    r = client.post(f"{BASE}/registration-batches", headers=admin, json={"batchName": "不挂学期批次"})
    assert r.status_code == 200


def test_ar9_export_requires_archived(client, db_mode):
    """12 卡：批次未 ARCHIVED 时导出应 409。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    r = client.get(f"{BASE}/archive/batches/{bid}/export", headers=admin, params={"purpose": "越权测试导出"})
    assert r.status_code == 409


def test_ar10_export_item_and_all_after_archive(client, db_mode):
    """12 卡：归档后单域导出(xlsx)+打包导出(zip)+下载记录留痕。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    # 用途 <5 字 → 400
    r0 = client.get(f"{BASE}/archive/batches/{bid}/items/STUDENT_STATUS/export", headers=admin, params={"purpose": "x"})
    assert r0.status_code == 400
    # 单域导出 → xlsx (PK 魔数)
    r1 = client.get(f"{BASE}/archive/batches/{bid}/items/STUDENT_STATUS/export", headers=admin,
                    params={"purpose": "上级检查留档核对"})
    assert r1.status_code == 200 and r1.content[:2] == b"PK"
    # 未知域 → 404
    r2 = client.get(f"{BASE}/archive/batches/{bid}/items/NOT_A_DOMAIN/export", headers=admin,
                    params={"purpose": "上级检查留档核对"})
    assert r2.status_code == 404
    # 打包下载全部 → zip (PK 魔数)
    r3 = client.get(f"{BASE}/archive/batches/{bid}/export", headers=admin, params={"purpose": "打包留存备查"})
    assert r3.status_code == 200 and r3.content[:2] == b"PK"
    # 下载记录：至少 2 条（单域+打包）
    log = client.get(f"{BASE}/archive/batches/{bid}/download-log", headers=admin).json()["data"]
    assert len(log) >= 2
    actions = {x["action"] for x in log}
    assert "ITEM_EXPORT_DOWNLOAD" in actions and "BATCH_EXPORT_DOWNLOAD" in actions


def test_ar12_guard_blocks_status_change_submit_on_current_archived_term(client, db_mode):
    """11 卡§6.2：AaStatusChange 无强 term_id 外键，guard 降级为「当前学期」判据——
    当前学期归档后，学籍异动 submit 应 409（真实生效，已如实注释精度局限）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    stu = db.query(StudentProfile).filter(StudentProfile.tenant_id == TID, StudentProfile.student_no == "AR2401").first()
    student_id = stu.id
    db.close()
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    r = client.post(f"{BASE}/status-changes", headers=admin,
                    json={"studentId": str(student_id), "changeType": "WITHDRAW", "reason": "归档后异动测试"})
    assert r.status_code == 409


def test_ar11_export_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True})
    stu = _stu_token("档甲", "AR2401")
    r = client.get(f"{BASE}/archive/batches/{bid}/export", headers=stu, params={"purpose": "越权下载测试"})
    assert r.status_code == 403

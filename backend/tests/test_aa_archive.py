"""教务归档（/academic-affairs/archive/*）端点测试（Stage C3）。

覆盖：建归档批次→十三域完整性检查→正式归档不可逆→Manifest V1→归档后普通
unfreeze 永久 409→学期写保护→归档导出。语义域本身另由 semantic-gates 测试；
本文件需要进入 ARCHIVED 的用例显式把批次置为 READY，并 mock 同事务实时复核为通过，
避免用旧 ``force=true`` 绕过生产归档门禁。
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


def _make_ready(monkeypatch, bid):
    """Only for endpoint workflow tests; semantic archive gates have their own real tests."""
    from app.db.session import get_sessionmaker
    from app.models import AaArchiveBatch
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest_svc

    db = get_sessionmaker()()
    batch = db.query(AaArchiveBatch).filter(
        AaArchiveBatch.id == int(bid), AaArchiveBatch.tenant_id == TID
    ).first()
    batch.status = "READY"
    batch.missing_count = 0
    db.commit()
    db.close()

    monkeypatch.setattr(
        manifest_svc,
        "_live_manifest_parts",
        lambda _db, _batch: (
            {"TEST_READY": 1},
            {"TEST_READY": "a" * 64},
            {"TEST_READY": 1},
        ),
    )


def _archive_ready(client, admin, bid, monkeypatch):
    _make_ready(monkeypatch, bid)
    r = client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0 and body["data"]["status"] == "ARCHIVED"
    assert body["data"]["manifestVersion"] == 1
    assert body["data"]["manifestHash"]
    return body["data"]


def test_ar1_batch_and_check(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).status_code == 409
    client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin)
    detail = client.get(f"{BASE}/archive/batches/{bid}", headers=admin).json()["data"]
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_svc
    assert len(detail["items"]) == len(archive_svc._DOMAINS)
    doms = {i["domain"]: i for i in detail["items"]}
    assert "STUDENT_STATUS" in doms and "PROGRAM" in doms


def test_ar2_confirm_archive_creates_manifest_and_freezes_term(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    chk = client.post(f"{BASE}/archive/batches/{bid}/check", headers=admin).json()["data"]
    if chk["status"] == "MISSING_ITEMS":
        assert client.post(f"{BASE}/archive/batches/{bid}/confirm", headers=admin, json={"force": True}).status_code == 409
    payload = _archive_ready(client, admin, bid, monkeypatch)

    from app.db.session import get_sessionmaker
    from app.models import AaTerm, ArchiveManifest
    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(AaTerm.id == ids["term"], AaTerm.tenant_id == TID).first()
    manifest = db.query(ArchiveManifest).filter(
        ArchiveManifest.archive_batch_id == int(bid), ArchiveManifest.tenant_id == TID
    ).one()
    assert term.status == "ARCHIVED"
    assert manifest.version_no == 1 and manifest.supersedes_id is None
    assert manifest.manifest_hash == payload["manifestHash"]
    db.close()


def test_ar3_archived_batch_cannot_be_unfrozen(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    assert client.post(f"{BASE}/archive/batches/{bid}/unfreeze", headers=admin, json={"reason": "x"}).status_code == 400
    r = client.post(f"{BASE}/archive/batches/{bid}/unfreeze", headers=admin, json={"reason": "发现成绩漏归档需补"})
    assert r.status_code == 409
    body = r.json()
    # Public API uses the platform-wide numeric error envelope; the internal
    # AppException code remains TERM_ARCHIVED and is covered by the unit contract.
    assert body["code"] != 0
    assert "归档后纠错" in body["message"]
    from app.db.session import get_sessionmaker
    from app.models import AaTerm
    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(AaTerm.id == ids["term"], AaTerm.tenant_id == TID).first()
    assert term.status == "ARCHIVED"
    db.close()


def test_ar4_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("档甲", "AR2401")
    assert client.post(f"{BASE}/archive/batches", headers=stu, json={}).status_code == 403
    assert client.get(f"{BASE}/archive/batches", headers=stu).status_code == 403


def test_ar5_precheck_realtime_no_batch(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/archive/precheck", headers=admin, params={"termId": str(ids["term"])}).json()
    assert r["code"] == 0
    domains = r["data"]["domains"]
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_svc
    assert len(domains) == len(archive_svc._DOMAINS)
    assert client.get(f"{BASE}/archive/batches", headers=admin).json()["data"]["total"] == 0


def test_ar6_precheck_student_forbidden(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("档甲", "AR2401")
    assert client.get(f"{BASE}/archive/precheck", headers=stu).status_code == 403


def test_ar7_guard_term_writable_blocks_registration_after_archive(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    r = client.post(f"{BASE}/registration-batches", headers=admin,
                    json={"batchName": "补测注册批次", "termId": str(ids["term"])})
    assert r.status_code == 409
    r2 = client.post(f"{BASE}/terms/{ids['term']}/publish", headers=admin)
    assert r2.status_code == 409


def test_ar8_guard_does_not_block_other_term(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    r = client.post(f"{BASE}/registration-batches", headers=admin, json={"batchName": "不挂学期批次"})
    assert r.status_code == 200


def test_ar9_export_requires_archived(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    r = client.get(f"{BASE}/archive/batches/{bid}/export", headers=admin, params={"purpose": "越权测试导出"})
    assert r.status_code == 409


def test_ar10_export_item_and_all_after_archive(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    r0 = client.get(f"{BASE}/archive/batches/{bid}/items/STUDENT_STATUS/export", headers=admin, params={"purpose": "x"})
    assert r0.status_code == 400
    r1 = client.get(f"{BASE}/archive/batches/{bid}/items/STUDENT_STATUS/export", headers=admin,
                    params={"purpose": "上级检查留档核对"})
    assert r1.status_code == 200 and r1.content[:2] == b"PK"
    r2 = client.get(f"{BASE}/archive/batches/{bid}/items/NOT_A_DOMAIN/export", headers=admin,
                    params={"purpose": "上级检查留档核对"})
    assert r2.status_code == 404
    r3 = client.get(f"{BASE}/archive/batches/{bid}/export", headers=admin, params={"purpose": "打包留存备查"})
    assert r3.status_code == 200 and r3.content[:2] == b"PK"
    log = client.get(f"{BASE}/archive/batches/{bid}/download-log", headers=admin).json()["data"]
    assert len(log) >= 2
    actions = {x["action"] for x in log}
    assert "ITEM_EXPORT_DOWNLOAD" in actions and "BATCH_EXPORT_DOWNLOAD" in actions


def test_ar11_export_student_forbidden(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    stu = _stu_token("档甲", "AR2401")
    r = client.get(f"{BASE}/archive/batches/{bid}/export", headers=stu, params={"purpose": "越权下载测试"})
    assert r.status_code == 403


def test_ar12_guard_blocks_status_change_submit_on_current_archived_term(client, db_mode, monkeypatch):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    stu = db.query(StudentProfile).filter(StudentProfile.tenant_id == TID, StudentProfile.student_no == "AR2401").first()
    student_id = stu.id
    db.close()
    bid = client.post(f"{BASE}/archive/batches", headers=admin, json={"termId": str(ids["term"])}).json()["data"]["batchId"]
    _archive_ready(client, admin, bid, monkeypatch)
    r = client.post(f"{BASE}/status-changes", headers=admin,
                    json={"studentId": str(student_id), "changeType": "WITHDRAW", "reason": "归档后异动测试"})
    assert r.status_code == 409

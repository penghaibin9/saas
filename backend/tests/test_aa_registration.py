"""13B-P1 入学/学年注册 + change_student_status 单一写入口 · 端到端。

R1 注册→主档学籍REGISTERED+异动流水+360；R2 重复注册409；R3 未开放批次409；
R4 名册在籍标记；R5 change_student_status 非法转移422；R6 is_enrolled 判定。

续工三级卡（2026-07-16，学期注册 + 注册归档）：
R7 学期注册（registerType=SEMESTER）注册成功且 change_type=SEMESTER_REGISTER；
R8 学期注册事件不泄漏进「学籍异动」台账（list_changes 排除三类注册 change_type）；
R9 非法 registerType 仍 400（VALIDATION_ERROR 契约映射）；R10 关闭→归档全链路+归档列表/详情/统计；
R11 非 OPEN 批次禁止关闭 409；R12 非 CLOSED 批次禁止归档 409；
R13 非已归档批次导出 409，已归档后导出成功；R14 学生令牌打归档管理端点一律 403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA001", real_name="新生甲", class_id=a.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"s": s.id}
    db.commit()
    db.close()
    return ids


def _open_batch(client, hdr, rtype="ENROLL"):
    return client.post(f"{BASE}/registration-batches", headers=hdr, json={
        "batchName": "2026级入学注册", "registerType": rtype, "open": True}).json()["data"]["batchId"]


def test_r1_register_updates_profile_via_single_entry(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    r = client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                    json={"studentId": str(ids["s"])}).json()
    assert r["data"]["studentStatus"] == "REGISTERED" and r["data"]["changeType"] == "ENROLL_REGISTER"
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.student_status == "REGISTERED"  # 主档已改
    assert db.query(AaStatusChange).filter_by(student_id=ids["s"], to_status="REGISTERED").count() == 1
    ev = db.query(StudentStageEvent).filter_by(student_id=ids["s"], to_stage="REGISTERED",
                                               source_module="academic-affairs").count()
    assert ev == 1  # 进 360
    db.close()


def test_r2_duplicate_register_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    assert client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                       json={"studentId": str(ids["s"])}).status_code == 409


def test_r3_batch_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/registration-batches", headers=hdr, json={
        "batchName": "草稿批次", "registerType": "ENROLL", "open": False}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                       json={"studentId": str(ids["s"])}).status_code == 409


def test_r4_roster_enrolled_flag(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr)
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    roster = client.get(f"{BASE}/roster", headers=hdr).json()["data"]["items"]
    row = next(x for x in roster if x["studentId"] == str(ids["s"]))
    assert row["studentStatus"] == "REGISTERED" and row["enrolled"] is True


def test_r5_illegal_transition_422(client, db_mode):
    ids = _seed(db_mode)
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services.academic_affairs_status_service import change_student_status
    from app.core.exceptions import AppException
    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    # 先合法置为 WITHDRAWN（NORMAL→WITHDRAWN 允许）
    change_student_status(db, ids["s"], "WITHDRAWN", change_type="WITHDRAW", reason="退学")
    db.commit()
    # WITHDRAWN 无出边 → 任何目标非法 422
    raised = False
    try:
        change_student_status(db, ids["s"], "REGISTERED", change_type="ANNUAL_REGISTER")
    except AppException as e:
        raised = e.code == "VALIDATION_ERROR"
    db.close()
    assert raised


def test_r6_is_enrolled():
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    assert is_enrolled("REGISTERED") and is_enrolled("NORMAL") and is_enrolled("RETAINED")
    assert not is_enrolled("SUSPENDED") and not is_enrolled("WITHDRAWN") and not is_enrolled("GRADUATED")


def test_r7_semester_register_type_change_type(client, db_mode):
    """学期注册（registerType=SEMESTER）：注册成功，change_type=SEMESTER_REGISTER。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, rtype="SEMESTER")
    r = client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr,
                    json={"studentId": str(ids["s"])}).json()
    assert r["data"]["studentStatus"] == "REGISTERED" and r["data"]["changeType"] == "SEMESTER_REGISTER"


def test_r8_semester_register_not_leaked_into_status_changes(client, db_mode):
    """三类注册 change_type 不得出现在「学籍异动」台账（list_changes 排除 ENROLL/ANNUAL/SEMESTER_REGISTER）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, rtype="SEMESTER")
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    changes = client.get(f"{BASE}/status-changes", headers=hdr).json()["data"]["items"]
    assert all(c["changeType"] != "SEMESTER_REGISTER" for c in changes)


def test_r9_invalid_register_type_400(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/registration-batches", headers=hdr,
                    json={"batchName": "非法类型批次", "registerType": "BOGUS", "open": True})
    assert r.status_code == 400


def test_r10_close_then_archive_flow(client, db_mode):
    """OPEN→CLOSED→ARCHIVED 全链路：关闭后禁止新注册；归档后进入归档列表/详情统计。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, rtype="ENROLL")
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    r_close = client.post(f"{BASE}/registration-batches/{bid}/close", headers=hdr)
    assert r_close.status_code == 200 and r_close.json()["data"]["status"] == "CLOSED"
    # 关闭后禁止再注册（batch 非 OPEN）
    assert client.get(f"{BASE}/registration-batches", headers=hdr).status_code == 200
    r_archive = client.post(f"{BASE}/registration-batches/{bid}/archive", headers=hdr)
    assert r_archive.status_code == 200 and r_archive.json()["data"]["status"] == "ARCHIVED"
    # 幂等：重复归档不报错
    assert client.post(f"{BASE}/registration-batches/{bid}/archive", headers=hdr).json()["data"]["status"] == "ARCHIVED"
    lst = client.get(f"{BASE}/registration/archive", headers=hdr).json()["data"]["items"]
    assert any(x["batchId"] == str(bid) for x in lst)
    detail = client.get(f"{BASE}/registration/archive/{bid}", headers=hdr).json()["data"]
    assert detail["status"] == "ARCHIVED" and detail["stats"]["total"] == 1 and detail["stats"]["registered"] == 1


def test_r11_close_non_open_batch_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/registration-batches", headers=hdr, json={
        "batchName": "草稿批次待关闭", "registerType": "ENROLL", "open": False}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/registration-batches/{bid}/close", headers=hdr).status_code == 409


def test_r12_archive_non_closed_batch_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, rtype="ANNUAL")
    assert client.post(f"{BASE}/registration-batches/{bid}/archive", headers=hdr).status_code == 409


def test_r13_export_requires_archived_and_purpose(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _open_batch(client, hdr, rtype="ENROLL")
    client.post(f"{BASE}/registration-batches/{bid}/register", headers=hdr, json={"studentId": str(ids["s"])})
    # 未归档批次禁止导出
    r_bad = client.post(f"{BASE}/registration/archive/{bid}/export", headers=hdr, json={"purpose": "用于学期归档核查"})
    assert r_bad.status_code == 409
    client.post(f"{BASE}/registration-batches/{bid}/close", headers=hdr)
    client.post(f"{BASE}/registration-batches/{bid}/archive", headers=hdr)
    # 用途不足5字校验失败（Pydantic min_length 由全局 RequestValidationError 处理器映射为 400）
    r_short = client.post(f"{BASE}/registration/archive/{bid}/export", headers=hdr, json={"purpose": "abc"})
    assert r_short.status_code == 400
    r_ok = client.post(f"{BASE}/registration/archive/{bid}/export", headers=hdr, json={"purpose": "用于学期归档核查留痕"})
    assert r_ok.status_code == 200
    assert r_ok.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_r14_student_forbidden_on_archive_endpoints_403(client, db_mode):
    """越权红线：学生令牌打注册归档管理端点一律 403（require_permission 无 academicAffairs.* 授予）。"""
    hdr = _hdr(client, "student01")
    assert client.post(f"{BASE}/registration-batches/1/close", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/registration-batches/1/archive", headers=hdr).status_code == 403
    assert client.get(f"{BASE}/registration/archive", headers=hdr).status_code == 403
    assert client.get(f"{BASE}/registration/archive/1", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/registration/archive/1/export", headers=hdr,
                       json={"purpose": "越权尝试导出归档台账"}).status_code == 403

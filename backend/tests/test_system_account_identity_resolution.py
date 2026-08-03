"""SYS-03 账号稳定主体、身份绑定与账号异常（真库）。

对应必测 SYS03-T01～T04：
学号工号修改后主体不变 / 同名重复手机号不串身份 / 停用立即使请求失效 / 批量操作逐项返回结果。
"""
import pytest

from app.core.exceptions import AppException
from app.services import account_identity_resolution_service as ident

MAIN_TENANT_ID = 1000000000000000001
OTHER_TENANT_ID = 8703


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _ensure_tenant(tenant_id: int = MAIN_TENANT_ID, code: str = "demo") -> None:
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, int(tenant_id)) is None:
            db.add(Tenant(id=int(tenant_id), tenant_code=code,
                          school_name=f"身份测试学校{tenant_id}", status="ACTIVE"))
            db.commit()


def _make_user(login_name: str, real_name: str = "测试用户", *, tenant_id: int = MAIN_TENANT_ID,
               user_type: str = "STUDENT", phone: str | None = None,
               password: str | None = None) -> int:
    from app.core.field_crypto import encrypt_field, hash_sensitive
    from app.core.security import hash_password
    from app.models import User

    _ensure_tenant(tenant_id, "demo" if tenant_id == MAIN_TENANT_ID else f"t{tenant_id}")
    with _session() as db:
        row = User(tenant_id=tenant_id, login_name=login_name, real_name=real_name,
                   password_hash=hash_password(password or "Init123456"),
                   user_type=user_type, status="ACTIVE")
        if phone:
            row.phone_encrypted = encrypt_field(phone)
            row.phone_hash = hash_sensitive(phone, "phone")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_student(student_no: str, real_name: str = "测试学生", *,
                  tenant_id: int = MAIN_TENANT_ID) -> int:
    from app.models import StudentProfile

    with _session() as db:
        row = StudentProfile(tenant_id=tenant_id, student_no=student_no, real_name=real_name,
                             current_stage="IN_SCHOOL", student_status="NORMAL", status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _bind(student_id: int, user_id: int, *, tenant_id: int = MAIN_TENANT_ID,
          source: str = "IDENTITY_IMPORT") -> int:
    from datetime import datetime

    from app.models import StudentAccountLink, StudentProfile, User

    with _session() as db:
        profile = db.get(StudentProfile, student_id)
        account = db.get(User, user_id)
        row = StudentAccountLink(
            tenant_id=tenant_id, student_id=student_id, user_id=user_id,
            link_status="ACTIVE", source=source,
            bound_login_name=account.login_name, bound_student_no=profile.student_no,
            bound_at=datetime.now().replace(microsecond=0))
        db.add(row)
        db.commit()
        return int(row.id)


def _issue_codes(identity: dict) -> set:
    return {i["code"] for i in identity["issues"]}


# ── SYS03-T01：学号/工号/登录名变了，主体不能变 ────────────────────────────────
def test_t01_identity_survives_student_no_and_login_name_change(db_mode):
    student_id = _make_student("2026001", "张三")
    user_id = _make_user("2026001", "张三")
    _bind(student_id, user_id)

    before = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)
    assert before["studentId"] == str(student_id)
    assert before["identitySource"] == ident.SOURCE_LINK
    assert before["subjectKey"] == f"user:{user_id}"

    # 学号与登录名同时改掉（学籍更正 + 账号改名）
    from app.models import StudentProfile, User

    with _session() as db:
        db.get(StudentProfile, student_id).student_no = "2026999"
        db.get(User, user_id).login_name = "zhangsan_new"
        db.commit()

    after = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)
    assert after["userId"] == before["userId"], "账号主体不得随登录名变化"
    assert after["studentId"] == str(student_id), "学籍主体不得随学号变化"
    assert after["studentNo"] == "2026999", "学号是属性，应跟随主档更新"
    assert after["identitySource"] == ident.SOURCE_LINK
    assert ident.ISSUE_STALE_SNAPSHOT in _issue_codes(after), "绑定快照过期应提示但不影响解析"

    reverse = ident.resolve_by_student(student_id, tenant_id=MAIN_TENANT_ID)
    assert reverse is not None and reverse["userId"] == str(user_id)


# ── SYS03-T02：同名 + 同手机号，绝不串身份 ───────────────────────────────────
def test_t02_same_name_same_phone_never_crosses_identity(db_mode):
    phone = "13800001111"
    s1 = _make_student("2026101", "李伟")
    s2 = _make_student("2026102", "李伟")
    u1 = _make_user("2026101", "李伟", phone=phone)
    u2 = _make_user("2026102", "李伟", phone=phone)
    _bind(s1, u1)
    _bind(s2, u2)

    i1 = ident.effective_identity(u1, tenant_id=MAIN_TENANT_ID)
    i2 = ident.effective_identity(u2, tenant_id=MAIN_TENANT_ID)
    assert i1["studentId"] == str(s1) and i2["studentId"] == str(s2)
    assert i1["studentId"] != i2["studentId"]
    assert ident.ISSUE_DUPLICATE_NAME_PHONE in _issue_codes(i1)
    assert ident.ISSUE_DUPLICATE_NAME_PHONE in _issue_codes(i2)
    assert str(u2) in [x for i in i1["issues"]
                       for x in (i.get("otherUserIds") or [])]

    # 没有绑定、登录名也对不上任何学号的账号：只能是"未绑定"，不许按姓名/手机号认领
    u3 = _make_user("temp_login_003", "李伟", phone=phone)
    i3 = ident.effective_identity(u3, tenant_id=MAIN_TENANT_ID)
    assert i3["studentId"] == ""
    assert ident.ISSUE_NO_BINDING in _issue_codes(i3)


# ── SYS03-T03：停用立即失效 ─────────────────────────────────────────────────
def _login(client, login_name: str, password: str) -> dict:
    result = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": login_name,
        "password": password, "clientType": "PC"}).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}


def _grant_role(user_id: int, role_code: str = "STUDENT") -> None:
    from app.models import Role, UserRole

    with _session() as db:
        from sqlalchemy import select

        role = db.scalars(select(Role).where(
            Role.tenant_id == MAIN_TENANT_ID, Role.role_code == role_code)).first()
        if role is None:
            role = Role(tenant_id=MAIN_TENANT_ID, role_code=role_code, role_name=role_code,
                        role_type="SYSTEM", status="ACTIVE")
            db.add(role)
            db.flush()
        db.add(UserRole(tenant_id=MAIN_TENANT_ID, user_id=user_id, role_id=role.id,
                        status="ACTIVE"))
        db.commit()


def test_t03_disable_invalidates_request_immediately(client, auth_headers, db_mode):
    user_id = _make_user("stu_disable_01", "待停用同学", password="Init123456")
    _grant_role(user_id)
    victim = _login(client, "stu_disable_01", "Init123456")
    assert client.get("/api/v1/auth/me", headers=victim).json()["code"] == 0

    disabled = client.put(f"/api/v1/system/users/{user_id}/status", headers=auth_headers,
                          json={"action": "DISABLE", "reason": "毕业离校账号停用"}).json()
    assert disabled["code"] == 0

    after = client.get("/api/v1/auth/me", headers=victim)
    assert after.status_code == 401, after.text


def test_t03b_bulk_scope_disable_also_invalidates_cache(client, auth_headers, db_mode):
    """按范围批量停用原来不清主体缓存，被停用的人在缓存 TTL 内还能继续访问。"""
    user_id = _make_user("stu_bulk_01", "批量停用同学", password="Init123456")
    _grant_role(user_id)
    victim = _login(client, "stu_bulk_01", "Init123456")
    assert client.get("/api/v1/auth/me", headers=victim).json()["code"] == 0

    result = client.put("/api/v1/system/user-batch-status", headers=auth_headers,
                        json={"action": "DISABLE", "accountType": "STUDENT", "scope": "SCHOOL",
                              "confirmSchoolScope": True,
                              "reason": "学年结束批量停用学生账号"}).json()
    assert result["code"] == 0 and result["data"]["count"] >= 1

    after = client.get("/api/v1/auth/me", headers=victim)
    assert after.status_code == 401, after.text


# ── SYS03-T04：批量操作逐项返回结果 ─────────────────────────────────────────
def test_t04_batch_status_returns_per_item_results(client, auth_headers, db_mode):
    ok_id = _make_user("stu_batch_ok", "可停用同学")
    missing_id = 987654321
    result = client.put("/api/v1/system/user-batch-status", headers=auth_headers,
                        json={"action": "DISABLE", "ids": [ok_id, missing_id],
                              "reason": "批量停用逐项结果验证"}).json()
    assert result["code"] == 0
    rows = {row["id"]: row for row in result["data"]["results"]}
    assert rows[str(ok_id)]["status"] == "OK"
    assert rows[str(missing_id)]["status"] == "FAILED"
    assert rows[str(missing_id)]["message"]
    assert result["data"]["total"] == 2
    assert result["data"]["succeeded"] == 1 and result["data"]["failed"] == 1


def test_t04b_batch_repair_returns_per_item_results(db_mode):
    s1 = _make_student("2026201", "批量甲")
    u1 = _make_user("2026201", "批量甲")
    s2 = _make_student("2026202", "批量乙")
    u2 = _make_user("other_login_202", "批量乙")
    _bind(s2, u2)  # 已绑定，重复修复应逐项失败而不是整批炸

    out = ident.batch_repair(
        [{"userId": u1, "studentId": s1}, {"userId": u2, "studentId": s2},
         {"userId": "abc", "studentId": s1}],
        reason="批量修复历史绑定", tenant_id=MAIN_TENANT_ID)
    assert out["total"] == 3 and out["succeeded"] == 1 and out["failed"] == 2
    statuses = [r["status"] for r in out["results"]]
    assert statuses == ["OK", "FAILED", "FAILED"]
    assert ident.effective_identity(u1, tenant_id=MAIN_TENANT_ID)["identitySource"] == ident.SOURCE_LINK


# ── 登录名兜底 → 结构化绑定 ─────────────────────────────────────────────────
def test_legacy_login_match_is_flagged_and_repairable(db_mode):
    student_id = _make_student("2026301", "兜底同学")
    user_id = _make_user("2026301", "兜底同学")

    legacy = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)
    assert legacy["identitySource"] == ident.SOURCE_LEGACY_LOGIN
    assert legacy["studentId"] == str(student_id)
    assert ident.ISSUE_LEGACY_LOGIN_MATCH in _issue_codes(legacy)
    assert legacy["repairable"] is True

    fixed = ident.repair_binding(user_id, student_id=student_id, reason="转为结构化绑定",
                                 tenant_id=MAIN_TENANT_ID)
    assert fixed["identitySource"] == ident.SOURCE_LINK
    assert ident.ISSUE_LEGACY_LOGIN_MATCH not in _issue_codes(fixed)
    assert fixed["binding"]["linkId"]

    # 修复后再改学号，主体依旧稳定
    from app.models import StudentProfile

    with _session() as db:
        db.get(StudentProfile, student_id).student_no = "2026399"
        db.commit()
    assert ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)["studentId"] == str(student_id)


def test_student_no_cannot_be_duplicated_at_all(db_mode):
    """登录名兜底之所以还能用，前提是学号在库层唯一（uk_tenant_student_no 含软删）。

    这个前提一旦被放宽，兜底匹配就会歧义——服务里的 AMBIGUOUS_LEGACY 分支是那时的防线，
    这里先把前提本身锁住：同租户同学号根本插不进第二条。
    """
    from sqlalchemy.exc import IntegrityError

    _make_student("2026401", "重号甲")
    with pytest.raises(IntegrityError):
        _make_student("2026401", "重号乙")


def test_dangling_binding_is_reported(db_mode):
    student_id = _make_student("2026501", "已删学籍")
    user_id = _make_user("2026501", "已删学籍")
    _bind(student_id, user_id)
    from app.models import StudentProfile

    with _session() as db:
        db.get(StudentProfile, student_id).is_deleted = True
        db.commit()

    identity = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)
    assert identity["studentId"] == ""
    assert ident.ISSUE_DANGLING_BINDING in _issue_codes(identity)


# ── 修复绑定的边界 ───────────────────────────────────────────────────────────
def test_repair_rejects_cross_tenant_student(db_mode):
    foreign_student = _make_student("2026601", "他校学生", tenant_id=OTHER_TENANT_ID)
    user_id = _make_user("local_601", "本校同学")
    with pytest.raises(AppException) as caught:
        ident.repair_binding(user_id, student_id=foreign_student, reason="尝试跨校绑定",
                             tenant_id=MAIN_TENANT_ID)
    assert caught.value.code == "DATA_NOT_FOUND"


def test_repair_rejects_student_already_bound(db_mode):
    student_id = _make_student("2026701", "已绑同学")
    first = _make_user("2026701", "已绑同学")
    second = _make_user("2026701_dup", "已绑同学")
    _bind(student_id, first)

    with pytest.raises(AppException) as caught:
        ident.repair_binding(second, student_id=student_id, reason="重复绑定同一学籍",
                             tenant_id=MAIN_TENANT_ID)
    assert "已绑定其他账号" in caught.value.message


def test_repair_expected_version_conflict(db_mode):
    student_id = _make_student("2026801", "版本同学")
    user_id = _make_user("2026801", "版本同学")
    identity = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)

    ident.repair_binding(user_id, student_id=student_id, reason="首次修复绑定",
                         expected_version=identity["version"], tenant_id=MAIN_TENANT_ID)
    other = _make_student("2026802", "版本同学乙")
    with pytest.raises(AppException) as caught:
        ident.repair_binding(user_id, student_id=other, reason="拿旧版本重复提交",
                             expected_version=identity["version"], tenant_id=MAIN_TENANT_ID)
    assert caught.value.code == "DATA_CONFLICT"
    assert caught.value.http_status == 409


def test_unbind_keeps_history(db_mode):
    from sqlalchemy import select

    from app.models import StudentAccountLink

    student_id = _make_student("2026901", "解绑同学")
    user_id = _make_user("2026901_login", "解绑同学")
    _bind(student_id, user_id)

    after = ident.unbind(user_id, reason="账号错绑需要解除", tenant_id=MAIN_TENANT_ID)
    assert after["studentId"] == ""
    assert ident.ISSUE_NO_BINDING in _issue_codes(after)

    with _session() as db:
        rows = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == MAIN_TENANT_ID,
            StudentAccountLink.user_id == user_id)).all()
    assert len(rows) == 1 and rows[0].link_status == "REVOKED", "解绑必须留痕，不能物理删除"


# ── 教职工：主体就是账号本身 ─────────────────────────────────────────────────
def test_staff_identity_is_the_account_itself(db_mode):
    user_id = _make_user("T2026001", "王老师", user_type="TEACHER")
    identity = ident.effective_identity(user_id, tenant_id=MAIN_TENANT_ID)
    assert identity["accountType"] == "STAFF"
    assert identity["staffId"] == str(user_id), "教职工没有独立人事主档，staffId 恒等于 userId"
    assert identity["staffNo"] == "T2026001"
    assert identity["studentId"] == ""
    assert ident.ISSUE_NO_BINDING not in _issue_codes(identity)


# ── 异常队列与 HTTP 层 ───────────────────────────────────────────────────────
def test_identity_issue_queue(db_mode):
    good_student = _make_student("2027001", "正常同学")
    good_user = _make_user("2027001_login", "正常同学")
    _bind(good_student, good_user)
    _grant_role(good_user)
    broken = _make_user("2027002_login", "缺绑同学", user_type="STUDENT")

    queue = ident.identity_issues(tenant_id=MAIN_TENANT_ID)
    ids = {row["userId"] for row in queue["list"]}
    assert str(broken) in ids
    assert str(good_user) not in ids, "已结构化绑定且有角色的账号不应进异常队列"
    assert queue["counts"][ident.ISSUE_NO_BINDING] >= 1


def test_http_identity_endpoints(client, auth_headers, db_mode):
    student_id = _make_student("2027101", "接口同学")
    user_id = _make_user("2027101", "接口同学")

    got = client.get(f"/api/v1/system/accounts/{user_id}/effective-identity",
                     headers=auth_headers).json()
    assert got["code"] == 0
    assert got["data"]["identitySource"] == ident.SOURCE_LEGACY_LOGIN
    version = got["data"]["version"]

    fixed = client.post(f"/api/v1/system/accounts/{user_id}/repair-binding",
                        headers=auth_headers,
                        json={"studentId": str(student_id), "reason": "页面修复绑定",
                              "expectedVersion": version}).json()
    assert fixed["code"] == 0
    assert fixed["data"]["identitySource"] == ident.SOURCE_LINK

    stale = client.post(f"/api/v1/system/accounts/{user_id}/repair-binding",
                        headers=auth_headers,
                        json={"studentId": str(student_id), "reason": "用过期版本重试",
                              "expectedVersion": version})
    assert stale.status_code == 409

    issues = client.get("/api/v1/system/accounts/identity-issues", headers=auth_headers).json()
    assert issues["code"] == 0 and "list" in issues["data"]


def test_http_user_write_honours_expected_version(client, auth_headers, db_mode):
    user_id = _make_user("T2027201", "版本老师", user_type="TEACHER")
    detail = client.get(f"/api/v1/system/users/{user_id}", headers=auth_headers).json()
    assert detail["code"] == 0
    version = detail["data"]["version"]

    ok = client.put(f"/api/v1/system/users/{user_id}", headers=auth_headers,
                    json={"name": "版本老师改", "expectedVersion": version}).json()
    assert ok["code"] == 0

    stale = client.put(f"/api/v1/system/users/{user_id}", headers=auth_headers,
                       json={"name": "再改一次", "expectedVersion": version})
    assert stale.status_code == 409

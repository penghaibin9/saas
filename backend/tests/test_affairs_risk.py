"""13A-P4 风险预警闭环 · 端到端（真实 DB 模式）。

R1 建单+分派；R2 处置→关闭进360；R3 无处置记录关闭409；R4 来源去重409；
R5 升级+超时扫描幂等；R6 心理来源明细按角色隐藏；越权跨班403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (Role, SchoolClass, StudentProfile, TeacherStudentScope, User, UserRole)
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    # 风险责任人校验回归：一个持处置角色(COUNSELOR)的在职账号，一个无处置角色的账号（用于负向用例）。
    role = Role(tenant_id=TID, role_code="COUNSELOR", role_name="辅导员", status="ACTIVE")
    other_role = Role(tenant_id=TID, role_code="EMPLOYMENT_TEACHER", role_name="就业老师", status="ACTIVE")
    db.add(role); db.add(other_role); db.flush()
    owner = User(tenant_id=TID, login_name="risk_owner01", real_name="风险责任人",
                password_hash="x", user_type="TEACHER", status="ACTIVE")
    no_role_user = User(tenant_id=TID, login_name="risk_norole01", real_name="无处置角色账号",
                        password_hash="x", user_type="TEACHER", status="ACTIVE")
    db.add(owner); db.add(no_role_user); db.flush()
    db.add(UserRole(tenant_id=TID, user_id=owner.id, role_id=role.id, status="ACTIVE"))
    db.add(UserRole(tenant_id=TID, user_id=no_role_user.id, role_id=other_role.id, status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id,
           "owner": owner.id, "noRole": no_role_user.id}
    db.close()
    return ids


def _create(client, hdr, sid, source="ACADEMIC_WARNING", ref="1001", level="MEDIUM", detail="学业预警明细"):
    return client.post(f"{BASE}/risk/records", headers=hdr, json={
        "studentId": str(sid), "source": source, "sourceRefId": ref, "riskLevel": level,
        "title": "风险", "detail": detail})


def test_r1_create_assign(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    owner_id = str(ids["owner"])
    r = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": owner_id}).json()
    assert r["data"]["status"] == "ASSIGNED" and r["data"]["ownerId"] == owner_id


def test_r2_process_close_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": str(ids["owner"])})
    client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr, json={"content": "已约谈学生了解情况"})
    r = client.post(f"{BASE}/risk/records/{rid}/close", headers=hdr,
                    json={"conclusion": "学生情绪稳定，风险解除"}).json()
    assert r["data"]["status"] == "CLOSED"
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="RISK_CLOSED").count() == 1
    db.close()


def test_r3_close_without_handle_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": str(ids["owner"])})
    # ASSIGNED 无处置记录直接关闭 → 状态校验 409（close 要求 PROCESSING/FOLLOWING/ESCALATED）
    assert client.post(f"{BASE}/risk/records/{rid}/close", headers=hdr,
                       json={"conclusion": "无处置直接关闭"}).status_code == 409


def test_r4_duplicate_source_ref_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _create(client, hdr, ids["sa"], source="ACADEMIC_WARNING", ref="2001")
    assert _create(client, hdr, ids["sa"], source="ACADEMIC_WARNING", ref="2001").status_code == 409


def test_r5_escalate_and_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"], level="LOW").json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": str(ids["owner"])})
    client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr, json={"content": "首次处置记录"})
    r = client.post(f"{BASE}/risk/records/{rid}/escalate", headers=hdr, json={"reason": "情况恶化"}).json()
    assert r["data"]["status"] == "ESCALATED" and r["data"]["riskLevel"] == "MEDIUM"  # LOW→MEDIUM
    # 超时扫描幂等（无 ASSIGNED 超时项 → 0）
    r2 = client.post(f"{BASE}/risk/scan-timeout", headers=hdr).json()
    assert r2["data"]["escalated"] == 0


def test_r6_mental_detail_mask_reveal_reason_audit(client, db_mode):
    """心理来源明细：默认遮蔽（含列表）；授权角色+原因方可查看明文并写 SENSITIVE_VIEW 审计；非授权角色恒遮蔽。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _create(client, admin, ids["sa"], source="MENTAL", ref="3001",
                  detail="心理咨询详细记录").json()["data"]["riskId"]
    # 授权角色(SCHOOL_ADMIN) 无原因 → 明细仍遮蔽（详情默认仅摘要）
    d0 = client.get(f"{BASE}/risk/records/{rid}", headers=admin).json()["data"]
    assert d0["mentalMasked"] is True and "心理咨询详细记录" not in d0["detail"]
    # 列表恒遮蔽心理明细
    lst = client.get(f"{BASE}/risk/records", params={"source": "MENTAL"}, headers=admin).json()["data"]["items"]
    assert lst and all(it["mentalMasked"] is True for it in lst)
    # 授权角色 + 原因(≥5字) → 明细可见
    d1 = client.get(f"{BASE}/risk/records/{rid}", params={"reason": "危机干预需核对记录"},
                    headers=admin).json()["data"]
    assert d1["detail"] == "心理咨询详细记录" and d1["mentalMasked"] is False
    # 辅导员(普通教师，不在授权集) → 恒遮蔽，即便带原因
    d_c = client.get(f"{BASE}/risk/records/{rid}", params={"reason": "想看一下明细"},
                     headers=_hdr(client, "counselor01")).json()["data"]
    assert d_c["mentalMasked"] is True and "心理咨询详细记录" not in d_c["detail"]
    # SENSITIVE_VIEW 已落 t_security_audit_log
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    db = get_sessionmaker()()
    cnt = db.query(SecurityAuditLog).filter_by(action="SENSITIVE_VIEW").count()
    db.close()
    assert cnt >= 1


def test_r7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _create(client, admin, ids["sb"], ref="4001").json()["data"]["riskId"]
    r = client.get(f"{BASE}/risk/records/{rid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_r8_unauthenticated_401(client, db_mode):
    _seed(db_mode)
    r = client.get(f"{BASE}/risk/records")  # 无 Authorization
    assert r.status_code == 401 and r.json()["bizCode"] == "UNAUTHORIZED"


def test_r9_no_permission_403001(client, db_mode):
    _seed(db_mode)
    # 就业老师(EMPLOYMENT_TEACHER) 无 studentAffairs.risk.* → 403 NO_PERMISSION
    r = client.get(f"{BASE}/risk/records", headers=_hdr(client, "employment01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"


def test_r10_sec2_student_affairs_admin_masked(client, db_mode):
    """SEC-2：学工处管理员(STUDENT_AFFAIRS_ADMIN) 默认不得查看心理原始明细，即便带原因。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _create(client, admin, ids["sa"], source="MENTAL", ref="3002",
                  detail="心理危机明细").json()["data"]["riskId"]
    sa = _hdr(client, "sa_admin01")
    d = client.get(f"{BASE}/risk/records/{rid}", params={"reason": "学工处例行检查"}, headers=sa).json()["data"]
    assert d["mentalMasked"] is True and "心理危机明细" not in d["detail"]


def test_r11_invalid_source_ref_400_not_500(client, db_mode):
    """sourceRefId 非数字（旧 manual-<ts> 会 int() 抛 500）→ 现校验 400 VALIDATION_ERROR。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/risk/records", headers=admin, json={
        "studentId": str(ids["sa"]), "source": "ACADEMIC_WARNING",
        "sourceRefId": "manual-abc", "riskLevel": "MEDIUM", "title": "x", "detail": "y"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"
    # MANUAL 来源无来源单据：忽略 sourceRefId、不去重、正常建单
    r2 = client.post(f"{BASE}/risk/records", headers=admin, json={
        "studentId": str(ids["sa"]), "source": "MANUAL", "riskLevel": "LOW",
        "title": "人工", "detail": "人工标记"})
    assert r2.status_code == 200 and r2.json()["data"]["source"] == "MANUAL"


def test_r12_cross_tenant_isolation_404(client, db_mode):
    """跨租户隔离：他租户风险记录对本租户不可见（_load tenant 校验 → 404）。"""
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    other = AffairsRiskRecord(tenant_id=TID + 1, student_id=ids["sa"], source="MANUAL",
                              risk_level="HIGH", title="他租户", detail="他租户明细", status="NEW")
    db.add(other); db.commit(); other_id = other.id; db.close()
    admin = _hdr(client, "school_admin01")
    assert client.get(f"{BASE}/risk/records/{other_id}", headers=admin).status_code == 404
    # 列表也不含他租户记录
    items = client.get(f"{BASE}/risk/records", headers=admin).json()["data"]["items"]
    assert all(str(it["riskId"]) != str(other_id) for it in items)


def test_r13_assign_owner_not_exist_400(client, db_mode):
    """责任人校验（历史欠账收口）：不存在的账号 id → 400 VALIDATION_ERROR，不再"分派成功"给虚空账号。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    r = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "999999999"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_r14_assign_owner_non_digit_400_not_500(client, db_mode):
    """非数字 id（如旧前端误传空串/文本）→ 400 VALIDATION_ERROR，不再 int() 抛 500。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    r = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": "abc"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_r15_assign_owner_without_disposal_role_400(client, db_mode):
    """账号存在但不持处置角色（如就业老师）→ 400 VALIDATION_ERROR，不再变成点开即 403 的死信待办。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    r = client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr,
                    json={"ownerId": str(ids["noRole"])})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_r16_transfer_owner_validated(client, db_mode):
    """转办同样受责任人校验约束：合法账号转办成功，非法账号 400。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    rid = _create(client, hdr, ids["sa"]).json()["data"]["riskId"]
    client.post(f"{BASE}/risk/records/{rid}/assign", headers=hdr, json={"ownerId": str(ids["owner"])})
    client.post(f"{BASE}/risk/records/{rid}/process", headers=hdr, json={"content": "首次处置记录"})
    bad = client.post(f"{BASE}/risk/records/{rid}/transfer", headers=hdr,
                      json={"newOwnerId": "999999999", "reason": "转给不存在账号"})
    assert bad.status_code == 400 and bad.json()["bizCode"] == "VALIDATION_ERROR"
    ok = client.post(f"{BASE}/risk/records/{rid}/transfer", headers=hdr,
                     json={"newOwnerId": str(ids["owner"]), "reason": "工作交接"}).json()
    assert ok["data"]["status"] == "ASSIGNED" and ok["data"]["ownerId"] == str(ids["owner"])

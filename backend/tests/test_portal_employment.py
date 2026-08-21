"""学生 PC 门户 · 就业服务（第5期）测试（MySQL 真库 via db_mode）：

我的就业查看 / 去向登记(校验+提交) / 打印回执 / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/employment"
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


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    row = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F", grade="2021",
                         current_stage="EMPLOYMENT", student_status="NORMAL", status="ACTIVE")
    db.add(row)
    db.commit()
    sid = int(row.id)
    db.close()
    return sid


def _seed_teacher(login_name="employment01"):
    """SP-E02/E04：/destination 现在真实开一条单节点审批，受理人按 EMPLOYMENT_TEACHER
    角色候选池解析；没有真实受理人时 submit() fail-closed（ASSIGNEE_NOT_CONFIGURED），
    与 AID/AA_STATUS_CHANGE 等既有域一致，测试必须像它们一样先建真实 User/Role/UserRole。"""
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    db = get_sessionmaker()()
    try:
        user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if user is None:
            user = User(tenant_id=TID, login_name=login_name, real_name="就业老师",
                       password_hash="test-only", user_type="TEACHER", status="ACTIVE")
            db.add(user)
            db.flush()
        role = db.query(Role).filter_by(tenant_id=TID, role_code="EMPLOYMENT_TEACHER").first()
        if role is None:
            role = Role(tenant_id=TID, role_code="EMPLOYMENT_TEACHER", role_name="就业老师",
                       role_type="SYSTEM", status="ACTIVE")
            db.add(role)
            db.flush()
        if not db.query(UserRole).filter_by(tenant_id=TID, user_id=user.id, role_id=role.id).first():
            db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"))
        db.commit()
        uid = int(user.id)
    finally:
        db.close()
    return uid


def test_my_view(client, db_mode):
    _seed("EM-001", "就业一")
    h = _stu_token("就业一", "EM-001")
    assert client.get(f"{PORTAL}/my", headers=h).json()["code"] == 0


def test_destination_register(client, db_mode):
    _seed_teacher()
    _seed("EM-002", "就业二")
    h = _stu_token("就业二", "EM-002")
    # 缺去向类型 → 校验失败
    assert client.post(f"{PORTAL}/destination", headers=h, json={}).json()["code"] != 0
    # SP-E03：destinationType 必须是 canonical code。旧实现接受任意字符串（本用例
    # 原本提交的就是中文 label "签约就业"），管理端根本识别不了这种值。
    ok = client.post(f"{PORTAL}/destination", headers=h,
                     json={"destinationType": "SIGNED", "companyName": "某科技公司",
                           "jobTitle": "后端工程师", "city": "杭州市",
                           "contact": "0571-00000000",
                           "remark": "已签订三方协议"}).json()
    assert ok["code"] == 0


def test_destination_register_rejects_non_canonical_type(client, db_mode):
    """SP-E03：学生 PC 之前硬编码 FURTHER/MILITARY，与 canonical
    FURTHER_STUDY/ENLISTED 漂移；中文 label 也曾能提交。两者现在都必须被拒。"""
    _seed("EM-004", "就业四")
    h = _stu_token("就业四", "EM-004")
    for bad in ("FURTHER", "MILITARY", "签约就业", "NOT_A_CODE"):
        r = client.post(f"{PORTAL}/destination", headers=h,
                        json={"destinationType": bad, "companyName": "X"}).json()
        assert r["code"] != 0, bad
        assert "SIGNED" in (r.get("details") or {}).get("allowed", []), r


def test_destination_register_persists_every_submitted_field(client, db_mode):
    """SP-E01/SP-E02：结构化 `EmpDestinationSubmission` 每个字段落自己的真实列，不再
    靠自由文本工单拼接"尽量不丢"（旧实现读 unitName，前端发的却是 companyName，
    单位被静默丢弃；jobTitle/city/contact 更是完全没有进入提交内容）。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpDestinationSubmission

    _seed_teacher()
    sid = _seed("EM-005", "就业五")
    h = _stu_token("就业五", "EM-005")
    ok = client.post(f"{PORTAL}/destination", headers=h,
                     json={"destinationType": "SIGNED", "companyName": "回读单位",
                           "jobTitle": "回读岗位", "city": "回读城市",
                           "contact": "回读联系方式", "remark": "回读说明"}).json()
    assert ok["code"] == 0, ok

    db = get_sessionmaker()()
    try:
        row = db.query(EmpDestinationSubmission).filter(
            EmpDestinationSubmission.tenant_id == TID,
            EmpDestinationSubmission.student_id == sid,
        ).order_by(EmpDestinationSubmission.id.desc()).first()
    finally:
        db.close()
    assert row is not None
    assert row.destination_type == "SIGNED"
    assert row.company_name == "回读单位"
    assert row.job_title == "回读岗位"
    assert row.city == "回读城市"
    assert row.contact == "回读联系方式"
    assert row.remark == "回读说明"
    assert row.status == "SUBMITTED"


def test_destination_register_accepts_legacy_unit_name_alias(client, db_mode):
    """unitName 作为 deprecated 兼容别名仍可用，但 canonical 名是 companyName。"""
    _seed_teacher()
    _seed("EM-006", "就业六")
    h = _stu_token("就业六", "EM-006")
    ok = client.post(f"{PORTAL}/destination", headers=h,
                     json={"destinationType": "SIGNED", "unitName": "旧字段单位"}).json()
    assert ok["code"] == 0, ok


def test_destination_register_enforces_required_company(client, db_mode):
    """服务端按 requiredFields 校验：签约必须有单位，入伍/自由职业不要求。"""
    _seed_teacher()
    _seed("EM-007", "就业七")
    h = _stu_token("就业七", "EM-007")
    missing = client.post(f"{PORTAL}/destination", headers=h,
                          json={"destinationType": "SIGNED"}).json()
    assert missing["code"] != 0, missing
    ok = client.post(f"{PORTAL}/destination", headers=h,
                     json={"destinationType": "ENLISTED"}).json()
    assert ok["code"] == 0, ok


def test_destination_options_are_canonical(client, db_mode):
    """SP-E03/SP-E10：服务端下发 canonical 去向与状态字典，学生端不再自写枚举。"""
    from app.modules.employment.services import employment_service as canonical

    _seed("EM-008", "就业八")
    h = _stu_token("就业八", "EM-008")
    r = client.get(f"{PORTAL}/destination/options", headers=h).json()
    assert r["code"] == 0, r
    data = r["data"]

    codes = [d["code"] for d in data["destinationTypes"]]
    assert codes == list(canonical.L_DEST.keys()), codes
    # 曾经漂移/缺失的这几个必须都在
    for expected in ("FURTHER_STUDY", "ENLISTED", "STARTUP", "FREELANCE"):
        assert expected in codes, expected
    assert "FURTHER" not in codes and "MILITARY" not in codes

    signed = next(d for d in data["destinationTypes"] if d["code"] == "SIGNED")
    assert signed["label"] == canonical.L_DEST["SIGNED"]
    assert "companyName" in signed["requiredFields"]
    assert {"code": "AGREEMENT", "label": canonical.L_MATTYPE["AGREEMENT"]} in signed["requiredMaterials"]

    # SP-E09：两套状态字典必须分开下发，前端才不可能把它们混成一个
    verify_codes = [x["code"] for x in data["verifyStatuses"]]
    material_codes = [x["code"] for x in data["materialStatuses"]]
    assert verify_codes == list(canonical.L_VERIFY.keys())
    assert material_codes == list(canonical.L_MAT.keys())
    assert "PENDING_VERIFY" in verify_codes
    assert "SUBMITTED" in material_codes and "REVIEWING" in material_codes


def test_my_view_returns_separate_verify_and_material_facts(client, db_mode):
    """SP-E09：材料审核通过 ≠ 去向已核验。DTO 必须同时给出两个独立事实与各自
    label，学生端不得用其中一个推另一个。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent, StudentProfile

    _seed("EM-009", "就业九")
    db = get_sessionmaker()()
    try:
        stu = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == TID, StudentProfile.student_no == "EM-009").first()
        db.add(EmpStudent(tenant_id=TID, student_id=stu.id, student_no="EM-009",
                          name="就业九", destination_type="SIGNED",
                          company_name="核验单位",
                          material_status="APPROVED", verify_status="PENDING_VERIFY",
                          help_level="NORMAL"))
        db.commit()
    finally:
        db.close()

    h = _stu_token("就业九", "EM-009")
    d = client.get(f"{PORTAL}/my", headers=h).json()["data"]
    assert d["hasData"] is True, d
    assert d["materialStatus"] == "APPROVED"
    assert d["verifyStatus"] == "PENDING_VERIFY"
    # SP-E10：label 来自 canonical，不是前端本地字典（旧本地字典根本没有
    # PENDING_VERIFY 这个 key，界面会直接显示英文原始码）。
    assert d["materialStatusLabel"] == "已通过"
    assert d["verifyStatusLabel"] == "待核验"
    assert d["destinationLabel"] == "签约就业"


def test_print(client, db_mode):
    # SP-E08：登记表打印真实生成 PDF，前提是先有 EmpStudent。这里直接建
    # EmpStudent 验证打印本身；/destination 提交到批准后原子写回 EmpStudent 的
    # 完整链路见 test_employment_destination_submission.py。
    sid = _seed("EM-003", "就业三")
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent
    db = get_sessionmaker()()
    db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="EM-003", name="就业三",
                      destination_type="SIGNED", company_name="某科技公司",
                      verify_status="PENDING_VERIFY", record_status="ACTIVE"))
    db.commit()
    db.close()

    h = _stu_token("就业三", "EM-003")
    r = client.post(f"{PORTAL}/destination/print", headers=h, json={"bizId": "E1"}).json()
    assert r["code"] == 0, r
    assert r["data"]["watermark"] == "就业三"
    assert r["data"]["fileId"] and r["data"]["fileId"].isdigit()


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/my", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/destination", headers=admin,
                       json={"destinationType": "SIGNED"}).json()["code"] == 403001
    # 权限先于入参校验：非法枚举也必须是 403，不能降级成 422 并回显 allowed 字典
    assert client.post(f"{PORTAL}/destination", headers=admin,
                       json={"destinationType": "NOT_A_CODE"}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/destination/options", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/destination/print", headers=admin, json={}).json()["code"] == 403001

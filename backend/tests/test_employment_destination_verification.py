"""就业去向核验：PC 与教师小程序同一门槛（V3 施工手册 TP-E02 / TP-E04）。

本轮决断的核心事实：`EmpStudent.verify_status = VERIFIED` 是 canonical 状态，
到达它的证据门槛不能因为老师用 PC 还是小程序而不同。

- 教师 PC 材料审核仍保留既有闭环（材料通过即完成核验），但只在这份材料**真的
  构成正式证据**时才闭环；只有历史 file_name 文本时材料照常 APPROVED，
  核验状态不被隐式推进。
- 教师 PC 新增独立核验命令，与小程序共用同一 domain 命令（状态机 / 证据门槛 /
  乐观锁 / 审计一致），授权各走本端数据范围权威。

全部用真实 MySQL 跑（db_mode），不是 mock。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
BASE = "/api/v1/employment"


def _hdr(client, login_name="employment01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(*, formal: bool, destination="SIGNED", scan_status="CLEAN", file_status="AVAILABLE"):
    """建一名在 employment01 数据范围内的学生 + 一份 SUBMITTED 材料。

    formal=True 时额外建立正式 FileObject + ACTIVE/is_current FileBinding，
    使该材料构成正式证据；formal=False 时只有历史 file_name 文本。
    """
    from app.db.session import get_sessionmaker
    from app.models import (College, EmpMaterial, EmpStudent, Major, SchoolClass,
                            StudentProfile, TeacherStudentScope)
    from app.models.file import FileBinding, FileObject

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name="核验学院", status="ACTIVE")
        db.add(college)
        db.flush()
        major = Major(tenant_id=TID, college_id=college.id, major_name="核验专业", status="ACTIVE")
        db.add(major)
        db.flush()
        klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="核验可见班",
                            grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(klass)
        db.flush()
        db.add(TeacherStudentScope(
            tenant_id=TID, teacher_key="employment01", teacher_name="刘芳",
            role_code="EMPLOYMENT_TEACHER", scope_type="CLASS",
            ref_value="核验可见班", status="ACTIVE"))

        profile = StudentProfile(
            tenant_id=TID, student_no="VER0001", real_name="核验学生",
            college_id=college.id, major_id=major.id, class_id=klass.id,
            grade="2026", current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add(profile)
        db.flush()

        emp = EmpStudent(
            tenant_id=TID, student_id=profile.id, student_no=profile.student_no,
            name=profile.real_name, college_name=college.college_name,
            major_name=major.major_name, class_id=str(klass.id), class_name=klass.class_name,
            destination_type=destination, company_name="核验单位",
            verify_status="PENDING_VERIFY", material_status="SUBMITTED",
            help_level="NORMAL", risk_level="LOW", record_status="ACTIVE")
        db.add(emp)
        db.flush()

        mat = EmpMaterial(tenant_id=TID, emp_student_id=emp.id, material_type="AGREEMENT",
                          file_name="agreement.pdf", submit_time=datetime.utcnow(),
                          status="SUBMITTED")
        db.add(mat)
        db.flush()

        if formal:
            fo = FileObject(tenant_id=TID, file_key="k/agreement.pdf", file_name="agreement.pdf",
                            status=file_status, scan_status=scan_status)
            db.add(fo)
            db.flush()
            db.add(FileBinding(
                tenant_id=TID, file_id=fo.id, biz_type="EMPLOYMENT_MATERIAL",
                biz_id=str(mat.id), module_code="EMPLOYMENT", relation_type="ATTACHMENT",
                subject_type="STUDENT", subject_id=str(profile.id),
                version_no=1, is_current=True, status="ACTIVE"))
        db.commit()
        return {"emp": str(emp.id), "mat": str(mat.id), "version": int(emp.version or 0)}
    finally:
        db.close()


def _emp_state(emp_id):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent
    db = get_sessionmaker()()
    try:
        row = db.get(EmpStudent, int(emp_id))
        return {"verify": row.verify_status, "material": row.material_status,
                "version": int(row.version or 0)}
    finally:
        db.close()


# ── TP-E04：材料审核闭环的证据门槛 ─────────────────────────────

def test_material_approve_with_formal_evidence_still_closes_the_loop(client, db_mode):
    """有正式证据时保持既有闭环：材料 APPROVED 同时完成去向核验。
    真实上传过材料的正常流程不受本轮改动影响。"""
    ids = _seed(formal=True)
    h = _hdr(client)
    r = client.post(f"{BASE}/materials/{ids['mat']}/approve",
                    headers={**h, "Idempotency-Key": "ik-formal-1"}, json={})
    body = r.json()
    assert body["code"] == 0, body
    assert body["data"]["formalEvidence"] is True, body
    assert body["data"]["destinationVerified"] is True, body

    state = _emp_state(ids["emp"])
    assert state["material"] == "APPROVED"
    assert state["verify"] == "VERIFIED", state


def test_material_approve_without_formal_evidence_does_not_verify(client, db_mode):
    """只有历史 file_name 文本时：材料照常通过（材料审核是独立业务行为），
    但 verify_status 不被隐式推进——这是 TP-E04 关心的证据强度问题。"""
    ids = _seed(formal=False)
    h = _hdr(client)
    r = client.post(f"{BASE}/materials/{ids['mat']}/approve",
                    headers={**h, "Idempotency-Key": "ik-legacy-1"}, json={}).json()
    assert r["code"] == 0, r
    assert r["data"]["formalEvidence"] is False, r
    assert r["data"]["destinationVerified"] is False, r

    state = _emp_state(ids["emp"])
    assert state["material"] == "APPROVED", state
    assert state["verify"] == "PENDING_VERIFY", state


def test_material_approve_with_pending_scan_is_not_evidence(client, db_mode):
    """扫描未放行的文件不算正式证据，不能闭环核验。"""
    ids = _seed(formal=True, scan_status="PENDING")
    h = _hdr(client)
    r = client.post(f"{BASE}/materials/{ids['mat']}/approve",
                    headers={**h, "Idempotency-Key": "ik-scan-1"}, json={}).json()
    assert r["code"] == 0, r
    assert r["data"]["destinationVerified"] is False, r
    assert _emp_state(ids["emp"])["verify"] == "PENDING_VERIFY"


# ── TP-E02：教师 PC 独立核验命令 ─────────────────────────────

def test_pc_verification_workspace_reports_evidence_and_blocked_reason(client, db_mode):
    ids = _seed(formal=False)
    h = _hdr(client)
    d = client.get(f"{BASE}/students/{ids['emp']}/verification", headers=h).json()
    assert d["code"] == 0, d
    data = d["data"]
    assert data["verifyStatus"] == "PENDING_VERIFY"
    assert data["formalApprovedCount"] == 0
    assert "VERIFY" not in data["allowedActions"], data
    assert "正式 FileBinding" in data["blockedReason"], data
    # 材料 DTO 必须能区分正式证据与历史文本
    assert data["materials"][0]["formalEvidence"] is False
    assert data["materials"][0]["legacyFileNameOnly"] is True


def test_pc_verify_rejected_without_formal_approved_material(client, db_mode):
    """PC 独立核验走的是与小程序同一道证据门槛：没有正式证据一律 409。"""
    ids = _seed(formal=False)
    h = _hdr(client)
    state = _emp_state(ids["emp"])
    r = client.post(f"{BASE}/students/{ids['emp']}/verification",
                    headers={**h, "Idempotency-Key": "ik-verify-deny"},
                    json={"action": "VERIFY", "expectedVersion": state["version"]})
    assert r.status_code == 409, r.text
    assert _emp_state(ids["emp"])["verify"] == "PENDING_VERIFY"


def test_pc_verify_succeeds_with_formal_approved_material(client, db_mode):
    ids = _seed(formal=True)
    h = _hdr(client)
    # 先让材料进入 APPROVED（这一步本身就会闭环核验），因此换一条路径验证：
    # 直接把材料置 APPROVED 但核验保持 PENDING，再走独立核验命令。
    from app.db.session import get_sessionmaker
    from app.models import EmpMaterial
    db = get_sessionmaker()()
    try:
        m = db.get(EmpMaterial, int(ids["mat"]))
        m.status = "APPROVED"
        db.commit()
    finally:
        db.close()

    state = _emp_state(ids["emp"])
    r = client.post(f"{BASE}/students/{ids['emp']}/verification",
                    headers={**h, "Idempotency-Key": "ik-verify-ok"},
                    json={"action": "VERIFY", "expectedVersion": state["version"]}).json()
    assert r["code"] == 0, r
    assert r["data"]["status"] == "VERIFIED", r
    assert _emp_state(ids["emp"])["verify"] == "VERIFIED"


def test_pc_verify_requires_matching_expected_version(client, db_mode):
    """核验是高风险状态推进，必须带乐观锁；版本不匹配一律 409。"""
    ids = _seed(formal=True)
    h = _hdr(client)
    from app.db.session import get_sessionmaker
    from app.models import EmpMaterial
    db = get_sessionmaker()()
    try:
        m = db.get(EmpMaterial, int(ids["mat"]))
        m.status = "APPROVED"
        db.commit()
    finally:
        db.close()

    state = _emp_state(ids["emp"])
    r = client.post(f"{BASE}/students/{ids['emp']}/verification",
                    headers={**h, "Idempotency-Key": "ik-verify-stale"},
                    json={"action": "VERIFY", "expectedVersion": state["version"] + 99})
    assert r.status_code == 409, r.text
    assert _emp_state(ids["emp"])["verify"] == "PENDING_VERIFY"


def test_pc_return_requires_actionable_comment(client, db_mode):
    ids = _seed(formal=False)
    h = _hdr(client)
    state = _emp_state(ids["emp"])
    short = client.post(f"{BASE}/students/{ids['emp']}/verification",
                        headers={**h, "Idempotency-Key": "ik-ret-short"},
                        json={"action": "RETURN", "comment": "不行", "expectedVersion": state["version"]})
    assert short.json()["code"] != 0, short.text

    ok = client.post(f"{BASE}/students/{ids['emp']}/verification",
                     headers={**h, "Idempotency-Key": "ik-ret-ok"},
                     json={"action": "RETURN", "comment": "请补交盖章版就业协议原件",
                           "expectedVersion": state["version"]}).json()
    assert ok["code"] == 0, ok
    assert _emp_state(ids["emp"])["verify"] == "RETURNED"


def test_pc_verify_rejects_unemployed_destination(client, db_mode):
    ids = _seed(formal=True, destination="UNEMPLOYED")
    h = _hdr(client)
    state = _emp_state(ids["emp"])
    r = client.post(f"{BASE}/students/{ids['emp']}/verification",
                    headers={**h, "Idempotency-Key": "ik-verify-unemp"},
                    json={"action": "VERIFY", "expectedVersion": state["version"]})
    assert r.status_code == 409, r.text

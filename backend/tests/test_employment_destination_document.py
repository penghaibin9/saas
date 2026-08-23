"""SP-E08：就业去向登记表真实文件生成（不是打印审计留痕）。

`student_portal/services/employment_service.py::destination_print()` 此前只写
PORTAL_PRINT 审计，没有生成任何真实文件。现在必须先有 EmpStudent 才能打印，
打印会真实生成 PDF 落 File Center（fileId + sha256），事实版本不变时复用同一份
文件，事实版本前进后重新生成。全部用真实 MySQL 跑（db_mode）。
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


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        row = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F",
                             grade="2021", current_stage="EMPLOYMENT",
                             student_status="NORMAL", status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)
    finally:
        db.close()


def test_print_without_destination_registered_is_rejected(client, db_mode):
    """没有就业档案时打印必须明确拒绝，不能生成一份空白/占位文件冒充登记表。"""
    _seed_student("EMD-001", "登记表一")
    h = _stu_token("登记表一", "EMD-001")
    payload = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()
    assert payload["code"] != 0
    assert payload["bizCode"] == "DATA_NOT_FOUND"


def test_print_generates_real_file_with_id_and_hash(client, db_mode):
    """SP-E08 核心：打印成功必须拿到真实 fileId + sha256，不再只是一条审计留痕。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("EMD-002", "登记表二")
    db = get_sessionmaker()()
    try:
        db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="EMD-002",
                          name="登记表二", destination_type="SIGNED",
                          company_name="某科技公司", job_title="后端工程师",
                          verify_status="PENDING_VERIFY", record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    h = _stu_token("登记表二", "EMD-002")
    payload = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert data["fileId"] and data["fileId"].isdigit()
    assert len(data["sha256"] or "") == 64, "必须是真实内容 sha256，不是占位字符串"
    assert data["sizeBytes"] > 0
    assert data["watermark"], "原有 PORTAL_PRINT 审计留痕（水印）必须保留"


def test_print_reuses_file_when_facts_unchanged(client, db_mode):
    """同一份事实版本不重复生成文件——第二次打印返回同一个 fileId。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("EMD-003", "登记表三")
    db = get_sessionmaker()()
    try:
        db.add(EmpStudent(tenant_id=TID, student_id=sid, student_no="EMD-003",
                          name="登记表三", destination_type="SIGNED",
                          company_name="某科技公司", verify_status="PENDING_VERIFY",
                          record_status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    h = _stu_token("登记表三", "EMD-003")
    first = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()["data"]
    second = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()["data"]
    assert first["fileId"] == second["fileId"]
    assert first["sha256"] == second["sha256"]


def test_print_regenerates_after_facts_change(client, db_mode):
    """事实版本前进（如核验通过）后必须重新生成，不能继续发旧文件。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    sid = _seed_student("EMD-004", "登记表四")
    db = get_sessionmaker()()
    try:
        emp = EmpStudent(tenant_id=TID, student_id=sid, student_no="EMD-004",
                         name="登记表四", destination_type="SIGNED",
                         company_name="某科技公司", verify_status="PENDING_VERIFY",
                         record_status="ACTIVE")
        db.add(emp)
        db.commit()
        emp_id = emp.id
    finally:
        db.close()

    h = _stu_token("登记表四", "EMD-004")
    first = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()["data"]

    db = get_sessionmaker()()
    try:
        emp = db.get(EmpStudent, emp_id)
        emp.verify_status = "VERIFIED"
        emp.version = int(emp.version or 0) + 1
        db.commit()
    finally:
        db.close()

    second = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()["data"]
    assert second["fileId"] != first["fileId"], "核验状态变化后必须重新生成，不能复用旧文件"
    assert second["sourceVersion"] > first["sourceVersion"]


def test_non_student_rejected(client, db_mode):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    h = {"Authorization": f"Bearer {data['accessToken']}"}
    payload = client.post(f"{PORTAL}/destination/print", headers=h, json={}).json()
    assert payload["code"] == 403001

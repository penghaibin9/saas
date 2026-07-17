"""就业服务域 RBAC 权限门禁回归。

此前 employment.py 全部端点仅 Depends(get_current_user)（只拦学生 token 不拦角色），
任何已登录用户都能新增/停用企业岗位、变更学生就业记录。本文件验证补齐 require_permission
后：EMPLOYMENT_TEACHER(employment.*)/SCHOOL_ADMIN(*) 正常放行；学生 token 及无就业授权
的教师(如 counselor01)对就业域写接口一律 403。
"""
from __future__ import annotations

BASE = "/api/v1/employment"
MAIN_TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(student_no="EZ001"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": "就业测试生", "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, EmpStudent
    db = get_sessionmaker()()
    try:
        s = EmpStudent(tenant_id=MAIN_TID, name="就业生", student_no="EZ100",
                       destination_type="NONE", verify_status="PENDING", class_name="软件2101")
        db.add(s); db.flush()
        c = EmpCompany(tenant_id=MAIN_TID, name="门禁测试企业", credit_code="CCZ100", status="ACTIVE")
        db.add(c); db.flush()
        db.commit()
        return {"student": s.id, "company": c.id}
    finally:
        db.close()


def test_employment_teacher_allowed(client, db_mode):
    """就业老师(employment.* 通配)：读写就业域正常放行。"""
    _seed(db_mode)
    hdr = _hdr(client, "employment01")
    assert client.get(f"{BASE}/students", headers=hdr).status_code == 200
    r = client.post(f"{BASE}/companies", headers=hdr,
                    json={"name": "就业老师新增企业", "creditCode": "CCNEW01"})
    assert r.status_code == 200 and r.json()["code"] == 0


def test_school_admin_allowed(client, db_mode):
    """学校管理员(* 全权)：不受影响正常放行。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    assert client.get(f"{BASE}/companies", headers=hdr).status_code == 200


def test_student_token_denied_on_writes(client, db_mode):
    """学生 token 对就业域写接口一律 403（此前只有学生被 require_staff 拦，现细粒度权限同样拦）。"""
    ids = _seed(db_mode)
    hdr = _stu_token()
    assert client.post(f"{BASE}/companies", headers=hdr,
                       json={"name": "越权企业", "creditCode": "CCX001"}).status_code == 403
    assert client.post(f"{BASE}/jobs", headers=hdr,
                       json={"companyId": str(ids["company"]), "title": "越权岗位"}).status_code == 403
    assert client.post(f"{BASE}/students", headers=hdr,
                       json={"name": "越权学生", "studentNo": "EZ999"}).status_code == 403


def test_counselor_denied_on_employment(client, db_mode):
    """无就业授权的教师(辅导员，无 employment.* 权限)对就业域写接口 403——这是本次补门禁前
    完全没有拦截的越权场景(此前辅导员 token 也能新增停用企业岗位)。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    assert client.post(f"{BASE}/companies", headers=hdr,
                       json={"name": "辅导员越权企业", "creditCode": "CCC001"}).status_code == 403
    assert client.post(f"{BASE}/companies/{ids['company']}/disable", headers=hdr,
                       json={"reason": "辅导员越权停用测试"}).status_code == 403

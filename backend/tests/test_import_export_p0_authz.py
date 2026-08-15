"""P0 · 导入导出权限收紧：精确权限、域白名单、任务归属、跨租户。"""
from __future__ import annotations

TID = 1000000000000000001
OTHER_TID = 1000000000000000002


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _token(role: str, *, tenant_id: int = TID, user_id: str = "u-x", user_type: str = "TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "realName": role, "userType": user_type,
        "tid": "demo", "tenantId": str(tenant_id), "activeContextId": f"ctx_{role}",
        "currentRoleCode": role, "clientType": "PC",
    })}


def test_teacher_cannot_export_students(client, db_mode):
    """学生批量导入已收敛到系统管理入口（见 test_student_import_entries.py），
    本用例继续锁导出侧越权。"""
    hdr = _hdr(client, "academic01")
    e = client.post("/api/v1/export/students", headers=hdr,
                    json={"purpose": "越权导出学生主档测试"})
    assert e.status_code == 403


def test_school_admin_export_ok(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    t = client.post("/api/v1/export/students", headers=hdr,
                    json={"purpose": "合法导出学生主档测试"}).json()
    assert t["code"] == 0 and t["data"]["taskId"].isdigit()
    dl = client.get(f"/api/v1/export/tasks/{t['data']['taskId']}/download", headers=hdr)
    assert dl.status_code == 200 and dl.content[:2] == b"PK"


def test_guess_task_id_denied_for_other_staff(client, db_mode):
    admin = _hdr(client, "school_admin01")
    t = client.post("/api/v1/export/students", headers=admin,
                    json={"purpose": "归属下载测试用途"}).json()["data"]["taskId"]
    teacher = _hdr(client, "academic01")
    r = client.get(f"/api/v1/export/tasks/{t}/download", headers=teacher)
    assert r.status_code == 404
    # 猜测不存在的 id
    assert client.get("/api/v1/export/tasks/999999999/download", headers=admin).status_code == 404


def test_illegal_domain_rejected(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.post("/api/v1/import/domain/not-a-real-domain/validate", headers=hdr,
                    json={"rows": []})
    assert r.status_code == 400
    r2 = client.post("/api/v1/export/domain/not-a-real-domain", headers=hdr,
                     json={"purpose": "非法域导出测试"})
    assert r2.status_code == 400


def test_cross_tenant_export_download_denied(client, db_mode):
    admin = _hdr(client, "school_admin01")
    t = client.post("/api/v1/export/students", headers=admin,
                    json={"purpose": "跨租户下载测试用途"}).json()["data"]["taskId"]
    other = _token("SCHOOL_ADMIN", tenant_id=OTHER_TID, user_id="u_other_admin",
                   user_type="ADMIN")
    r = client.get(f"/api/v1/export/tasks/{t}/download", headers=other)
    assert r.status_code == 404

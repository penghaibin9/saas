"""P3 · 岗位实习端点细粒度权限负向测试（对齐 07 整改方案 §11.2）。

要点：前端菜单投影只是展示，后端 require_permission 才是安全边界。
view 可读、manage/export/log 仅管理员/学院负责人，越权一律 403，权限码与 ROLE_PERMISSIONS 一致。
"""
from __future__ import annotations

INT = "/api/v1/internship/intern-students"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _tok(role, user_type="TEACHER", client_type="PC"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{role}", "realName": role, "userType": user_type,
        "tid": "x", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": client_type})}


def test_mentor_can_view_students(client, db_mode):
    # 指导教师有 internship.student.view → 列表可读（数据范围仍由 service 收敛）
    assert client.get(INT, headers=_tok("INTERN_MENTOR")).status_code == 200


def test_mentor_cannot_manage_export_log(client, db_mode):
    m = _tok("INTERN_MENTOR")
    assert client.get(f"{INT}/advisors", headers=m).status_code == 403          # student.manage
    assert client.post(f"{INT}/export", headers=m).status_code == 403           # student.export
    assert client.get(f"{INT}/assignment-logs", headers=m).status_code == 403   # match.log.view


def test_counselor_view_only(client, db_mode):
    c = _tok("COUNSELOR")
    assert client.get(INT, headers=c).status_code == 200                        # student.view
    assert client.post(f"{INT}/export", headers=c).status_code == 403           # 无导出权


def test_student_forbidden_on_pc(client, db_mode):
    # 学生令牌进 PC 管理端：require_staff + 空权限集双重拦截
    assert client.get(INT, headers=_tok("STUDENT", "STUDENT", "MP")).status_code == 403


def test_unregistered_teacher_role_denied(client, db_mode):
    # 未登记角色（真实教职工但无实习授权）→ 默认拒绝
    assert client.get(INT, headers=_tok("SOME_CUSTOM_ROLE")).status_code == 403


def test_admin_full_access(client, db_mode):
    a = _admin(client)
    assert client.get(f"{INT}/advisors", headers=a).status_code == 200
    assert client.post(f"{INT}/export", headers=a).status_code == 200
    assert client.get(f"{INT}/assignment-logs", headers=a).status_code == 200

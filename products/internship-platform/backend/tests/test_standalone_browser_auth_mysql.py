from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.main import app
from app.models import Role, Tenant, User, UserRole


TENANT_ID = 88001
STAFF_ID = 88011
STUDENT_ID = 88012
STAFF_ROLE_ID = 88021
STUDENT_ROLE_ID = 88022


def _seed():
    db = get_sessionmaker()()
    try:
        db.execute(delete(UserRole).where(UserRole.tenant_id == TENANT_ID))
        db.execute(delete(Role).where(Role.tenant_id == TENANT_ID))
        db.execute(delete(User).where(User.tenant_id == TENANT_ID))
        db.execute(delete(Tenant).where(Tenant.id == TENANT_ID))
        db.commit()
        tenant = Tenant(
            id=TENANT_ID,
            tenant_code="AUTH-GATE",
            school_name="浏览器认证验收学校",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        )
        staff_role = Role(
            id=STAFF_ROLE_ID,
            tenant_id=TENANT_ID,
            role_code="SCHOOL_ADMIN",
            role_name="学校管理员",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        student_role = Role(
            id=STUDENT_ROLE_ID,
            tenant_id=TENANT_ID,
            role_code="STUDENT",
            role_name="学生",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        staff = User(
            id=STAFF_ID,
            tenant_id=TENANT_ID,
            login_name="auth.staff",
            real_name="认证管理员",
            password_hash=hash_password("Staff-Evidence-2026!"),
            user_type="SCHOOL_ADMIN",
            status="ACTIVE",
            must_change_password=False,
            credential_version=0,
        )
        student = User(
            id=STUDENT_ID,
            tenant_id=TENANT_ID,
            login_name="202688012",
            real_name="认证学生",
            password_hash=hash_password("Student-Evidence-2026!"),
            user_type="STUDENT",
            status="ACTIVE",
            must_change_password=False,
            credential_version=0,
        )
        db.add_all([
            tenant,
            staff_role,
            student_role,
            staff,
            student,
            UserRole(
                tenant_id=TENANT_ID,
                user_id=STAFF_ID,
                role_id=STAFF_ROLE_ID,
                status="ACTIVE",
            ),
            UserRole(
                tenant_id=TENANT_ID,
                user_id=STUDENT_ID,
                role_id=STUDENT_ROLE_ID,
                status="ACTIVE",
            ),
        ])
        db.commit()
    finally:
        db.close()


def _login(client: TestClient, *, login_name: str, password: str, client_type: str, session_id: str):
    response = client.post(
        "/api/v1/auth/browser-login",
        json={
            "tenantCode": "AUTH-GATE",
            "loginName": login_name,
            "password": password,
            "clientType": client_type,
        },
        headers={"X-Browser-Session-Id": session_id},
    )
    return response


def test_staff_browser_login_refresh_me_logout_real_mysql():
    _seed()
    with TestClient(app) as client:
        session_id = "staff-tab-auth-evidence"
        login = _login(
            client,
            login_name="auth.staff",
            password="Staff-Evidence-2026!",
            client_type="PC",
            session_id=session_id,
        )
        assert login.status_code == 200, login.text
        payload = login.json()
        assert payload["code"] == 0
        data = payload["data"]
        assert data["user"]["userId"] == f"db-{STAFF_ID}"
        assert data["currentRole"]["roleCode"] == "SCHOOL_ADMIN"
        assert data["tenantId"] == str(TENANT_ID)
        assert data["accessToken"]
        assert "refreshToken" not in data
        assert "httponly" in login.headers["set-cookie"].lower()

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data['accessToken']}"},
        )
        assert me.status_code == 200, me.text
        me_data = me.json()["data"]
        assert me_data["user"]["realName"] == "认证管理员"
        assert me_data["currentRole"]["roleCode"] == "SCHOOL_ADMIN"
        assert me_data["tenantId"] == str(TENANT_ID)

        batches = client.get(
            "/api/v1/internship/batches?page=1&pageSize=20",
            headers={"Authorization": f"Bearer {data['accessToken']}"},
        )
        assert batches.status_code == 200, batches.text
        assert batches.json()["code"] == 0
        assert batches.json()["data"]["total"] == 0

        refreshed = client.post(
            "/api/v1/auth/browser-refresh",
            headers={
                "X-Browser-Session": "staff",
                "X-Browser-Session-Id": session_id,
            },
        )
        assert refreshed.status_code == 200, refreshed.text
        refresh_data = refreshed.json()["data"]
        assert refresh_data["accessToken"]
        assert "refreshToken" not in refresh_data

        logout = client.post(
            "/api/v1/auth/browser-logout",
            headers={
                "X-Browser-Session": "staff",
                "X-Browser-Session-Id": session_id,
                "Authorization": f"Bearer {refresh_data['accessToken']}",
            },
        )
        assert logout.status_code == 200, logout.text
        assert logout.json()["data"]["invalidated"] is True

        denied = client.post(
            "/api/v1/auth/browser-refresh",
            headers={
                "X-Browser-Session": "staff",
                "X-Browser-Session-Id": session_id,
            },
        )
        assert denied.status_code == 401


def test_student_browser_channel_and_cross_surface_fail_closed_real_mysql():
    _seed()
    with TestClient(app) as student_client:
        session_id = "student-tab-auth-evidence"
        login = _login(
            student_client,
            login_name="202688012",
            password="Student-Evidence-2026!",
            client_type="STUDENT_PC",
            session_id=session_id,
        )
        assert login.status_code == 200, login.text
        data = login.json()["data"]
        assert data["user"]["userType"] == "STUDENT"
        assert data["currentRole"]["roleCode"] == "STUDENT"
        assert data["user"]["studentNo"] == "202688012"

        me = student_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data['accessToken']}"},
        )
        assert me.status_code == 200, me.text
        assert me.json()["data"]["currentRole"]["roleCode"] == "STUDENT"

        denied_staff_route = student_client.get(
            "/api/v1/internship/batches?page=1&pageSize=20",
            headers={"Authorization": f"Bearer {data['accessToken']}"},
        )
        assert denied_staff_route.status_code == 403, denied_staff_route.text

    with TestClient(app) as wrong_surface:
        denied_student = _login(
            wrong_surface,
            login_name="auth.staff",
            password="Staff-Evidence-2026!",
            client_type="STUDENT_PC",
            session_id="wrong-student-tab",
        )
        assert denied_student.status_code == 403

        denied_staff = _login(
            wrong_surface,
            login_name="202688012",
            password="Student-Evidence-2026!",
            client_type="PC",
            session_id="wrong-staff-tab",
        )
        assert denied_staff.status_code == 403

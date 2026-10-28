from datetime import datetime, timedelta
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select


def test_funding_export_and_old_download_ticket_recheck_the_current_duty_scope(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RoleAssignmentScope, RolePermission, User, UserRole
    from app.services import affairs_funding_export_service as exports
    from app.services.system_role_shadow_service import published_system_role_permissions
    from affairs_contract_test_support import ensure_role_user
    from test_affairs_security import TID, _base
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_funding_disbursement import _seed_granted

    ids = _base(db_mode)
    uid = ensure_role_user("FUNDING_TEACHER", login_name="export_duty_owner", real_name="资助导出验证老师")
    with get_sessionmaker()() as db:
        account = db.get(User, uid)
        account.password_hash = hash_password(TEST_LOGIN_PASSWORD)
        account.must_change_password = False
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "FUNDING_TEACHER"))
        codes = set(published_system_role_permissions(db, role.role_code)) | {
            "studentAffairs.export", "studentAffairs.funding.sensitiveView"}
        role.role_type = "CUSTOM"; role.version += 1
        for permission in db.scalars(select(Permission).where(Permission.permission_code.in_(codes))).all():
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        member = db.scalar(select(UserRole).where(UserRole.user_id == uid, UserRole.role_id == role.id))
        scope = RoleAssignmentScope(tenant_id=TID, user_id=uid, user_role_id=member.id,
            role_code="FUNDING_TEACHER", scope_type="SCHOOL", scope_id=0, status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1))
        db.add(scope); db.flush()
        scope_id, member_id = scope.id, member.id
        db.commit()
    headers = _real_hdr(client, "export_duty_owner")
    base = "/api/v1/student-affairs/funding"
    for student_id in (ids["A"], ids["C"]):
        batch_id = _seed_granted(student_id, n=1)
        generated = client.post(f"{base}/batches/{batch_id}/disbursements/generate", headers=headers)
        assert generated.status_code == 200, generated.text
        assert generated.json()["data"]["generated"] == 1
    created = client.post(f"{base}/disbursements/export", headers=headers, json={"purpose": "核验授权范围内资助台账"})
    assert created.status_code == 200, created.text
    job_id = created.json()["data"]["jobId"]
    from app.core.context import get_tenant, set_tenant
    previous_tenant = get_tenant()
    set_tenant(TID)
    try:
        exports.run_pending(limit=1)
    finally:
        set_tenant(previous_tenant)

    def issue_ticket():
        result = client.get(f"{base}/disbursements/export-jobs/{job_id}", headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()["data"]["status"] == "SUCCEEDED", result.json()["data"].get("errorMessage")
        ticket = client.post(f"{base}/disbursements/export-jobs/{job_id}/download-ticket", headers=headers,
            json={"expectedVersion": result.json()["data"]["version"]})
        assert ticket.status_code == 200, ticket.json().get("message")
        return ticket.json()["data"]["ticket"]

    ticket = issue_ticket()
    downloaded = client.get(f"{base}/disbursements/export-jobs/{job_id}/download", headers=headers,
                            params={"ticket": ticket})
    assert downloaded.status_code == 200
    workbook = load_workbook(BytesIO(downloaded.content), read_only=True)
    assert "C001" in str(list(workbook.active.values))
    workbook.close()
    old_ticket = issue_ticket()
    with get_sessionmaker()() as db:
        old = db.get(RoleAssignmentScope, scope_id)
        old.status = "REVOKED"; old.version += 1
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=uid, user_role_id=member_id,
            role_code="FUNDING_TEACHER", scope_type="COLLEGE", scope_id=ids["col1"], status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        db.commit()
    denied = client.get(f"{base}/disbursements/export-jobs/{job_id}/download", headers=headers,
                        params={"ticket": old_ticket})
    assert denied.status_code == 403, denied.json().get("message")

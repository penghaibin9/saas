"""培养方案的详情动作与两级审核命令共用实时责任岗位。"""
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.modules.academic_affairs.services import academic_affairs_program_service as service


@pytest.mark.parametrize("node,scope", [("COLLEGE_REVIEW", "COLLEGE"), ("ACADEMIC_REVIEW", "TENANT_ALL")])
@pytest.mark.parametrize("condition", ["valid", "expired", "permission_revoked", "other_assignee", "account_disabled"])
def test_program_detail_and_command_share_live_review_responsibility(node, scope, condition, monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility

    db = MagicMock()
    program = Row(id=91, major_id=101, status=node, program_name="两级审核方案", grade_year="2041", total_credits=100, version=7)
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = program
    db.scalars.return_value.all.return_value = [101]
    ctx = Row(scope_type=scope, college_ids={12}, allowed_class_ids=lambda db: set(),
        permission_codes=set() if condition == "permission_revoked" else {"academicAffairs.program.review"})
    monkeypatch.setattr(service, "session", lambda: nullcontext(db))
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "build_affairs_context", lambda *args: ctx)
    monkeypatch.setattr(service.governance, "_ensure_program_scope", lambda *args: None)
    owner = {"resolved": condition != "expired", "assigneeUserIds": ["31" if condition == "other_assignee" else "21"],
        "reason": "当前审核任职已过期"}
    resolver = MagicMock(return_value=owner)
    monkeypatch.setattr(responsibility, "resolve_program", resolver)
    current = MagicMock(return_value=21)
    if condition == "account_disabled":
        current.side_effect = no_permission("账号已停用")
    monkeypatch.setattr(identity, "_current_user_id", current)
    audit = MagicMock()
    monkeypatch.setattr(service._core, "_audit", audit)
    user = {"userId": "db-21"}

    detail = service._review_node(db, program, user)
    assert detail["canReview"] is (condition == "valid")
    if condition == "valid":
        result = service.review_program(91, user, "APPROVE")
        assert result["status"] == ("ACADEMIC_REVIEW" if node == "COLLEGE_REVIEW" else "PUBLISHED")
        assert audit.call_count == 1 and db.commit.call_count == 1
        current.assert_called_with(db, user)
    else:
        with pytest.raises(AppException) as denied:
            service.review_program(91, user, "APPROVE")
        assert denied.value.code == "NO_DATA_SCOPE"
        assert program.status == node
        audit.assert_not_called()
        db.commit.assert_not_called()
    # 写入口不继承详情请求的身份缓存，每次均实时解析。
    if condition != "permission_revoked":
        assert resolver.call_count == 2
        resolver.assert_called_with(db, program)


def test_mysql_program_review_expiry_and_revocation_block_both_nodes_then_allow_handoff(db_mode):
    """只在主控串行的独立 MySQL 测试库运行，权限和责任解析均不替换。"""
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Permission, RolePermission, StaffAssignment
    from tests.test_aa_program_review_authority_r3 import TID, COLLEGE_USER, SCHOOL_USER, _seed, _program, _audit_count

    previous = get_tenant()
    set_tenant(TID)
    try:
        program_id = _seed()["own"]
        for user, node, next_node in ((COLLEGE_USER, "COLLEGE_REVIEW", "ACADEMIC_REVIEW"),
                                      (SCHOOL_USER, "ACADEMIC_REVIEW", "PUBLISHED")):
            assert service.get_program(program_id, user)["reviewNode"]["canReview"] is True
            with get_sessionmaker()() as db:
                appointment = db.scalar(select(StaffAssignment).where(
                    StaffAssignment.tenant_id == TID, StaffAssignment.user_id == int(user["userId"])))
                appointment_id = appointment.id
                appointment.expires_at = datetime.utcnow() - timedelta(days=1)
                db.commit()
            expired = service.get_program(program_id, user)
            assert not expired["responsibility"]["resolved"] and not expired["reviewNode"]["canReview"]
            with pytest.raises(AppException) as denied:
                service.review_program(program_id, user, "APPROVE")
            assert denied.value.code == "NO_DATA_SCOPE" and _program(program_id)[0] == node

            with get_sessionmaker()() as db:
                db.get(StaffAssignment, appointment_id).expires_at = None
                grant = db.scalar(select(RolePermission).join(Permission, Permission.id == RolePermission.permission_id).where(
                    RolePermission.tenant_id == TID, RolePermission.role_id == int(user["activeContextId"].split(":")[1]),
                    Permission.permission_code == "academicAffairs.program.review"))
                grant_id = grant.id
                grant.status = "DISABLED"
                db.commit()
            revoked = service.get_program(program_id, user)
            assert not revoked["responsibility"]["resolved"] and not revoked["reviewNode"]["canReview"]
            with pytest.raises(AppException) as denied:
                service.review_program(program_id, user, "APPROVE")
            assert denied.value.code == "NO_DATA_SCOPE" and _program(program_id)[0] == node

            with get_sessionmaker()() as db:
                db.get(RolePermission, grant_id).status = "ACTIVE"
                db.commit()
            assert service.get_program(program_id, user)["reviewNode"]["canReview"] is True
            assert service.review_program(program_id, user, "APPROVE")["status"] == next_node
        assert _program(program_id) == ("PUBLISHED", 7)
        assert _audit_count(program_id, "APPROVE") == 2
    finally:
        set_tenant(previous)


def test_published_unbound_program_projects_two_live_school_publishers(db_mode):
    """Published content still needs a school owner to bind its applicable grade."""
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaProgramBinding, Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole
    from tests.support_academic_review_identity import _ensure_permission
    from tests.test_aa_program_review_authority_r3 import TID, SCHOOL_USER, _seed

    previous = get_tenant()
    set_tenant(TID)
    try:
        program_id = _seed(status="PUBLISHED")["own"]
        with get_sessionmaker()() as db:
            role_id = int(SCHOOL_USER["activeContextId"].split(":")[1])
            role = db.get(Role, role_id)
            permission = _ensure_permission(db, "academicAffairs.program.publish")
            grant = RolePermission(tenant_id=TID, role_id=role_id,
                                   permission_id=permission.id, status="ACTIVE")
            db.add(grant)
            second = User(tenant_id=TID, login_name="aa-r3-program-school-second",
                          real_name="第二位校教务发布人", user_type="TEACHER",
                          password_hash="unused-in-service-test", status="ACTIVE")
            db.add(second)
            db.flush()
            link = UserRole(tenant_id=TID, user_id=second.id, role_id=role.id, status="ACTIVE")
            db.add(link)
            db.flush()
            db.add(RoleAssignmentScope(
                tenant_id=TID, user_role_id=link.id, user_id=second.id,
                role_code=role.role_code, scope_type="SCHOOL", scope_id=0,
                status="ACTIVE", effective_at=datetime(2020, 1, 1)))
            db.add(StaffAssignment(
                tenant_id=TID, user_id=second.id, org_type="SCHOOL", org_node_id=TID,
                assignment_type="ACADEMIC_REVIEWER", status="ACTIVE",
                effective_at=datetime(2020, 1, 1)))
            second_id = str(second.id)
            db.flush()
            grant_id = grant.id
            db.commit()

        detail = service.get_program(program_id, SCHOOL_USER)
        assert detail["status"] == "PUBLISHED"
        assert detail["nextStep"] == {"code": "ENABLED", "label": "由校教务绑定适用年级后启用"}
        assert detail["responsibility"]["resolved"] is True
        assert set(detail["responsibility"]["assigneeUserIds"]) == {
            SCHOOL_USER["userId"], second_id}
        with get_sessionmaker()() as db:
            assert db.scalar(select(AaProgramBinding.id).where(
                AaProgramBinding.tenant_id == TID,
                AaProgramBinding.program_id == program_id,
                AaProgramBinding.status == "ACTIVE")) is None
            db.get(RolePermission, grant_id).status = "DISABLED"
            db.commit()

        unresolved = service.get_program(program_id, SCHOOL_USER)
        assert unresolved["responsibility"]["resolved"] is False
        assert unresolved["responsibility"]["assigneeUserIds"] == []
        assert unresolved["nextStep"]["code"] == "ENABLED"
    finally:
        set_tenant(previous)

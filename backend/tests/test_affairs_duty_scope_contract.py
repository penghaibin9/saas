from datetime import datetime, timedelta

import pytest

from test_affairs_security import TID, _base


def test_amount_adjustment_does_not_borrow_another_role_or_cached_permissions(monkeypatch):
    from app.core.exceptions import AppException
    from app.services.affairs_funding_authority_service import _require_amount_role
    with pytest.raises(AppException):
        _require_amount_role({"currentRoleCode": "COUNSELOR", "roleCodes": ["COUNSELOR", "FUNDING_TEACHER"],
            "roles": [{"roleCode": "FUNDING_TEACHER"}],
            "permissionCodes": ["studentAffairs.funding.approve", "studentAffairs.funding.publicity.manage"]})
    with pytest.raises(AppException):
        _require_amount_role({"currentRoleCode": "FUNDING_TEACHER", "roleCodes": ["COUNSELOR", "FUNDING_TEACHER"]})
    from app.core import permissions
    monkeypatch.setattr(permissions, "get_base_permission_patterns", lambda user:
                        ["studentAffairs.funding.approve", "studentAffairs.funding.sensitiveView"])
    _require_amount_role({"currentRoleCode": "FUNDING_TEACHER"})


def test_combined_duties_keep_separate_college_class_and_psychology_scopes(db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.core.affairs_security import build_affairs_context, require_school_scope
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, Role, RoleAssignmentScope, SchoolClass, StudentProfile, User, UserRole
    from app.services.affairs_mental_service import psy_scope_ids
    from app.services.affairs_assignee_service import resolve_assignee_ids
    ids = _base(db_mode)
    previous = get_tenant(); set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            assert psy_scope_ids(db, {"currentRoleCode": "SCHOOL_ADMIN", "loginName": "school_admin01"}) == set()
            account = User(tenant_id=TID, login_name="multi_duty_owner", real_name="兼岗测试人员",
                           user_type="TEACHER", password_hash="unused-test-hash", status="ACTIVE")
            db.add(account); db.flush()
            db.get(SchoolClass, ids["cA"]).counselor_id = account.id
            roles, links = {}, {}
            for code in ("COUNSELOR", "FUNDING_TEACHER", "PSYCHOLOGY_TEACHER"):
                role = Role(tenant_id=TID, role_code=code, role_name=code, role_type="SYSTEM", status="ACTIVE")
                db.add(role); db.flush(); roles[code] = role
                link = UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE")
                db.add(link); db.flush(); links[code] = link
            def user(code):
                return {"userId": str(account.id), "tenantId": str(TID), "loginName": account.login_name,
                        "currentRoleCode": code, "userType": "TEACHER", "roleCodes": list(roles)}
            def grant(code, scope_type, scope_id):
                row = RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=links[code].id,
                    role_code=code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                    effective_at=datetime.utcnow() - timedelta(days=1))
                db.add(row); db.flush(); return row
            assert build_affairs_context(user("FUNDING_TEACHER"), db).scope_type == "NONE"
            grant("COUNSELOR", "CLASS", ids["cA"])
            funding = grant("FUNDING_TEACHER", "COLLEGE", ids["col2"])
            grant("FUNDING_TEACHER", "CLASS", ids["cA"])
            grant("PSYCHOLOGY_TEACHER", "STUDENT", ids["A"])
            grant("PSYCHOLOGY_TEACHER", "SCHOOL", 0)
            assert build_affairs_context(user("PSYCHOLOGY_TEACHER"), db).scope_type == "STUDENT"
            counselor = build_affairs_context(user("COUNSELOR"), db)
            assert counselor.require_student(db, ids["A"]).id == ids["A"]
            with pytest.raises(AppException):
                counselor.require_student(db, ids["C"])
            aid = build_affairs_context(user("FUNDING_TEACHER"), db)
            assert aid.scope_type == "COLLEGE"
            with pytest.raises(AppException):
                require_school_scope(db, user("FUNDING_TEACHER"))
            assert aid.require_student(db, ids["C"]).id == ids["C"]
            assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=ids["C"],
                                        role_codes={"FUNDING_TEACHER"}) == [account.id]
            assert resolve_assignee_ids(db, "COLLEGE_REVIEW", student_id=ids["A"],
                                        role_codes={"FUNDING_TEACHER"}) == []
            assert resolve_assignee_ids(db, "SCHOOL_REVIEW", student_id=ids["C"],
                                        role_codes={"FUNDING_TEACHER"}) == []
            with pytest.raises(AppException):
                aid.require_student(db, ids["A"])
            assert psy_scope_ids(db, user("PSYCHOLOGY_TEACHER")) == {ids["A"]}
            assert psy_scope_ids(db, user("COUNSELOR")) == set()
            assert psy_scope_ids(db, user("FUNDING_TEACHER")) == set()
            db.commit()
            from app.services.mobile_teacher_service import my_classes, my_students, resolve_teacher_scope
            mobile_psy_scope = resolve_teacher_scope(user("PSYCHOLOGY_TEACHER"))
            assert mobile_psy_scope["studentNos"] == {"A001"}
            assert mobile_psy_scope["classNames"] == set() and mobile_psy_scope["collegeNames"] == set()
            assert {row["studentId"] for row in my_students(user("FUNDING_TEACHER"))["items"]} == {str(ids["C"]), str(ids["D"])}
            assert {row["studentId"] for row in my_students(user("COUNSELOR"))["items"]} == {str(ids["A"])}
            with pytest.raises(AppException):
                my_classes(user("FUNDING_TEACHER"))
            funding.status = "REVOKED"
            grant("FUNDING_TEACHER", "SCHOOL", 0)
            assert build_affairs_context(user("FUNDING_TEACHER"), db).scope_type == "TENANT_ALL"
            assert require_school_scope(db, user("FUNDING_TEACHER")).scope_type == "TENANT_ALL"
            assert resolve_assignee_ids(db, "SCHOOL_REVIEW", student_id=ids["C"],
                                        role_codes={"FUNDING_TEACHER"}) == [account.id]
            assert build_affairs_context(user("COUNSELOR"), db).class_ids == {ids["cA"]}
            assert psy_scope_ids(db, user("PSYCHOLOGY_TEACHER")) == {ids["A"]}
            peer = StudentProfile(tenant_id=TID, student_no="SAME_CLASS_PEER", real_name="同班未授权学生",
                class_id=ids["cA"], college_id=ids["col1"], current_stage="CAMPUS",
                student_status="NORMAL", status="ACTIVE")
            db.add(peer); db.flush()
            records = [AffairsRiskRecord(tenant_id=TID, student_id=student_id, source="MENTAL",
                source_ref_id=ref, risk_level="LOW", title="逐生范围测试", status="NEW")
                for student_id, ref in ((ids["A"], 101), (peer.id, 102))]
            db.add_all(records); db.flush()
            other_risk = records[1].id
            psych_user = user("PSYCHOLOGY_TEACHER")
            db.commit()
        from app.services.affairs_risk_service import get_risk, list_risks
        items, total, _ = list_risks(psych_user)
        assert total == 1 and [item["studentId"] for item in items] == [str(ids["A"])]
        with pytest.raises(AppException):
            get_risk(other_risk, psych_user)
        assert [row["studentId"] for row in my_students(psych_user)["items"]] == [str(ids["A"])]
    finally:
        set_tenant(previous)


def test_funding_scope_editor_requires_explicit_school_or_college(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DataScopeRule, Role
    from app.services.role_assignment_scope_service import role_scope_policy
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code="FUNDING_TEACHER", role_name="资助职责",
                    role_type="SYSTEM", status="ACTIVE")
        db.add(role); db.flush()
        db.add(DataScopeRule(tenant_id=TID, role_code=role.role_code, rule_name="旧资助范围",
                            scope_type="FUNDING_BIZ", status="ACTIVE"))
        db.flush()
        policy = role_scope_policy(db, role)
        assert policy["scopeMode"] != "AUTO"
        assert policy["allowedScopeTypes"] == ["SCHOOL", "COLLEGE"]

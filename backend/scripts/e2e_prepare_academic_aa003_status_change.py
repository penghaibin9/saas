"""Prepare the isolated real-account fixture for AA-003 status-change Gold Deep.

This script runs only against a disposable e2e/test MySQL.  It reuses the canonical
identity-import accounts already used by browser acceptance and adds only the exact
AA-003 permission/scope graph required for the four-surface flow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaStatusChange,
    AaTerm,
    College,
    Permission,
    Role,
    RolePermission,
    SchoolClass,
    StudentProfile,
    TeacherStudentScope,
    Tenant,
    User,
    UserRole,
)

TID = 1000000000000000007
TENANT_CODE = "sandbox-school"
STUDENT_NO = "E2E20260001"
COUNSELOR_LOGIN = "e2e_advisor_a"
COUNSELOR_ROLE = "GD_MENTOR"
COLLEGE_LOGIN = "e2e_college_secretary"
COLLEGE_ROLE = "GD_COLLEGE_ADMIN"
OFFICE_LOGIN = "e2e_academic_admin"
OFFICE_ROLE = "ACADEMIC_ADMIN"
VIEW_PERM = "academicAffairs.statusChange.view"
COUNSELOR_PERM = "academicAffairs.statusChange.counselorReview"
COLLEGE_PERM = "academicAffairs.statusChange.collegeReview"
OFFICE_PERM = "academicAffairs.statusChange.officeReview"
STATE_PATH = Path(__file__).resolve().parents[1] / "tmp/e2e_academic_aa003_state.local.json"


def safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    env = str(os.getenv("APP_ENV") or "").lower()
    deploy = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env in {"prod", "production"} or deploy in {"prod", "production"}:
        raise SystemExit("refusing AA-003 fixture preparation in production")
    raw = str(os.getenv("DATABASE_URL") or "")
    lowered = raw.lower()
    if not raw or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    if urlparse(raw).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("AA-003 fixture only accepts local MySQL")


def one(db, model, **where):
    stmt = select(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    rows = db.scalars(stmt).all()
    if len(rows) != 1:
        raise SystemExit(f"expected one {model.__name__} for {where}, got {len(rows)}")
    return rows[0]


def ensure_permission(db, code: str):
    row = db.scalars(select(Permission).where(Permission.permission_code == code)).first()
    if row is None:
        row = Permission(
            permission_code=code,
            permission_name=code,
            module_code="academicAffairs",
            action="REVIEW" if code != VIEW_PERM else "VIEW",
        )
        db.add(row)
        db.flush()
    return row


def grant(db, user: User, role_code: str, permission_codes: tuple[str, ...]):
    role = one(db, Role, tenant_id=TID, role_code=role_code)
    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == TID,
        UserRole.user_id == int(user.id),
        UserRole.role_id == int(role.id),
        UserRole.is_deleted.is_(False),
    )).first()
    if link is None:
        raise SystemExit(f"{user.login_name} is not linked to required role {role_code}")
    link.status = "ACTIVE"
    for code in permission_codes:
        permission = ensure_permission(db, code)
        rp = db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == TID,
            RolePermission.role_id == int(role.id),
            RolePermission.permission_id == int(permission.id),
            RolePermission.is_deleted.is_(False),
        )).first()
        if rp is None:
            db.add(RolePermission(
                tenant_id=TID,
                role_id=int(role.id),
                permission_id=int(permission.id),
                status="ACTIVE",
            ))
        else:
            rp.status = "ACTIVE"
    return role


def ensure_scope(db, *, login: str, role_code: str, scope_type: str, ref_value: str, real_name: str):
    rows = db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == TID,
        TeacherStudentScope.teacher_key == login,
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == scope_type,
        TeacherStudentScope.ref_value == ref_value,
        TeacherStudentScope.is_deleted.is_(False),
    )).all()
    if len(rows) > 1:
        raise SystemExit(f"duplicate scope rows for {login}/{role_code}/{scope_type}/{ref_value}")
    if rows:
        row = rows[0]
        row.status = "ACTIVE"
        row.teacher_name = real_name
        return row
    row = TeacherStudentScope(
        tenant_id=TID,
        teacher_key=login,
        teacher_name=real_name,
        role_code=role_code,
        scope_type=scope_type,
        ref_value=ref_value,
        status="ACTIVE",
    )
    db.add(row)
    return row


def ensure_current_term(db):
    rows = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == TID,
        AaTerm.is_deleted.is_(False),
        AaTerm.is_current.is_(True),
    ).with_for_update()).all()
    for row in rows:
        row.is_current = False
    term = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == TID,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    )).first()
    if term is None:
        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="2026-2027学年第1学期",
            status="PUBLISHED",
            is_current=True,
        )
        db.add(term)
    else:
        term.status = "PUBLISHED"
        term.is_current = True
    db.flush()
    return term


def main() -> int:
    safe_target()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TID)
        if not tenant or tenant.tenant_code != TENANT_CODE:
            raise SystemExit("sandbox-school tenant fixture is missing")

        student = one(db, StudentProfile, tenant_id=TID, student_no=STUDENT_NO)
        if not student.class_id or not student.college_id or not student.major_id:
            raise SystemExit("AA-003 student must have class/college/major identity")
        klass = one(db, SchoolClass, id=int(student.class_id), tenant_id=TID)
        college = one(db, College, id=int(student.college_id), tenant_id=TID)
        counselor = one(db, User, tenant_id=TID, login_name=COUNSELOR_LOGIN)
        college_user = one(db, User, tenant_id=TID, login_name=COLLEGE_LOGIN)
        office_user = one(db, User, tenant_id=TID, login_name=OFFICE_LOGIN)

        # Use one simple status transition for the acceptance chain.  Identity import itself
        # does not make an academic status-change case; force a clean enrolled starting fact.
        student.student_status = "REGISTERED"
        student.status = "ACTIVE"
        student.is_deleted = False
        klass.status = "ACTIVE"
        klass.class_status = "NORMAL"
        college.status = "ACTIVE"
        college.is_deleted = False

        klass.counselor_id = int(counselor.id)
        college.secretary_id = int(college_user.id)

        grant(db, counselor, COUNSELOR_ROLE, (VIEW_PERM, COUNSELOR_PERM))
        grant(db, college_user, COLLEGE_ROLE, (VIEW_PERM, COLLEGE_PERM))
        grant(db, office_user, OFFICE_ROLE, (VIEW_PERM, OFFICE_PERM))
        ensure_scope(
            db,
            login=COUNSELOR_LOGIN,
            role_code=COUNSELOR_ROLE,
            scope_type="CLASS",
            ref_value=klass.class_name,
            real_name=counselor.real_name or COUNSELOR_LOGIN,
        )
        ensure_scope(
            db,
            login=COLLEGE_LOGIN,
            role_code=COLLEGE_ROLE,
            scope_type="COLLEGE",
            ref_value=college.college_name,
            real_name=college_user.real_name or COLLEGE_LOGIN,
        )
        term = ensure_current_term(db)

        active = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == TID,
            AaStatusChange.student_id == int(student.id),
            AaStatusChange.change_type == "SUSPEND",
            AaStatusChange.status.in_(("DRAFT", "SUBMITTED", "IN_REVIEW", "RETURNED")),
            AaStatusChange.is_deleted.is_(False),
        )).all()
        if active:
            raise SystemExit(f"AA-003 fixture is not clean; existing SUSPEND cases: {[r.id for r in active]}")

        db.commit()
        state = {
            "tenantId": str(TID),
            "tenantCode": TENANT_CODE,
            "studentId": str(student.id),
            "studentNo": student.student_no,
            "studentName": student.real_name,
            "studentBaseVersion": int(student.version or 0),
            "classId": str(klass.id),
            "className": klass.class_name,
            "collegeId": str(college.id),
            "collegeName": college.college_name,
            "termId": str(term.id),
            "termCode": f"{term.year_code}-{int(term.term_no)}",
            "accounts": {
                "counselor": {"login": COUNSELOR_LOGIN, "role": COUNSELOR_ROLE, "userId": str(counselor.id)},
                "college": {"login": COLLEGE_LOGIN, "role": COLLEGE_ROLE, "userId": str(college_user.id)},
                "office": {"login": OFFICE_LOGIN, "role": OFFICE_ROLE, "userId": str(office_user.id)},
            },
        }
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

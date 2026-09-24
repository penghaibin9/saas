"""Retire the legacy Academic E2E topology pollution from ``sandbox-school``.

The historical bootstrap added 2 colleges, 2 majors, 3 classes and 3 student
profiles to the exact 20K reference tenant.  That makes the authoritative 20K
gate fail even though the rows are synthetic.  This repair is deliberately
one-shot and narrow:

* default mode is read-only ``--dry-run``;
* ``--apply`` requires a verified tenant-scoped backup manifest and SQL digest;
* exact tenant identity, fixture names and row counts must match;
* rows are retired with the repository's soft-delete/status semantics;
* no standard 20K organization, profile or account is selected;
* the transaction commits only if the resulting profile is exactly
  ``standard-20k``.

The original rows remain recoverable from the mandatory logical backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import _mysql_env  # noqa: E402,F401
from app.db.session import get_sessionmaker  # noqa: E402
from app.models import (  # noqa: E402
    College,
    Major,
    Role,
    SchoolClass,
    StudentAccountLink,
    StudentProfile,
    Tenant,
    TeacherStudentScope,
    User,
    UserRole,
)
from app.services.sandbox_school_profile import (  # noqa: E402
    PROFILE_STANDARD,
    PROFILE_STANDARD_DAMAGED,
    classify_sandbox_profile,
)
from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID  # noqa: E402


COLLEGE_NAMES = {"E2E教务测试学院A", "E2E教务测试学院B"}
MAJOR_NAMES = {"E2E教务测试软件技术", "E2E教务测试机电一体化"}
CLASS_NAMES = {"E2E教务测试软技2601班", "E2E教务测试软技2602班", "E2E教务测试机电2601班"}
STUDENT_NUMBERS = {"E2EAA20260001", "E2EAA20260002", "E2EAA20260003"}
SECONDARY_ROLE_EXTRAS = {
    ("teacher2", "FUNDING_TEACHER"),
    ("sbx_t0478", "GD_COLLEGE_ADMIN"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_backup(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if str(manifest.get("tenantId")) != str(SANDBOX_TID) or manifest.get("tenantCode") != SANDBOX_CODE:
        raise RuntimeError("backup manifest tenant identity mismatch")
    dump = path.parent / str(manifest.get("dumpFile") or "")
    if not dump.is_file() or dump.stat().st_size != int(manifest.get("sizeBytes") or -1):
        raise RuntimeError("backup dump is missing or size does not match manifest")
    actual = _sha256(dump)
    if actual != manifest.get("sha256"):
        raise RuntimeError("backup dump SHA-256 does not match manifest")
    return {
        "manifest": str(path.resolve()),
        "dump": str(dump.resolve()),
        "sha256": actual,
        "sizeBytes": dump.stat().st_size,
        "tenantScopedTableCount": int(manifest.get("tenantScopedTableCount") or 0),
    }


def _inventory(db) -> dict:
    colleges = list(db.scalars(select(College).where(
        College.tenant_id == SANDBOX_TID,
        College.college_name.in_(COLLEGE_NAMES),
        College.is_deleted.is_(False),
    )).all())
    majors = list(db.scalars(select(Major).where(
        Major.tenant_id == SANDBOX_TID,
        Major.major_name.in_(MAJOR_NAMES),
        Major.is_deleted.is_(False),
    )).all())
    classes = list(db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == SANDBOX_TID,
        SchoolClass.class_name.in_(CLASS_NAMES),
        SchoolClass.is_deleted.is_(False),
    )).all())
    students = list(db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == SANDBOX_TID,
        StudentProfile.student_no.in_(STUDENT_NUMBERS),
        StudentProfile.is_deleted.is_(False),
    )).all())
    users = list(db.scalars(select(User).where(
        User.tenant_id == SANDBOX_TID,
        User.is_deleted.is_(False),
        (User.login_name.like("e2e_aa_%") | User.login_name.in_(STUDENT_NUMBERS)),
    )).all())
    user_ids = [int(row.id) for row in users]
    links = list(db.scalars(select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == SANDBOX_TID,
        StudentAccountLink.user_id.in_(user_ids or [-1]),
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    )).all())
    return {
        "colleges": colleges,
        "majors": majors,
        "classes": classes,
        "students": students,
        "users": users,
        "links": links,
    }


def _safe_summary(rows: dict) -> dict:
    return {
        "counts": {key: len(value) for key, value in rows.items()},
        "collegeIds": [str(row.id) for row in rows["colleges"]],
        "majorIds": [str(row.id) for row in rows["majors"]],
        "classIds": [str(row.id) for row in rows["classes"]],
        "studentIds": [str(row.id) for row in rows["students"]],
        "userIds": [str(row.id) for row in rows["users"]],
        "accountLinkIds": [str(row.id) for row in rows["links"]],
    }


def _role_residue(db) -> dict:
    users = list(db.scalars(select(User).where(
        User.tenant_id == SANDBOX_TID,
        (User.login_name.like("e2e_aa_%") | User.login_name.in_(STUDENT_NUMBERS)),
    )).all())
    user_ids = [int(row.id) for row in users]
    user_roles = list(db.scalars(select(UserRole).where(
        UserRole.tenant_id == SANDBOX_TID,
        UserRole.user_id.in_(user_ids or [-1]),
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
    )).all())
    teacher_scopes = list(db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == SANDBOX_TID,
        TeacherStudentScope.teacher_key.like("e2e_aa_%"),
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    )).all())
    return {"users": users, "userRoles": user_roles, "teacherScopes": teacher_scopes}


def _residue_summary(rows: dict) -> dict:
    return {
        "counts": {key: len(value) for key, value in rows.items()},
        "userIds": [str(row.id) for row in rows["users"]],
        "userRoleIds": [str(row.id) for row in rows["userRoles"]],
        "teacherScopeIds": [str(row.id) for row in rows["teacherScopes"]],
    }


def _retire_role_residue(rows: dict) -> None:
    for user_role in rows["userRoles"]:
        user_role.status = "DISABLED"
        user_role.is_deleted = True
        user_role.version = int(user_role.version or 0) + 1
    for scope in rows["teacherScopes"]:
        scope.status = "DISABLED"
        scope.is_deleted = True
        scope.version = int(scope.version or 0) + 1


def _secondary_role_extras(db) -> list[tuple[UserRole, str, str]]:
    rows = db.execute(
        select(UserRole, User.login_name, Role.role_code)
        .join(User, User.id == UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.tenant_id == SANDBOX_TID,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            User.login_name.in_({item[0] for item in SECONDARY_ROLE_EXTRAS}),
            Role.role_code.in_({item[1] for item in SECONDARY_ROLE_EXTRAS}),
        )
    ).all()
    selected = [(binding, str(login), str(role)) for binding, login, role in rows
                if (str(login), str(role)) in SECONDARY_ROLE_EXTRAS]
    actual = {(login, role) for _, login, role in selected}
    if actual and actual != SECONDARY_ROLE_EXTRAS:
        raise RuntimeError(
            "known pre-existing secondary-role drift does not match the exact repair set: "
            f"{[(login, role, binding.id) for binding, login, role in selected]}"
        )
    return selected


def _assert_exact(rows: dict) -> None:
    expected = {"colleges": 2, "majors": 2, "classes": 3, "students": 3, "users": 14, "links": 3}
    actual = {key: len(value) for key, value in rows.items()}
    if actual != expected:
        raise RuntimeError(f"fixture inventory mismatch; refusing repair: expected={expected} actual={actual}")
    if {row.college_name for row in rows["colleges"]} != COLLEGE_NAMES:
        raise RuntimeError("college identity mismatch")
    if {row.major_name for row in rows["majors"]} != MAJOR_NAMES:
        raise RuntimeError("major identity mismatch")
    if {row.class_name for row in rows["classes"]} != CLASS_NAMES:
        raise RuntimeError("class identity mismatch")
    if {row.student_no for row in rows["students"]} != STUDENT_NUMBERS:
        raise RuntimeError("student identity mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair Academic E2E pollution in exact sandbox 20K topology")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    args = parser.parse_args()
    if args.apply and args.backup_manifest is None:
        parser.error("--apply requires --backup-manifest")

    backup = _verify_backup(args.backup_manifest) if args.backup_manifest else None
    now = datetime.now().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, SANDBOX_TID)
        if tenant is None or tenant.tenant_code != SANDBOX_CODE or tenant.is_deleted:
            raise RuntimeError("sandbox tenant identity mismatch")
        before = classify_sandbox_profile(db, SANDBOX_TID)
        rows = _inventory(db)
        residue = _role_residue(db)
        phase = "TOPOLOGY_AND_ROLE_REPAIR"
        secondary_extras: list[tuple[UserRole, str, str]] = []
        if before.get("profile") == PROFILE_STANDARD_DAMAGED:
            _assert_exact(rows)
            if len(residue["users"]) != 14 or len(residue["userRoles"]) != 14 or len(residue["teacherScopes"]) != 4:
                raise RuntimeError(f"role residue inventory mismatch: {_residue_summary(residue)}")
        elif before.get("profile") == PROFILE_STANDARD:
            active_counts = {key: len(value) for key, value in rows.items()}
            if any(active_counts.values()):
                raise RuntimeError(f"standard profile still has active E2E topology rows: {active_counts}")
            if len(residue["users"]) != 14:
                raise RuntimeError(f"archived E2E user inventory mismatch: {_residue_summary(residue)}")
            if len(residue["userRoles"]) == 14 and len(residue["teacherScopes"]) == 4:
                phase = "ROLE_RESIDUE_REPAIR"
            elif not residue["userRoles"] and not residue["teacherScopes"]:
                secondary_extras = _secondary_role_extras(db)
                phase = (
                    "STANDARD_RELATIONSHIP_RECONCILE"
                    if secondary_extras
                    else "CURRENT_GRADUATION_WORKLOAD_RECONCILE"
                )
            else:
                raise RuntimeError(f"post-topology role residue mismatch: {_residue_summary(residue)}")
        else:
            raise RuntimeError(f"expected standard-20k family before repair, got {before}")
        print(json.dumps({
            "mode": "APPLY" if args.apply else "DRY_RUN",
            "phase": phase,
            "tenantId": str(SANDBOX_TID),
            "tenantCode": SANDBOX_CODE,
            "beforeProfile": before,
            "fixture": _safe_summary(rows),
            "roleResidue": _residue_summary(residue),
            "secondaryRoleExtras": [
                {"userRoleId": str(binding.id), "loginName": login, "roleCode": role}
                for binding, login, role in secondary_extras
            ],
            "backup": backup,
        }, ensure_ascii=False, indent=2))
        if args.dry_run:
            db.rollback()
            print("DRY_RUN PASS: exact legacy Academic E2E rows found; no writes")
            return 0

        _retire_role_residue(residue)
        mentor_reconcile = None
        if phase in {"STANDARD_RELATIONSHIP_RECONCILE", "CURRENT_GRADUATION_WORKLOAD_RECONCILE"}:
            for binding, _login, _role in secondary_extras:
                binding.status = "DISABLED"
                binding.is_deleted = True
                binding.version = int(binding.version or 0) + 1
            db.flush()
            from app.services.sandbox_school_mentor_workload import reconcile_school_mentor_workload_20k

            mentor_reconcile = reconcile_school_mentor_workload_20k(db, SANDBOX_TID)
        for link in rows["links"]:
            link.link_status = "REVOKED"
            link.unbound_at = now
            link.remark = "Academic V8.1 E2E fixture retired after verified 007 backup"
            link.is_deleted = True
            link.version = int(link.version or 0) + 1
        for user in rows["users"]:
            user.status = "DISABLED"
            user.is_deleted = True
            user.version = int(user.version or 0) + 1
        for student in rows["students"]:
            student.status = "INACTIVE"
            student.student_status = "RECYCLED"
            student.is_deleted = True
            student.version = int(student.version or 0) + 1
        for school_class in rows["classes"]:
            school_class.status = "DISABLED"
            school_class.class_status = "DISBANDED"
            school_class.is_deleted = True
            school_class.version = int(school_class.version or 0) + 1
        for major in rows["majors"]:
            major.status = "DISABLED"
            major.enroll_status = "STOPPED"
            major.is_deleted = True
            major.version = int(major.version or 0) + 1
        for college in rows["colleges"]:
            college.status = "DISABLED"
            college.is_deleted = True
            college.version = int(college.version or 0) + 1

        db.flush()
        after = classify_sandbox_profile(db, SANDBOX_TID)
        if after.get("profile") != PROFILE_STANDARD:
            raise RuntimeError(f"repair did not restore exact standard profile: {after}")
        db.commit()
        print(json.dumps({
            "afterProfile": after,
            "mentorRelationshipReconcile": mentor_reconcile,
            "status": "PASS",
        }, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

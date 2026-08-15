"""B8-02 exact-head IAM topology proof over the canonical #104 standard-20k school."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.core.permissions import ROLE_PERMISSIONS
from app.db.session import get_sessionmaker
from app.models import Role, StudentProfile, TeacherStudentScope, UserRole
from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
from app.services import system_role_shadow_service as shadow
from app.services.sandbox_school_master_seed import validate_school_master
from app.services.sandbox_school_role_reconcile import validate_school_roles_20k
from app.services.sandbox_service import SANDBOX_TID

DEMO_TID = 1000000000000000012


def main() -> None:
    head_sha = str(os.environ.get("B8_TOPOLOGY_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("B8_TOPOLOGY_EXPECTED_SHA/GITHUB_SHA is required")

    db = get_sessionmaker()()
    try:
        master = validate_school_master(db, SANDBOX_TID)
        roles = validate_school_roles_20k(db, SANDBOX_TID)
        neighbor_students = int(db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == DEMO_TID,
            StudentProfile.is_deleted.is_(False),
        )) or 0)
        user_role_total = int(db.scalar(select(func.count()).select_from(UserRole).where(
            UserRole.tenant_id == SANDBOX_TID,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        )) or 0)
        teacher_scope_total = int(db.scalar(select(func.count()).select_from(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == SANDBOX_TID,
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        )) or 0)
        active_role_total = int(db.scalar(select(func.count()).select_from(Role).where(
            Role.tenant_id == SANDBOX_TID,
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )) or 0)
    finally:
        db.close()

    if neighbor_students != 20:
        raise RuntimeError(f"neighbor tenant sentinel changed: expected=20 actual={neighbor_students}")
    if master.get("students") != 20000 or master.get("activeStudentLinks") != 20000 or master.get("studentAccounts") != 20000:
        raise RuntimeError(f"20K school identity topology incomplete: {master}")
    if master.get("backgroundStaffAccounts") != 1280 or roles.get("backgroundStaffAccounts") != 1280:
        raise RuntimeError(f"20K staff topology incomplete: master={master} roles={roles}")
    if not roles.get("passed") or roles.get("requiredRoles", 0) < 24 or roles.get("secondaryRoleBindings", 0) <= 0:
        raise RuntimeError(f"20K role topology incomplete: {roles}")

    convergence = shadow.converge_published_system_templates(actor_user_id=9902, source_commit_sha=head_sha)
    shadow_report = shadow.shadow_system_roles()
    if not shadow_report.get("zeroUnexplainedDrift") or shadow_report.get("tenantPermissionUniverseCount", 0) <= 400:
        raise RuntimeError(f"B8 shadow not sealed on 20K topology: {shadow_report}")
    if "*" not in set(ROLE_PERMISSIONS.get("SCHOOL_ADMIN", set())):
        raise RuntimeError("B8-02 must not retire SCHOOL_ADMIN runtime wildcard before the explicit cutover card")

    db = get_sessionmaker()()
    try:
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
        if template is None:
            raise RuntimeError("missing published SCHOOL_ADMIN TENANT RoleTemplate")
        template_codes = set(db.scalars(select(RoleTemplatePermission.permission_code).where(
            RoleTemplatePermission.tenant_id == 0,
            RoleTemplatePermission.role_template_id == int(template.id),
            RoleTemplatePermission.is_deleted.is_(False),
        )).all())
    finally:
        db.close()
    expected_codes = set(shadow.active_tenant_permission_codes())
    if template_codes != expected_codes:
        raise RuntimeError(f"SCHOOL_ADMIN explicit snapshot drift expected={len(expected_codes)} actual={len(template_codes)}")
    if any(code.startswith("platform.") or code.startswith("enterprise.") for code in template_codes):
        raise RuntimeError("SCHOOL_ADMIN snapshot contains forbidden PLATFORM/enterprise permission")

    evidence = {
        "schemaVersion": 1,
        "card": "CTRL-B8-02",
        "headSha": head_sha,
        "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schoolTenantId": SANDBOX_TID,
        "neighborTenantId": DEMO_TID,
        "neighborStudents": neighbor_students,
        "master": master,
        "roles": roles,
        "activeRoleTotal": active_role_total,
        "activeUserRoleTotal": user_role_total,
        "activeTeacherStudentScopeTotal": teacher_scope_total,
        "schoolAdminTemplateVersion": int(template.template_version or 0),
        "schoolAdminExplicitPermissionCount": len(template_codes),
        "tenantPermissionUniverseCount": len(expected_codes),
        "runtimeSchoolAdminWildcardStillPresent": True,
        "shadow": {
            "roleCount": shadow_report["roleCount"],
            "unexplainedDriftCount": shadow_report["unexplainedDriftCount"],
            "planeViolationCount": shadow_report["planeViolationCount"],
            "zeroUnexplainedDrift": shadow_report["zeroUnexplainedDrift"],
        },
        "templateConvergence": convergence,
        "goldCandidate": True,
    }
    path = Path(os.environ.get("B8_TOPOLOGY_EVIDENCE_PATH") or "../artifacts/control-plane/b8-20k-topology.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

"""Exact-head 20K IAM read-path query-bound proof.

This check runs after the canonical standard-20k school rebuild.  It measures
production service/router SQL rather than a synthetic query and fails if page
size, tenant isolation, aggregation, or constant-query budgets regress.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable

from sqlalchemy import event, func, select

from app.core.context import set_tenant, set_trace_id
from app.db.session import get_engine, get_sessionmaker
from app.models import Role, User, UserRole
from app.models.permission_governance import (
    TEMPLATE_CATEGORY_SYSTEM_ROLE,
    TEMPLATE_PLANE_TENANT,
    TEMPLATE_PUBLISHED,
    RoleTemplate,
)
from app.modules.system_admin.routers import system_bundle, system_i4_router
from app.modules.system_admin.services import school_iam_workspace_service as school_iam
from app.services.sandbox_service import SANDBOX_TID

ROOT = Path(__file__).resolve().parents[2]


def _measure(label: str, budget: int, operation: Callable[[], object]) -> tuple[object, dict]:
    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        if str(statement or "").lstrip().upper().startswith("SELECT"):
            statements.append(" ".join(str(statement).split())[:240])

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    started = perf_counter()
    try:
        result = operation()
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 3)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    query_count = len(statements)
    if query_count > budget:
        raise RuntimeError(
            f"{label} exceeded SELECT budget: actual={query_count} budget={budget} "
            f"firstStatements={statements[:20]}"
        )
    return result, {
        "selectCount": query_count,
        "selectBudget": budget,
        "durationMs": duration_ms,
        "bounded": True,
    }


def _fixtures() -> tuple[int, int, int]:
    db = get_sessionmaker()()
    try:
        student_role = db.scalar(select(Role).where(
            Role.tenant_id == SANDBOX_TID,
            Role.role_code == "STUDENT",
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        ).limit(1))
        if student_role is None:
            raise RuntimeError("20K school is missing active STUDENT role")
        subject_id = db.scalar(select(User.id).join(
            UserRole, UserRole.user_id == User.id
        ).where(
            User.tenant_id == SANDBOX_TID,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            UserRole.tenant_id == SANDBOX_TID,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        ).group_by(User.id).having(
            func.count(func.distinct(UserRole.role_id)) == 1,
        ).order_by(User.id).limit(1))
        if subject_id is None:
            raise RuntimeError("20K school is missing a single-role active subject for bounded Access Explain")
        template_id = db.scalar(select(RoleTemplate.id).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
            RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_code, RoleTemplate.template_version.desc()).limit(1))
        if template_id is None:
            raise RuntimeError("20K school is missing a published TENANT system-role template")
        return int(student_role.id), int(subject_id), int(template_id)
    finally:
        db.close()


def main() -> None:
    head_sha = str(os.environ.get("IAM_20K_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("IAM_20K_EXPECTED_SHA/GITHUB_SHA is required")

    set_tenant(SANDBOX_TID)
    set_trace_id(f"iam-20k-query-proof-{head_sha[:12]}")
    try:
        student_role_id, subject_id, template_id = _fixtures()
        actor = {"userId": "iam-20k-proof", "tenantId": str(SANDBOX_TID)}

        role_list, role_list_metric = _measure(
            "roleList",
            4,
            lambda: system_bundle.list_system_roles(
                keyword="", type="", status="", page=1, page_size=10, user=actor,
            ),
        )
        role_data = role_list["data"]
        if len(role_data["list"]) > 10 or int(role_data["pageSize"]) != 10:
            raise RuntimeError(f"role list is not SQL page bounded: {role_data}")

        members, member_metric = _measure(
            "roleMembers",
            3,
            lambda: system_i4_router.role_members(
                student_role_id, page=1, pageSize=50, user=actor,
            ),
        )
        member_data = members["data"]
        if len(member_data["items"]) > 50 or int(member_data["total"]) < 20000:
            raise RuntimeError(f"20K STUDENT member page is incomplete or unbounded: {member_data}")

        audit, audit_metric = _measure(
            "roleAudit",
            3,
            lambda: system_i4_router.role_audit(
                student_role_id, page=1, pageSize=50, user=actor,
            ),
        )
        audit_data = audit["data"]
        if len(audit_data["items"]) > 50:
            raise RuntimeError(f"role audit page is unbounded: {audit_data}")

        permission_tree, permission_metric = _measure(
            "permissionTree",
            0,
            school_iam.assignable_catalog,
        )
        if not permission_tree.get("assignablePermissions"):
            raise RuntimeError("Permission Catalog projection is unexpectedly empty")

        navigation_path = ROOT / "shared/contracts/navigation-surface-contract.json"
        navigation, navigation_metric = _measure(
            "navigationPreview",
            0,
            lambda: json.loads(navigation_path.read_text(encoding="utf-8")),
        )
        if int((navigation.get("counts") or {}).get("productionVisible") or 0) <= 0:
            raise RuntimeError("Navigation projection contract is unexpectedly empty")

        impact, impact_metric = _measure(
            "roleTemplateImpact",
            8,
            lambda: school_iam.school_template_impact(template_id),
        )
        if impact.get("affectedUserCountAuthority") != "DB_COUNT_DISTINCT_USER_ROLE":
            raise RuntimeError(f"RoleTemplate affected-user aggregation authority missing: {impact}")

        explanation, explain_metric = _measure(
            "accessExplainSingleObject",
            60,
            lambda: school_iam.explain_subject_access(
                subject_id,
                module_key="internship",
                permission_code="internship.recruitment.manage",
            ),
        )
        explained_roles = explanation.get("roles") or []
        if len(explained_roles) != 1 or str((explanation.get("subject") or {}).get("userId")) != str(subject_id):
            raise RuntimeError(f"Access Explain escaped its single-object fixture: {explanation}")

        evidence = {
            "schemaVersion": 1,
            "card": "IAM_W13_20K_QUERY_BOUNDS",
            "headSha": head_sha,
            "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tenantId": str(SANDBOX_TID),
            "scale": {
                "students": int(member_data["total"]),
                "roleTotal": int(role_data["total"]),
                "accessExplainSubjectRoles": len(explained_roles),
            },
            "checks": {
                "roleList": {**role_list_metric, "pageSize": 10, "returned": len(role_data["list"])},
                "roleMembers": {**member_metric, "pageSize": 50, "returned": len(member_data["items"])},
                "roleAudit": {**audit_metric, "pageSize": 50, "returned": len(audit_data["items"])},
                "permissionTree": {**permission_metric, "authority": "STATIC_PERMISSION_CATALOG"},
                "navigationPreview": {**navigation_metric, "authority": navigation.get("authority")},
                "roleTemplateImpact": {
                    **impact_metric,
                    "affectedPinnedCustomRoleCount": int(impact.get("affectedPinnedCustomRoleCount") or 0),
                    "affectedUserCount": int(impact.get("affectedUserCount") or 0),
                    "affectedUserCountAuthority": impact.get("affectedUserCountAuthority"),
                },
                "accessExplainSingleObject": {
                    **explain_metric,
                    "subjectUserId": str(subject_id),
                    "subjectRoleCount": len(explained_roles),
                },
            },
            "allBounded": True,
        }
        path = Path(os.environ.get("IAM_20K_QUERY_EVIDENCE_PATH") or "../artifacts/control-plane/iam-20k-query-bounds.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    finally:
        set_tenant(None)
        set_trace_id("-")


if __name__ == "__main__":
    main()

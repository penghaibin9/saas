"""审计演示租户中需要人工范围但尚未落库的角色授权。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import Role, RoleAssignmentScope, User, UserRole  # noqa: E402
from app.services.role_assignment_scope_service import role_scope_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="审计角色授权范围断链")
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()

    missing = []
    with get_sessionmaker()() as db:
        rows = db.execute(
            select(UserRole, User, Role)
            .join(User, User.id == UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.tenant_id == args.tenant_id,
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
                User.tenant_id == args.tenant_id,
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
                Role.tenant_id == args.tenant_id,
                Role.status == "ACTIVE",
                Role.is_deleted.is_(False),
            )
            .order_by(User.login_name, Role.role_code)
        ).all()
        scoped_user_role_ids = set(
            db.scalars(
                select(RoleAssignmentScope.user_role_id).where(
                    RoleAssignmentScope.tenant_id == args.tenant_id,
                    RoleAssignmentScope.status == "ACTIVE",
                    RoleAssignmentScope.is_deleted.is_(False),
                )
            ).all()
        )
        policy_by_role_id = {}
        for user_role, user, role in rows:
            policy = policy_by_role_id.get(int(role.id))
            if policy is None:
                policy = role_scope_policy(db, role)
                policy_by_role_id[int(role.id)] = policy
            # 全校角色无需额外选节点；AUTO 角色依赖授课/指导等业务关系。
            if policy["scopeMode"] == "AUTO" or policy["scopeType"] == "SCHOOL":
                continue
            if int(user_role.id) not in scoped_user_role_ids:
                missing.append(
                    {
                        "userRoleId": str(user_role.id),
                        "userId": str(user.id),
                        "loginName": user.login_name,
                        "roleCode": role.role_code,
                        "roleName": role.role_name,
                        "scopeMode": policy["scopeMode"],
                        "scopeType": policy["scopeType"],
                    }
                )

    role_counts = Counter(row["roleCode"] for row in missing)
    role_samples = {
        role_code: [
            row["loginName"] for row in missing if row["roleCode"] == role_code
        ][:3]
        for role_code in sorted(role_counts)
    }
    payload = {
        "tenantId": str(args.tenant_id),
        "activeUserRoleCount": len(rows),
        "missingManualScopeCount": len(missing),
        "missingByRole": dict(sorted(role_counts.items())),
        "policyByRole": {
            role_code: {
                "scopeMode": next(
                    row["scopeMode"] for row in missing if row["roleCode"] == role_code
                ),
                "scopeType": next(
                    row["scopeType"] for row in missing if row["roleCode"] == role_code
                ),
            }
            for role_code in sorted(role_counts)
        },
        "samplesByRole": role_samples,
    }
    if args.details:
        payload["missingManualScopes"] = missing
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

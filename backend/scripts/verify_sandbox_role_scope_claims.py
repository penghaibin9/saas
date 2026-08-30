"""验证代表演示账号切换角色后能拿到与新版授权表一致的组织/学生范围。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import RoleAssignmentScope, User  # noqa: E402
from app.services.auth_service_db import _claims, _role_contexts  # noqa: E402


CASES = (
    ("sbx_aa001", "COLLEGE_ADMIN", "COLLEGE", "collegeIds"),
    ("sbx_aa001", "GD_MAJOR_ADMIN", "MAJOR", "majorIds"),
    ("sbx_c001", "COUNSELOR", "CLASS", "classIds"),
    ("sbx_sa001", "STUDENT_AFFAIRS", "COLLEGE", "collegeIds"),
    ("sbx_sa001", "PSYCHOLOGY_TEACHER", "STUDENT", "studentIds"),
    ("sbx_sa001", "EMPLOYMENT_TEACHER", "COLLEGE", "collegeIds"),
)


def main() -> int:
    tenant_id = 1000000000000000007
    results = []
    with get_sessionmaker()() as db:
        for login_name, role_code, scope_type, claim_key in CASES:
            user = db.scalars(select(User).where(
                User.tenant_id == tenant_id,
                User.login_name == login_name,
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
            )).one()
            contexts = _role_contexts(db, user)
            context = next(row for row in contexts if row["roleCode"] == role_code)
            claims = _claims(db, user, context, contexts, "PC")
            persisted = {
                str(value)
                for value in db.scalars(select(RoleAssignmentScope.scope_id).where(
                    RoleAssignmentScope.tenant_id == tenant_id,
                    RoleAssignmentScope.user_id == user.id,
                    RoleAssignmentScope.role_code == role_code,
                    RoleAssignmentScope.scope_type == scope_type,
                    RoleAssignmentScope.status == "ACTIVE",
                    RoleAssignmentScope.is_deleted.is_(False),
                )).all()
            }
            projected = {str(value) for value in claims.get(claim_key) or []}
            if not persisted or persisted != projected:
                raise RuntimeError(
                    f"{login_name}/{role_code} 范围投影不一致: "
                    f"persisted={sorted(persisted)} projected={sorted(projected)}"
                )
            results.append({
                "loginName": login_name,
                "roleCode": role_code,
                "scopeType": scope_type,
                "scopeCount": len(projected),
                "claimKey": claim_key,
                "scopeIds": sorted(projected),
            })
    print(json.dumps({"passed": True, "cases": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

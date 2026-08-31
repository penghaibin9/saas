"""Activate two existing 20K actors for Academic Browser/Playwright journeys.

The reference school already contains real teacher/student identities, schedules,
registrations and stable account links.  Creating extra colleges, classes or
student profiles would corrupt its exact 20K topology signature.  This utility
therefore changes only the password hashes of one allow-listed teacher and one
allow-listed student, then verifies both through the real login endpoint.

Safety properties:
- default is read-only ``--dry-run``;
- the immutable ``sandbox-school`` tenant identity is checked before any write;
- the two exact reference logins are hard-coded and their expected roles checked;
- it never creates organizations, profiles, accounts, roles or data scopes;
- no password or password hash is printed;
- credentials are written only to the existing ignored ``backend/tmp`` location.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.security import hash_password, verify_password  # noqa: E402
from app.core.tenant_identity import SANDBOX_SCHOOL  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
import _mysql_env  # noqa: E402,F401
from app.models import Role, Tenant, User, UserRole  # noqa: E402
from app.services.sandbox_school_profile import classify_sandbox_profile, is_standard_family  # noqa: E402
from scripts import e2e_bootstrap_academic_affairs_accounts as academic_e2e  # noqa: E402

CRED_PATH = academic_e2e.CRED_PATH
STABLE_PWD = academic_e2e.STABLE_PWD
STATE_PATH = academic_e2e.STATE_PATH
TENANT = academic_e2e.TENANT
academic_e2e.BASE = os.environ.get("ACADEMIC_E2E_BASE_URL", academic_e2e.BASE).rstrip("/")
_req = academic_e2e._req


TARGET_ROLES = {
    "sbx_t0257": "ACADEMIC_TEACHER",
    "2024S0002": "STUDENT",
}


def _target_logins() -> list[str]:
    values = list(TARGET_ROLES)
    if values != ["sbx_t0257", "2024S0002"]:
        raise RuntimeError("reference actor allow-list changed unexpectedly")
    return values


def _inventory(db, tenant_id: int, logins: list[str]) -> tuple[dict[str, User], dict[str, list[str]]]:
    users = {
        row.login_name: row
        for row in db.scalars(select(User).where(
            User.tenant_id == tenant_id,
            User.login_name.in_(logins),
            User.is_deleted.is_(False),
        )).all()
    }
    role_rows = db.execute(
        select(User.login_name, Role.role_code)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.tenant_id == tenant_id,
            User.login_name.in_(logins),
            User.is_deleted.is_(False),
            UserRole.tenant_id == tenant_id,
            UserRole.is_deleted.is_(False),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        )
    ).all()
    roles: dict[str, list[str]] = {login: [] for login in logins}
    for login, role_code in role_rows:
        roles.setdefault(str(login), []).append(str(role_code))
    return users, roles


def _verify_login(login: str, index: int) -> dict:
    response = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": f"10.252.81.{20 + index}"},
        body={"loginName": login, "password": STABLE_PWD, "tenantCode": TENANT},
    )
    ok = response.get("code") == 0
    data = response.get("data") or {}
    return {
        "loginName": login,
        "ok": ok,
        "role": (data.get("currentRole") or {}).get("roleCode") if ok else None,
        "message": None if ok else response.get("message"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Activate dedicated Academic E2E sandbox actors")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    logins = _target_logins()
    db = get_sessionmaker()()
    try:
        tenant = db.scalar(select(Tenant).where(
            Tenant.id == SANDBOX_SCHOOL.tenant_id,
            Tenant.tenant_code == SANDBOX_SCHOOL.tenant_code,
            Tenant.is_deleted.is_(False),
        ))
        if tenant is None or tenant.tenant_code != TENANT:
            print("REFUSED: immutable sandbox-school identity mismatch")
            return 2

        profile = classify_sandbox_profile(db, int(tenant.id))
        if not is_standard_family(profile):
            print(json.dumps({"REFUSED": "not a standard-20k family database", "profile": profile},
                             ensure_ascii=False, indent=2))
            return 2

        users, roles = _inventory(db, int(tenant.id), logins)
        missing = sorted(set(logins) - set(users))
        inventory = [
            {
                "loginName": login,
                "status": users[login].status if login in users else "MISSING",
                "roles": sorted(set(roles.get(login) or [])),
            }
            for login in logins
        ]
        role_mismatch = {
            login: {"expected": TARGET_ROLES[login], "actual": sorted(set(roles.get(login) or []))}
            for login in logins
            if TARGET_ROLES[login] not in set(roles.get(login) or [])
        }
        print(json.dumps({
            "tenantCode": tenant.tenant_code,
            "tenantId": str(tenant.id),
            "profile": profile,
            "targetCount": len(logins),
            "missing": missing,
            "roleMismatch": role_mismatch,
            "accounts": inventory,
            "mode": "DRY_RUN" if args.dry_run else "CONFIRM",
        }, ensure_ascii=False, indent=2))
        if missing or role_mismatch:
            print("REFUSED: exact reference actors or roles are missing")
            return 3
        if args.dry_run:
            print(json.dumps({
                "plannedPasswordHashUpdates": logins,
                "plannedEntityCreates": 0,
                "topologyPreserved": True,
            }, ensure_ascii=False, indent=2))
            print("DRY_RUN PASS: no database writes; confirm changes two password hashes only")
            return 0

        password_hash = hash_password(STABLE_PWD)
        for login in logins:
            user = users[login]
            user.password_hash = password_hash
            user.must_change_password = False
            user.status = "ACTIVE"
            user.version = int(user.version or 0) + 1
        db.commit()
        db.expire_all()

        for login in logins:
            refreshed = db.get(User, users[login].id)
            if refreshed is None or not verify_password(STABLE_PWD, refreshed.password_hash):
                raise RuntimeError(f"password hash verification failed for {login}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    results = [_verify_login(login, index) for index, login in enumerate(logins)]
    ok_logins = sorted(item["loginName"] for item in results if item["ok"])
    credential_payload = {
        "tenantCode": TENANT,
        "stablePassword": STABLE_PWD,
        "passwords": {login: STABLE_PWD for login in ok_logins},
        "loginResults": results,
        "method": "sandbox-guarded password-only activation + real /auth/login verification",
        "note": "existing reference identities only; local secret file; do not commit",
    }
    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps(credential_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update({
        "tenantCode": TENANT,
        "accounts": logins,
        "loginOk": ok_logins,
        "passwordFile": str(CRED_PATH),
    })
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"REAL_LOGIN_PASS={len(ok_logins)}/{len(logins)}")
    return 0 if len(ok_logins) == len(logins) else 4


if __name__ == "__main__":
    raise SystemExit(main())

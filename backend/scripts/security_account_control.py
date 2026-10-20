#!/usr/bin/env python3
"""OS-operator incident containment. Default inspect is read-only.

There is deliberately no HTTP route and no re-enable/password-setting action.
New WX approval issuance will be enabled only with its consuming runtime/UI.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--tenant-code", required=True)
    result.add_argument("--user-id", required=True, type=int)
    result.add_argument("--action", choices=("inspect", "contain"), default="inspect")
    result.add_argument("--expected-version", type=int)
    result.add_argument("--incident-ref")
    result.add_argument("--apply", action="store_true")
    return result


def _operator() -> str:
    if os.name == "posix":
        import pwd
        return "os:" + pwd.getpwuid(os.geteuid()).pw_name[:90]
    return "os:" + getpass.getuser()[:90]


def _invalidate_after_commit(user_id: int, tenant_id: int) -> bool:
    """Return whether cache recovery is required, never replay a committed mutation."""
    try:
        from app.services.auth_service_db import invalidate_subject_cache
        from app.core.redis_client import redis_health
        invalidate_subject_cache(f"db-{user_id}", tenant_id)
        return not bool(redis_health().get("ok"))
    except Exception:
        return True


def main(argv=None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    args.tenant_code = args.tenant_code.strip()
    if not 1 <= len(args.tenant_code) <= 100 or args.user_id <= 0:
        arguments.error("A bounded tenant code and positive user ID are required")
    writing = args.action == "contain"
    incident = str(args.incident_ref or "").strip()
    if writing and (not args.apply or args.expected_version is None or args.expected_version < 0
                    or not 3 <= len(incident) <= 120):
        arguments.error("Containment requires --apply, --expected-version and a 3..120 character incident reference")
    if args.apply and not writing:
        arguments.error("--apply requires --action contain")

    db = None
    commit_attempted = False
    committed = False
    try:
        from sqlalchemy import select
        from app.core.config import settings
        from app.db.session import db_enabled, get_sessionmaker
        from app.models import Tenant, User
        if not db_enabled() or settings.db_dialect != "mysql":
            raise RuntimeError("Explicit MySQL runtime required")
        db = get_sessionmaker()()
        tenant = db.scalars(select(Tenant).where(Tenant.tenant_code == args.tenant_code)).one_or_none()
        if tenant is None:
            raise RuntimeError("Unknown tenant")
        if not writing:
            user = db.scalars(select(User).where(
                User.id == args.user_id, User.tenant_id == tenant.id,
                User.is_deleted.is_(False),
            )).one_or_none()
            if user is None:
                raise RuntimeError("Unknown subject in specified tenant")
            print(json.dumps({"readOnly": True, "changed": False, "tenantId": str(tenant.id),
                              "userId": str(user.id), "status": user.status, "version": int(user.version or 0)}))
            return 0

        from app.services.account_compromise_service import contain_in_session
        result = contain_in_session(
            db, tenant_id=int(tenant.id), user_id=args.user_id,
            expected_version=args.expected_version, incident_ref=incident, operator=_operator(),
        )
        commit_attempted = True
        db.commit()
        committed = True
        cache_recovery = _invalidate_after_commit(args.user_id, int(tenant.id))
        print(json.dumps({**result, "changed": True, "committed": True,
                          "recoveryRequired": True, "cacheRecoveryRequired": cache_recovery,
                          "replayContainment": False}, ensure_ascii=False))
        return 0
    except Exception as exc:
        if db is not None and not committed:
            try:
                db.rollback()
            except Exception:
                pass
        # A failed commit acknowledgement can be ambiguous. Inspect the subject
        # before retrying; never print a connection URL, password or traceback.
        print(json.dumps({"ok": False, "errorType": type(exc).__name__,
                          "commitAttempted": commit_attempted,
                          "outcome": "COMMITTED" if committed else "UNCONFIRMED" if commit_attempted else "NOT_COMMITTED",
                          "replayContainment": False,
                          "reinspectRequired": True}), file=sys.stderr)
        return 1
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                print(json.dumps({"resourceCleanupRequired": True}), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

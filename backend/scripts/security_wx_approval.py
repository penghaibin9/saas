#!/usr/bin/env python3
"""OS-only independent approval of new school WeChat bindings.

No HTTP issuer; --apply and an independent identity-verification reference are
mandatory. A password or wxToken alone is not proof of the applicant's identity.
Approval is delivered to a new 0600 file only AFTER its audit transaction commits.
The existing security_account_control inspect/contain command is unchanged.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--tenant-code", required=True)
    result.add_argument("--user-id", type=int, required=True)
    result.add_argument("--expected-version", type=int, required=True)
    result.add_argument("--incident-ref", required=True)
    result.add_argument("--identity-verified", action="store_true")
    result.add_argument("--ticket-file", type=Path, required=True)
    result.add_argument("--apply", action="store_true")
    return result


def _hidden_token() -> str:
    # getpass normally falls back to echoed input without a TTY. Refuse that
    # fallback so a redirected CI log can never capture the applicant's token.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass("Applicant wxToken (hidden; never enter a campus password): ").strip()


def _operator() -> str:
    import pwd
    return "os:" + pwd.getpwuid(os.geteuid()).pw_name[:90]


def main(argv=None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    args.tenant_code = args.tenant_code.strip()
    args.incident_ref = args.incident_ref.strip()
    if (not args.apply or not args.identity_verified or args.user_id <= 0
            or args.expected_version < 0 or not 1 <= len(args.tenant_code) <= 100
            or not 3 <= len(args.incident_ref) <= 120):
        arguments.error("Require explicit --apply, independent verification, exact subject/version and bounded incident reference")

    db = None
    ticket = None
    commit_attempted = False
    committed = False
    delivery_complete = False
    approval_ref = None
    try:
        if os.name != "posix":
            raise RuntimeError("Use the controlled Linux backend environment for private ticket delivery")
        # Reserve without clobbering a file/symlink. Do not print a code to stdout.
        fd = os.open(args.ticket_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        ticket = os.fdopen(fd, "w", encoding="utf-8")
        from sqlalchemy import select
        from app.core.config import settings
        from app.db.session import db_enabled, get_sessionmaker
        from app.models import Tenant
        from app.services.wx_auth_service import openid_from_bind_token
        from app.services.wx_binding_approval_service import issue_in_session
        if not db_enabled() or settings.db_dialect != "mysql":
            raise RuntimeError("Explicit MySQL runtime required")
        raw = _hidden_token()
        if not 10 <= len(raw) <= 2000:
            raise ValueError("Invalid applicant token length")
        openid = openid_from_bind_token(raw)
        del raw
        # Human input completes before any database lock is acquired.
        db = get_sessionmaker()()
        tenant = db.scalars(select(Tenant).where(Tenant.tenant_code == args.tenant_code)).one_or_none()
        if tenant is None:
            raise RuntimeError("Unknown tenant")
        result = issue_in_session(
            db, tenant_id=int(tenant.id), user_id=args.user_id,
            expected_version=args.expected_version, openid=openid,
            incident_ref=args.incident_ref, operator=_operator(), identity_verified=True,
        )
        approval_ref = result["approvalRef"]
        commit_attempted = True
        db.commit()
        committed = True
        json.dump(result, ticket, ensure_ascii=False)
        ticket.write("\n")
        ticket.flush()
        os.fsync(ticket.fileno())
        delivery_complete = True
        print(json.dumps({"committed": True, "delivered": True, "approvalRef": approval_ref,
                          "expiresIn": result["expiresIn"], "ticketFile": str(args.ticket_file)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        if db is not None and not committed:
            try:
                db.rollback()
            except Exception:
                pass
        # After a failed commit ACK or delivery, a grant might exist. Never
        # replay automatically; examine the audit ref or let its 5-minute TTL lapse.
        print(json.dumps({"ok": False, "errorType": type(exc).__name__,
                          "approvalRef": approval_ref, "deliveryComplete": delivery_complete,
                          "outcome": "COMMITTED" if committed else "UNCONFIRMED" if commit_attempted else "NOT_COMMITTED",
                          "replayApproval": False, "reinspectRequired": True}), file=sys.stderr)
        return 1
    finally:
        if ticket is not None:
            try:
                ticket.close()
            except Exception:
                print(json.dumps({"privateFileCleanupRequired": True}), file=sys.stderr)
        if db is not None:
            try:
                db.close()
            except Exception:
                print(json.dumps({"resourceCleanupRequired": True}), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

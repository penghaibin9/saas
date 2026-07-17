"""Backfill cross-domain student_id links safely.

Dry-run is the default.  Matching prefers tenant + student number.  Orientation
records, which historically only had admission number/name, use admission number
first and a unique-in-tenant name only as an explicitly reported legacy fallback.

Usage:
  python scripts/backfill_student_domain_links.py
  python scripts/backfill_student_domain_links.py --apply --confirm BACKFILL-STUDENT-ID
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AcademicStudent, EmpStudent, OrientationStudent, StudentProfile, Tenant

CONFIRM = "BACKFILL-STUDENT-ID"


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    return parser.parse_args()


def _maps(profiles):
    by_no = {str(p.student_no).strip(): p for p in profiles if p.student_no}
    names = defaultdict(list)
    for profile in profiles:
        names[str(profile.real_name or "").strip()].append(profile)
    unique_name = {name: rows[0] for name, rows in names.items() if name and len(rows) == 1}
    ambiguous_names = {name for name, rows in names.items() if name and len(rows) > 1}
    return by_no, unique_name, ambiguous_names


def _candidate(row, domain: str, by_no, unique_name):
    if domain in ("academic", "employment"):
        profile = by_no.get(str(row.student_no or "").strip())
        if profile:
            return profile, "student_no"
    if domain == "orientation":
        profile = by_no.get(str(row.admission_no or "").strip())
        if profile:
            return profile, "admission_no"
    profile = unique_name.get(str(row.name or "").strip())
    return (profile, "unique_name") if profile else (None, "unmatched")


def main() -> int:
    args = _args()
    if args.apply and args.confirm != CONFIRM:
        raise SystemExit(f"--apply requires --confirm {CONFIRM}")
    db = get_sessionmaker()()
    totals = defaultdict(int)
    try:
        tenant_stmt = select(Tenant.id)
        if args.tenant_id:
            tenant_stmt = tenant_stmt.where(Tenant.id == args.tenant_id)
        tenant_ids = list(db.scalars(tenant_stmt))
        for tenant_id in tenant_ids:
            profiles = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False))).all()
            by_no, unique_name, ambiguous_names = _maps(profiles)
            print(f"tenant={tenant_id} profiles={len(profiles)} ambiguousNames={len(ambiguous_names)}")
            for domain, model in (
                ("academic", AcademicStudent),
                ("employment", EmpStudent),
                ("orientation", OrientationStudent),
            ):
                rows = db.scalars(select(model).where(
                    model.tenant_id == tenant_id,
                    model.student_id.is_(None),
                    model.is_deleted.is_(False))).all()
                for row in rows:
                    profile, method = _candidate(row, domain, by_no, unique_name)
                    totals[f"{domain}:{method}"] += 1
                    if profile is not None and args.apply:
                        row.student_id = profile.id
                print(f"  {domain}: missing={len(rows)}")
            if args.apply:
                db.commit()
            else:
                db.rollback()
        print("summary")
        for key in sorted(totals):
            print(f"  {key}={totals[key]}")
        print("mode=" + ("APPLIED" if args.apply else "DRY_RUN"))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

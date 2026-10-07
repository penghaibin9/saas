#!/usr/bin/env python3
"""Rebuild searchable sensitive-field hashes after an explicit HMAC-key rotation.

This is deliberately separate from ``rewrap_encrypted_fields.py``: encryption
key rotation must not silently alter lookup hashes.  Run it only against an
isolated, verified copy after supplying the *old* search-HMAC key through the
process environment.  It never prints plaintext or either key.

The script refuses an unknown hash format or an ambiguous contact type rather
than guessing.  That makes a failed dry run a release blocker, not a reason to
publish an environment where phone/ID lookups silently stop working.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.field_crypto import decrypt_field, hash_sensitive  # noqa: E402


def _old_hash(value: str, field_type: str, key: str) -> str:
    return hmac.new(
        key.encode(), f"{field_type}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def _hash_for_contact(value: str, stored_hash: str, old_key: str) -> str:
    """Keep the historical field type, but refuse to infer it without proof."""
    matches = [
        field_type for field_type in ("phone", "email", "generic")
        if hmac.compare_digest(_old_hash(value, field_type, old_key), stored_hash)
    ]
    if len(matches) != 1:
        raise ValueError("contact hash cannot be matched to one approved field type")
    return hash_sensitive(value, matches[0]) or ""


def _rehash_hmac_pairs(db, old_key: str, dry_run: bool) -> tuple[int, int]:
    from app.models import StudentContact, StudentLoan, StudentParentLink, StudentProfile, User
    from app.models.internship import InternshipComplaint

    fixed = (
        (StudentLoan, "receipt_code_encrypted", "receipt_code_hash", "loan_receipt"),
        (InternshipComplaint, "complainant_contact_encrypted", "complainant_contact_hash", "internship_complaint_contact"),
        (StudentProfile, "id_card_encrypted", "id_card_hash", "id_card"),
        (User, "phone_encrypted", "phone_hash", "phone"),
    )
    scanned = changed = 0
    for model, encrypted_name, hash_name, field_type in fixed:
        for row in db.scalars(select(model)).yield_per(500):
            stored = getattr(row, encrypted_name)
            old_value = getattr(row, hash_name)
            if not stored or not old_value:
                continue
            plain = decrypt_field(stored, allow_legacy_plaintext=False)
            if plain is None or not hmac.compare_digest(_old_hash(plain, field_type, old_key), old_value):
                raise ValueError(f"{model.__tablename__}.{hash_name} does not match its verified legacy contract")
            scanned += 1
            new_value = hash_sensitive(plain, field_type)
            if not hmac.compare_digest(new_value or "", old_value):
                changed += 1
                if not dry_run:
                    setattr(row, hash_name, new_value)

    for row in db.scalars(select(StudentContact)).yield_per(500):
        if not row.contact_value_encrypted or not row.contact_value_hash:
            continue
        plain = decrypt_field(row.contact_value_encrypted, allow_legacy_plaintext=False)
        if plain is None:
            raise ValueError("t_student_contact encrypted value could not be decrypted")
        scanned += 1
        new_value = _hash_for_contact(plain, row.contact_value_hash, old_key)
        if not hmac.compare_digest(new_value, row.contact_value_hash):
            changed += 1
            if not dry_run:
                row.contact_value_hash = new_value

    # Older parent links used raw SHA-256 while newer paths already used the old
    # HMAC.  Both are legacy formats; normalize them to the keyed phone digest
    # consumed by the deployed guardian authorization service.
    for row in db.scalars(select(StudentParentLink)).yield_per(500):
        if not row.guardian_phone_encrypted or not row.guardian_phone_hash:
            continue
        plain = decrypt_field(row.guardian_phone_encrypted, allow_legacy_plaintext=False)
        normalized = (plain or "").strip()
        old_sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        old_hmac = _old_hash(normalized, "phone", old_key)
        if not (hmac.compare_digest(old_sha, row.guardian_phone_hash)
                or hmac.compare_digest(old_hmac, row.guardian_phone_hash)):
            raise ValueError("t_student_parent_link.guardian_phone_hash does not match a verified legacy contract")
        scanned += 1
        new_value = hash_sensitive(normalized, "phone")
        if not hmac.compare_digest(new_value or "", row.guardian_phone_hash):
            changed += 1
            if not dry_run:
                row.guardian_phone_hash = new_value

    return scanned, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="verify and count only")
    args = parser.parse_args()
    old_key = os.environ.get("OLD_SENSITIVE_SEARCH_HMAC_KEY", "").strip()
    if not old_key:
        raise SystemExit("OLD_SENSITIVE_SEARCH_HMAC_KEY is required and must be supplied outside source control")

    from app.core.field_crypto import assert_field_encryption_safe
    from app.db.session import get_sessionmaker

    assert_field_encryption_safe()
    db = get_sessionmaker()()
    try:
        scanned, changed = _rehash_hmac_pairs(db, old_key, args.dry_run)
        if not args.dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    action = "would update" if args.dry_run else "updated"
    print(f"verified {scanned} searchable sensitive rows; {action} {changed} HMAC hashes; plaintext not emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

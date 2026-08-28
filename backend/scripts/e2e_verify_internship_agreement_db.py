"""Read-only MySQL seal for IX-011 agreement lifecycle Browser First evidence."""
from __future__ import annotations

import os

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import FileObject, InternshipAgreement, InternshipAuditTrail

TENANT_ID = 1000000000000000007


def need(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"missing {name}")
    return value


def main() -> int:
    old_id = int(need("E2E_IX011_OLD_AGREEMENT_ID"))
    new_id = int(need("E2E_IX011_NEW_AGREEMENT_ID"))
    internship_id = int(need("E2E_IX011_INTERNSHIP_ID"))
    student_name = need("E2E_IX011_STUDENT_NAME")
    company_name = need("E2E_IX011_COMPANY_NAME")
    position_name = need("E2E_IX011_POSITION_NAME")
    reject_reason = need("E2E_IX011_REJECT_REASON")

    db = get_sessionmaker()()
    try:
        old = db.scalar(select(InternshipAgreement).where(
            InternshipAgreement.id == old_id,
            InternshipAgreement.tenant_id == TENANT_ID,
            InternshipAgreement.internship_id == internship_id,
            InternshipAgreement.is_deleted.is_(False),
        ))
        new = db.scalar(select(InternshipAgreement).where(
            InternshipAgreement.id == new_id,
            InternshipAgreement.tenant_id == TENANT_ID,
            InternshipAgreement.internship_id == internship_id,
            InternshipAgreement.is_deleted.is_(False),
        ))
        assert old is not None, "old rejected agreement missing"
        assert new is not None, "replacement archived agreement missing"
        assert old.id != new.id, "reissue must create a new immutable agreement instance"

        assert old.status == "REJECTED", old.status
        assert old.student_confirm_status == "REJECTED", old.student_confirm_status
        assert reject_reason in (old.reject_reason or ""), old.reject_reason

        assert new.status == "ARCHIVED", new.status
        assert new.student_confirm_status == "CONFIRMED", new.student_confirm_status
        assert new.enterprise_confirm_status == "CONFIRMED", new.enterprise_confirm_status
        assert new.school_confirm_status == "CONFIRMED", new.school_confirm_status
        assert new.file_id, "signed scan file_id missing"
        assert new.source_file_id == new.file_id, (new.source_file_id, new.file_id)
        assert new.source_type == "FILE_EVIDENCE", new.source_type
        assert new.recorded_by_name, "school recorder missing"
        assert new.enterprise_confirm_at is not None
        assert new.school_confirm_at is not None
        assert int(new.version or 0) >= 5, new.version

        body = new.rendered_body or ""
        for text in (student_name, company_name, position_name):
            assert text in body, f"rendered template snapshot missing {text!r}"

        try:
            file_pk = int(str(new.file_id))
        except ValueError as exc:
            raise AssertionError(f"unexpected file id format: {new.file_id}") from exc
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == file_pk,
            FileObject.tenant_id == TENANT_ID,
            FileObject.is_deleted.is_(False),
        ))
        assert file_obj is not None, "agreement scan FileObject missing"
        assert file_obj.status in {"AVAILABLE", "UPLOADED", "READY"}, file_obj.status
        assert (file_obj.mime_type or "").startswith("image/"), file_obj.mime_type
        assert int(file_obj.size_bytes or 0) > 0, file_obj.size_bytes
        assert file_obj.sha256, "agreement scan sha256 missing"

        old_actions = [row.action for row in db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "AGREEMENT",
            InternshipAuditTrail.target_id == old_id,
        ).order_by(InternshipAuditTrail.id)).all()]
        new_actions = [row.action for row in db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "AGREEMENT",
            InternshipAuditTrail.target_id == new_id,
        ).order_by(InternshipAuditTrail.id)).all()]
        assert old_actions == ["GENERATE", "ISSUE", "STUDENT_REJECT"], old_actions
        for action in ["GENERATE", "ISSUE", "STUDENT_CONFIRM", "ENTERPRISE_CONFIRM", "SCHOOL_CONFIRM", "ARCHIVE"]:
            assert action in new_actions, (action, new_actions)
        assert new_actions.index("GENERATE") < new_actions.index("ISSUE") < new_actions.index("STUDENT_CONFIRM")
        assert new_actions.index("STUDENT_CONFIRM") < new_actions.index("ENTERPRISE_CONFIRM") < new_actions.index("SCHOOL_CONFIRM") < new_actions.index("ARCHIVE")

        print("[ix-011-db-seal] PASS", {
            "oldAgreementId": str(old.id),
            "newAgreementId": str(new.id),
            "oldActions": old_actions,
            "newActions": new_actions,
            "fileId": new.file_id,
            "version": int(new.version or 0),
        })
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

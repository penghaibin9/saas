"""Read-only MySQL verification for the browser-created internship application journey."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipApplication, InternshipAuditTrail, InternshipRecord
from app.models.file import FileBinding, FileObject

TENANT_ID = 1000000000000000007


def required(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def assert_safe_target() -> None:
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("refusing to inspect production/staging database")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("application DB verifier only accepts a local database")


def main() -> int:
    assert_safe_target()
    app_id = int(required("E2E_INTERNSHIP_APPLICATION_ID"))
    final_file_id = int(required("E2E_INTERNSHIP_APPLICATION_FILE_ID"))
    expected_company = required("E2E_INTERNSHIP_APPLICATION_COMPANY")
    expected_position = required("E2E_INTERNSHIP_APPLICATION_POSITION")

    db = get_sessionmaker()()
    try:
        app = db.get(InternshipApplication, app_id)
        if not app or app.tenant_id != TENANT_ID or app.is_deleted:
            raise AssertionError("browser-created application missing from MySQL")
        if app.status != "APPROVED":
            raise AssertionError(f"application status is {app.status}, expected APPROVED")
        if app.application_type != "SELF_ARRANGED":
            raise AssertionError(f"application type is {app.application_type}")
        if app.company_name != expected_company or app.position_name != expected_position:
            raise AssertionError("application destination does not match browser input")
        if int(app.evidence_file_id or 0) != final_file_id:
            raise AssertionError("application does not reference the final browser-uploaded evidence file")

        record = db.get(InternshipRecord, app.record_id)
        if not record or record.tenant_id != TENANT_ID or record.is_deleted:
            raise AssertionError("authoritative internship record missing")
        if record.destination_type != "SELF_ARRANGED":
            raise AssertionError(f"destination_type is {record.destination_type}, expected SELF_ARRANGED")
        if record.enterprise_name != expected_company or record.position_name != expected_position:
            raise AssertionError("approved application did not land the authoritative destination")

        trails = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == TENANT_ID,
            InternshipAuditTrail.target_type == "APPLICATION",
            InternshipAuditTrail.target_id == app_id,
        ).order_by(InternshipAuditTrail.id)).all()
        actions = [row.action for row in trails]
        required_actions = ["SAVE_DRAFT", "SUBMIT", "REJECT", "APPROVE"]
        for action in required_actions:
            if action not in actions:
                raise AssertionError(f"missing application audit action {action}: {actions}")
        if actions.count("SAVE_DRAFT") < 2 or actions.count("SUBMIT") < 2:
            raise AssertionError(f"resubmit version history is incomplete: {actions}")

        file_obj = db.get(FileObject, final_file_id)
        if not file_obj or file_obj.tenant_id != TENANT_ID or file_obj.is_deleted:
            raise AssertionError("final evidence FileObject missing")
        if str(file_obj.biz_type or "").upper() != "INTERNSHIP_APPLICATION":
            raise AssertionError(f"file biz_type is {file_obj.biz_type}")
        if str(file_obj.biz_id or "") != str(app_id):
            raise AssertionError(f"file biz_id is {file_obj.biz_id}, expected {app_id}")
        if str(file_obj.visibility or "").upper() != "BIZ_SCOPED":
            raise AssertionError(f"file visibility is {file_obj.visibility}")

        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == TENANT_ID,
            FileBinding.file_id == final_file_id,
            FileBinding.biz_type == "INTERNSHIP_APPLICATION",
            FileBinding.biz_id == str(app_id),
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        )).first()
        if not binding:
            raise AssertionError("active business-scoped file binding is missing")
        if binding.student_id and int(binding.student_id) != int(app.student_id):
            raise AssertionError("file binding student scope does not match application student")

        evidence = {
            "tenantId": str(app.tenant_id),
            "applicationId": str(app.id),
            "studentId": str(app.student_id),
            "recordId": str(app.record_id),
            "status": app.status,
            "destinationType": record.destination_type,
            "companyName": app.company_name,
            "positionName": app.position_name,
            "fileId": str(final_file_id),
            "fileBizType": file_obj.biz_type,
            "fileVisibility": file_obj.visibility,
            "bindingId": str(binding.id),
            "auditActions": actions,
        }
        print("[internship-application-db-audit] DB_EVIDENCE_OK")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

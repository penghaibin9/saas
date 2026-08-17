"""INT MySQL lifecycle proof for Program through the shared File Exchange owner."""
from __future__ import annotations

import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker

TID = 1000000000000000001
USER_ID = 81001


def _user() -> dict:
    return {
        "tenantId": str(TID),
        "userId": str(USER_ID),
        "realName": "Program shared lifecycle tester",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "permissions": ["*"],
        "dataScope": "ALL",
    }


def _patch_program_scope(monkeypatch) -> None:
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_confirm_service as binding
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as definition
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_service as preview

    context = lambda _user, _db: SimpleNamespace(  # noqa: E731 - frozen TENANT_ALL fixture
        scope_type="TENANT_ALL",
        college_ids=set(),
        class_ids=set(),
    )
    monkeypatch.setattr(preview, "build_affairs_context", context)
    monkeypatch.setattr(definition, "build_affairs_context", context)
    monkeypatch.setattr(binding, "build_affairs_context", context)


def _seed_authorities_and_file(workbook: bytes) -> tuple[int, str, int]:
    from app.models import AaCourse, Major, Tenant
    from app.models.file import FileObject
    from app.services import data_exchange_job_service as jobs
    from app.services.file_scan_constants import SCAN_NOT_REQUIRED

    suffix = uuid.uuid4().hex[:10].upper()
    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code=f"program-shared-{suffix.lower()}",
                school_name=f"Program shared lifecycle school {suffix}",
                status="ACTIVE",
            ))
            db.flush()
        major = Major(
            tenant_id=TID,
            college_id=889001,
            major_name=f"Program shared software {suffix}",
            code=f"PS{suffix}",
            status="ACTIVE",
            education_years=3,
            enroll_status="ENROLLING",
        )
        course = AaCourse(
            tenant_id=TID,
            course_code=f"PSC{suffix}",
            course_name=f"Program shared course {suffix}",
            category="MAJOR_CORE",
            nature="REQUIRED",
            credit=3,
            exam_mode="EXAM",
            is_core=True,
            prerequisite_codes_json="[]",
            applicable_majors_json="[]",
            is_all_major=False,
            version=1,
            status="ENABLED",
        )
        db.add_all([major, course])
        db.flush()
        now = jobs._now()
        file_row = FileObject(
            tenant_id=TID,
            file_key=f"program-shared/{suffix}/source.xlsx",
            file_name="academic_program_import.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=len(workbook),
            sha256=hashlib.sha256(workbook).hexdigest(),
            biz_type="ACADEMIC_PROGRAM_IMPORT_SOURCE",
            owner_user_id=USER_ID,
            created_by=USER_ID,
            visibility="PRIVATE",
            security_level="SENSITIVE",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="IMPORT",
            upload_source="USER",
            scan_required=False,
            scan_status=SCAN_NOT_REQUIRED,
            scan_attempts=0,
            scanned_at=now,
            available_at=now,
        )
        db.add(file_row)
        db.commit()
        return int(major.id), str(course.course_code), int(file_row.id)
    finally:
        db.close()


def _workbook_bytes(*, major_id: int, course_code: str, series_key: str) -> bytes:
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_workbook_adapter as workbook

    content = workbook.build_program_import_template()
    wb = load_workbook(BytesIO(content))
    try:
        for sheet_name in ("培养方案", "方案课程", "学分要求", "实践环节", "毕业要求", "适用范围"):
            wb[sheet_name]["A2"] = series_key
        wb["培养方案"]["C2"] = "Program shared 2026 definition"
        wb["培养方案"]["D2"] = major_id
        wb["方案课程"]["C2"] = course_code
        wb["适用范围"]["C2"] = major_id
        # PRACTICE is optional; keep this contract focused on shared job lifecycle.
        wb["实践环节"].delete_rows(2, 1)
        output = BytesIO()
        wb.save(output)
        return output.getvalue()
    finally:
        wb.close()


def _replace_file_payload(file_id: int, workbook: bytes) -> None:
    from app.models.file import FileObject

    db = get_sessionmaker()()
    try:
        row = db.get(FileObject, file_id)
        assert row is not None
        row.size_bytes = len(workbook)
        row.sha256 = hashlib.sha256(workbook).hexdigest()
        db.commit()
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_program_shared_importjob_definition_then_binding_real_mysql_lifecycle(tmp_path, monkeypatch):
    from app.models import AaProgram, AaProgramBinding
    from app.models.data_exchange import ImportJob
    from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
    from app.services import data_exchange_confirm_service as confirm
    from app.services import file_scan_service

    user = _user()
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    try:
        _patch_program_scope(monkeypatch)

        # Seed authorities first, then replace the template's placeholder IDs with
        # the real Major/Course values.  The FileObject is real; only the physical
        # storage/scan edge is substituted because File Center owns that contract.
        placeholder = b"program-shared-placeholder"
        major_id, course_code, file_id = _seed_authorities_and_file(placeholder)
        series_key = f"INT-SHARED-{uuid.uuid4().hex[:12].upper()}"
        workbook = _workbook_bytes(
            major_id=major_id,
            course_code=course_code,
            series_key=series_key,
        )
        _replace_file_payload(file_id, workbook)
        source_path = Path(tmp_path) / "academic_program_import.xlsx"
        source_path.write_bytes(workbook)
        monkeypatch.setattr(exchange, "_source_file_path", lambda _row, _user: source_path)
        monkeypatch.setattr(file_scan_service, "assert_file_ready_for_business", lambda *_args, **_kwargs: None)

        definition_job = exchange.create_academic_import_job(
            filename=source_path.name,
            source_file_id=file_id,
            import_type=exchange.ACADEMIC_PROGRAM_IMPORT,
            context={"phase": "DEFINITION"},
            user=user,
        )
        assert definition_job["status"] == "VALIDATED"
        assert definition_job["validRows"] == 5
        assert definition_job["invalidRows"] == 0
        assert definition_job["preview"]["invalidRows"] == 0

        definition_done = confirm.confirm_import_job(
            definition_job["id"],
            expected_version=definition_job["version"],
            user=user,
        )
        assert definition_done["status"] == "SUCCEEDED"
        assert definition_done["confirmedRows"] == 5
        assert definition_done["result"]["phase"] == "DEFINITION"

        db = get_sessionmaker()()
        try:
            program = db.scalars(select(AaProgram).where(
                AaProgram.tenant_id == TID,
                AaProgram.series_key == series_key,
                AaProgram.version == 1,
                AaProgram.is_deleted.is_(False),
            )).one()
            program_id = int(program.id)
            assert program.status == "DRAFT"
            definition_row = db.get(ImportJob, int(definition_job["id"]))
            assert definition_row is not None
            assert definition_row.status == "SUCCEEDED"
            assert definition_row.lease_token is None
            assert definition_row.lease_started_at is None
            assert dict(definition_row.source_snapshot_json or {})["context"] == {"phase": "DEFINITION"}
            assert dict(definition_row.source_snapshot_json or {}).get("rowDigest")

            # Approval is intentionally outside ordinary import.  BINDING may only
            # activate a definition that is already PUBLISHED/ENABLED.
            program.status = "PUBLISHED"
            db.commit()
        finally:
            db.close()

        binding_job = exchange.create_academic_import_job(
            filename=source_path.name,
            source_file_id=file_id,
            import_type=exchange.ACADEMIC_PROGRAM_IMPORT,
            context={"phase": "BINDING"},
            user=user,
        )
        assert binding_job["status"] == "VALIDATED"
        assert binding_job["validRows"] == 5
        assert binding_job["invalidRows"] == 0

        binding_done = confirm.confirm_import_job(
            binding_job["id"],
            expected_version=binding_job["version"],
            user=user,
        )
        assert binding_done["status"] == "SUCCEEDED"
        assert binding_done["confirmedRows"] == 5
        assert binding_done["result"]["phase"] == "BINDING"

        db = get_sessionmaker()()
        try:
            program = db.get(AaProgram, program_id)
            assert program is not None and program.status == "ENABLED"
            bindings = db.scalars(select(AaProgramBinding).where(
                AaProgramBinding.tenant_id == TID,
                AaProgramBinding.major_id == major_id,
                AaProgramBinding.grade_year == "2026",
                AaProgramBinding.class_id.is_(None),
                AaProgramBinding.is_deleted.is_(False),
            )).all()
            assert len(bindings) == 1
            assert int(bindings[0].program_id) == program_id
            assert bindings[0].status == "ACTIVE"

            binding_row = db.get(ImportJob, int(binding_job["id"]))
            assert binding_row is not None
            assert binding_row.status == "SUCCEEDED"
            assert binding_row.lease_token is None
            assert binding_row.lease_started_at is None
            assert dict(binding_row.source_snapshot_json or {})["context"] == {"phase": "BINDING"}
            assert dict(binding_row.source_snapshot_json or {}).get("rowDigest")
        finally:
            db.close()
    finally:
        set_current_user(None)
        set_tenant(None)

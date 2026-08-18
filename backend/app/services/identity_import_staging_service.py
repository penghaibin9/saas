"""I3 normalized identity-import staging authority.

Scanned XLSX rows are streamed into MySQL in bounded chunks. Validation and final
onboarding reuse the existing canonical business services through repeatable lazy
sequences, so a 20K job never needs a 20K Python row list or batch JSON payload.
"""
from __future__ import annotations

import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import delete, func, select, update

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import IdentityImportStagingRow, ImportRowError
from app.models.identity_import_batch import IdentityImportBatch
from app.services.identity_import_path_parser import _open, _sha256
from app.services.identity_import_file_service import (
    BATCH_TTL_SECONDS,
    STUDENT_HEADERS,
    STUDENT_REQUIRED_HEADERS,
    TEACHER_HEADERS,
    TEACHER_REQUIRED_HEADERS,
    _row_cells,
    _user_key,
)

MAX_STAGING_ROWS = 20_000
STAGING_CHUNK_SIZE = 500
STAGING_MARKER_VERSION = 1


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_digest(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _kind(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized not in {"STUDENT", "TEACHER"}:
        raise AppException("VALIDATION_ERROR", "身份导入类型仅支持 STUDENT 或 TEACHER")
    return normalized


def _payload_from_cells(kind: str, row_no: int, cells: dict, errors: list[dict]) -> tuple[str, dict]:
    if kind == "STUDENT":
        account_no, name = cells["学号"], cells["姓名"]
        if not account_no:
            errors.append({"row": row_no, "entity": "student", "field": "学号", "error": "学号必填"})
        if not name:
            errors.append({"row": row_no, "entity": "student", "field": "姓名", "error": "姓名必填"})
        if not cells["班级名称"]:
            errors.append({
                "row": row_no, "entity": "student", "field": "班级名称",
                "error": "班级必填：学生必须归属完整的学院、专业、班级",
            })
        return account_no, {
            "_rowNo": row_no,
            "studentNo": account_no,
            "name": name,
            "collegeName": cells["所属学院"],
            "majorName": cells["所属专业"],
            "className": cells["班级名称"],
            "grade": cells["年级"],
            "gender": cells["性别"],
            "idCard": cells["身份证号"],
        }
    account_no, name = cells["工号"], cells["姓名"]
    if not account_no:
        errors.append({"row": row_no, "entity": "teacher", "field": "工号", "error": "工号必填"})
    if not name:
        errors.append({"row": row_no, "entity": "teacher", "field": "姓名", "error": "姓名必填"})
    if not cells["预设角色编码"]:
        errors.append({
            "row": row_no, "entity": "teacher", "field": "预设角色编码",
            "error": "教师必须指定预设角色编码",
        })
    return account_no, {
        "_rowNo": row_no,
        "loginName": account_no,
        "name": name,
        "departmentName": cells["所属部门"],
        "positionName": cells["岗位名称"],
        "roleCodes": cells["预设角色编码"],
        "scopeType": cells["数据范围类型"],
        "scopeRef": cells["数据范围引用"],
    }


class StagingRowSequence:
    """Repeatable keyset-paged view over staged rows; never materializes the job."""

    def __init__(self, tenant_id: int, import_job_id: int, entity_type: str, *, chunk_size: int = STAGING_CHUNK_SIZE):
        self.tenant_id = int(tenant_id)
        self.import_job_id = int(import_job_id)
        self.entity_type = _kind(entity_type)
        self.chunk_size = max(1, min(int(chunk_size), 2000))

    def __bool__(self) -> bool:
        db = get_sessionmaker()()
        try:
            return bool(db.scalar(select(func.count(IdentityImportStagingRow.id)).where(
                IdentityImportStagingRow.tenant_id == self.tenant_id,
                IdentityImportStagingRow.import_job_id == self.import_job_id,
                IdentityImportStagingRow.entity_type == self.entity_type,
                IdentityImportStagingRow.is_deleted.is_(False),
            )) or 0)
        finally:
            db.close()

    def __iter__(self):
        db = get_sessionmaker()()
        try:
            last_row = 0
            while True:
                rows = list(db.scalars(select(IdentityImportStagingRow).where(
                    IdentityImportStagingRow.tenant_id == self.tenant_id,
                    IdentityImportStagingRow.import_job_id == self.import_job_id,
                    IdentityImportStagingRow.entity_type == self.entity_type,
                    IdentityImportStagingRow.row_no > last_row,
                    IdentityImportStagingRow.is_deleted.is_(False),
                ).order_by(IdentityImportStagingRow.row_no).limit(self.chunk_size)).all())
                if not rows:
                    break
                for row in rows:
                    yield dict(row.payload_json or {})
                last_row = int(rows[-1].row_no)
                db.expunge_all()
        finally:
            db.close()


def lazy_payload(tenant_id: int, job_id: int) -> dict:
    return {
        "tenantId": str(int(tenant_id)),
        "students": StagingRowSequence(tenant_id, job_id, "STUDENT"),
        "teachers": StagingRowSequence(tenant_id, job_id, "TEACHER"),
        "atomic": True,
    }


def stage_identity_xlsx(
    *, path: str | Path, filename: str, kind: str, tenant_id: int, job_id: int, actor_id: int | None,
) -> dict:
    """Stream a scanned workbook into normalized staging in <=500-row commits."""
    file_path = Path(path)
    kind_up = _kind(kind)
    if kind_up == "STUDENT":
        headers, required, what = STUDENT_HEADERS, STUDENT_REQUIRED_HEADERS, "学生导入"
    else:
        headers, required, what = TEACHER_HEADERS, TEACHER_REQUIRED_HEADERS, "教师导入"

    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(
            ImportRowError.tenant_id == int(tenant_id),
            ImportRowError.import_job_id == int(job_id),
        ))
        db.execute(delete(IdentityImportStagingRow).where(
            IdentityImportStagingRow.tenant_id == int(tenant_id),
            IdentityImportStagingRow.import_job_id == int(job_id),
        ))
        db.commit()
    finally:
        db.close()

    workbook, iterator, parsed_headers = _open(
        file_path, filename, headers=headers, required=required, what=what
    )
    header_index = {name: parsed_headers.index(name) for name in headers if name in parsed_headers}
    parser_errors: list[dict] = []
    pending: list[IdentityImportStagingRow] = []
    total = 0
    db = get_sessionmaker()()
    try:
        for row_no, values in enumerate(iterator, 2):
            row_errors: list[dict] = []
            entity = "student" if kind_up == "STUDENT" else "teacher"
            cells, empty = _row_cells(values, headers, header_index, row_no, row_errors, entity)
            if empty:
                continue
            total += 1
            if total > MAX_STAGING_ROWS:
                raise AppException(
                    "VALIDATION_ERROR",
                    f"单个身份导入任务最多 {MAX_STAGING_ROWS} 行；请拆分后重试",
                )
            natural_key, payload = _payload_from_cells(kind_up, row_no, cells, row_errors)
            parser_errors.extend(row_errors)
            pending.append(IdentityImportStagingRow(
                tenant_id=int(tenant_id),
                import_job_id=int(job_id),
                row_no=int(row_no),
                entity_type=kind_up,
                natural_key=str(natural_key or ""),
                payload_json=payload,
                validation_status="PENDING",
                error_count=0,
                row_digest=_row_digest(payload),
                created_by=actor_id,
                updated_by=actor_id,
            ))
            if len(pending) >= STAGING_CHUNK_SIZE:
                db.add_all(pending)
                db.commit()
                pending.clear()
                db.expunge_all()
        if pending:
            db.add_all(pending)
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        workbook.close()
        db.close()
    if total == 0:
        raise AppException("VALIDATION_ERROR", "Excel 没有数据行，请填写后再上传")
    count, digest = staging_fingerprint(int(tenant_id), int(job_id))
    if count != total:
        raise AppException("STAGING_INTEGRITY_DRIFT", "staging 行数与解析结果不一致", http_status=409)
    return {
        "totalRows": total,
        "fileName": str(filename),
        "fileSha256": _sha256(file_path),
        "kind": kind_up,
        "parserErrors": parser_errors,
        "stagingDigest": digest,
    }


def staging_fingerprint(tenant_id: int, job_id: int) -> tuple[int, str]:
    """Recompute row payload digests and aggregate digest; detects DB payload tampering."""
    digest = hashlib.sha256()
    count = 0
    db = get_sessionmaker()()
    try:
        last_row = 0
        while True:
            rows = list(db.scalars(select(IdentityImportStagingRow).where(
                IdentityImportStagingRow.tenant_id == int(tenant_id),
                IdentityImportStagingRow.import_job_id == int(job_id),
                IdentityImportStagingRow.row_no > last_row,
                IdentityImportStagingRow.is_deleted.is_(False),
            ).order_by(IdentityImportStagingRow.row_no).limit(STAGING_CHUNK_SIZE)).all())
            if not rows:
                break
            for row in rows:
                actual = _row_digest(dict(row.payload_json or {}))
                if actual != str(row.row_digest or ""):
                    raise AppException(
                        "STAGING_INTEGRITY_DRIFT",
                        "身份导入 staging payload 与 rowDigest 不一致，拒绝确认",
                        http_status=409,
                        details={"rowNo": int(row.row_no)},
                    )
                digest.update(f"{int(row.row_no)}:{actual}\n".encode("utf-8"))
                count += 1
            last_row = int(rows[-1].row_no)
            db.expunge_all()
    finally:
        db.close()
    return count, digest.hexdigest()


def assert_staging_integrity(
    *, tenant_id: int, job_id: int, expected_rows: int, expected_digest: str,
) -> None:
    count, digest = staging_fingerprint(tenant_id, job_id)
    if count != int(expected_rows) or digest != str(expected_digest or ""):
        raise AppException(
            "STAGING_INTEGRITY_DRIFT",
            "身份导入 staging 已发生漂移，拒绝确认；请重新上传预检",
            http_status=409,
            details={"expectedRows": int(expected_rows), "actualRows": count},
        )


def expand_staging_marker(source: dict) -> dict:
    """Mutate claimed batch payload into lazy sequences before canonical onboarding."""
    marker = source.pop("_staging", None)
    if not marker:
        return source
    tenant_id = int(source.get("tenantId") or marker.get("tenantId") or 0)
    job_id = int(marker.get("jobId") or 0)
    if not tenant_id or not job_id:
        raise AppException("STAGING_INTEGRITY_DRIFT", "身份导入 staging marker 不完整", http_status=409)
    assert_staging_integrity(
        tenant_id=tenant_id,
        job_id=job_id,
        expected_rows=int(marker.get("rows") or 0),
        expected_digest=str(marker.get("digest") or ""),
    )
    source["tenantId"] = str(tenant_id)
    source["students"] = StagingRowSequence(tenant_id, job_id, "STUDENT")
    source["teachers"] = StagingRowSequence(tenant_id, job_id, "TEACHER")
    source["atomic"] = True
    return source


def validate_staging(*, user: dict, tenant_id: int, job_id: int, parser_errors: list[dict]) -> dict:
    """Reuse canonical preview against repeatable DB-backed sequences, then persist row truth."""
    from app.services.identity_import_service import preview_identity_import

    report = preview_identity_import(user, lazy_payload(tenant_id, job_id), pre_errors=parser_errors)
    errors = list(report.get("errors") or [])
    counts: dict[int, int] = {}
    for item in errors:
        row_no = int(item.get("row") or 0)
        if row_no > 0:
            counts[row_no] = counts.get(row_no, 0) + 1

    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(
            ImportRowError.tenant_id == int(tenant_id),
            ImportRowError.import_job_id == int(job_id),
        ))
        db.execute(update(IdentityImportStagingRow).where(
            IdentityImportStagingRow.tenant_id == int(tenant_id),
            IdentityImportStagingRow.import_job_id == int(job_id),
            IdentityImportStagingRow.is_deleted.is_(False),
        ).values(validation_status="VALID", error_count=0))
        for row_no, error_count in counts.items():
            db.execute(update(IdentityImportStagingRow).where(
                IdentityImportStagingRow.tenant_id == int(tenant_id),
                IdentityImportStagingRow.import_job_id == int(job_id),
                IdentityImportStagingRow.row_no == int(row_no),
                IdentityImportStagingRow.is_deleted.is_(False),
            ).values(validation_status="INVALID", error_count=int(error_count)))
        for item in errors:
            db.add(ImportRowError(
                tenant_id=int(tenant_id),
                import_job_id=int(job_id),
                sheet_name="导入模板",
                row_no=int(item.get("row") or 0) or None,
                field_code=str(item.get("field") or "")[:100] or None,
                error_code=str(item.get("errorCode") or "VALIDATION_ERROR")[:80],
                error_message=str(item.get("message") or item.get("error") or "校验失败")[:1000],
                raw_snapshot_json={"entity": item.get("entity"), "row": item.get("row")},
            ))
        db.commit()
    finally:
        db.close()
    report["errors"] = errors
    return report


def create_staging_batch(
    *, user: dict, tenant_id: int, job_id: int, filename: str, file_sha256: str,
    total_rows: int, staging_digest: str, report: dict,
) -> dict:
    """Persist only a bounded marker; normalized staging remains the row authority."""
    errors = list(report.get("errors") or [])
    invalid_rows = {int(item.get("row") or 0) for item in errors if int(item.get("row") or 0) > 0}
    invalid_count = len(invalid_rows) if invalid_rows else (1 if errors else 0)
    batch_no = f"IDSTG{datetime.utcnow():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"
    bounded_errors = errors[:200]
    if len(errors) > len(bounded_errors):
        bounded_errors.append({
            "row": 0, "entity": "batch", "field": "",
            "error": f"另有 {len(errors) - 200} 条错误，完整明细以 ImportRowError/错误回执为准",
        })
    summary_report = {
        key: value for key, value in report.items()
        if key not in {"errors", "studentCredentials", "teacherCredentials"}
    }
    summary_report["errors"] = bounded_errors
    db = get_sessionmaker()()
    try:
        db.add(IdentityImportBatch(
            tenant_id=int(tenant_id),
            batch_no=batch_no,
            operator_key=_user_key(user),
            file_name=str(filename),
            file_sha256=str(file_sha256),
            status="VALIDATED",
            payload_json={
                "tenantId": str(int(tenant_id)),
                "students": [],
                "teachers": [],
                "atomic": True,
                "_staging": {
                    "version": STAGING_MARKER_VERSION,
                    "tenantId": int(tenant_id),
                    "jobId": int(job_id),
                    "rows": int(total_rows),
                    "digest": str(staging_digest),
                },
            },
            raw_rows_json=[],
            errors_json=bounded_errors if errors else [],
            pre_errors_json=[],
            report_json=summary_report,
            relationships_json=[],
            relation_errors_json=[],
            expires_at=datetime.utcnow() + timedelta(seconds=BATCH_TTL_SECONDS),
        ))
        db.commit()
    finally:
        db.close()
    return {
        "batchNo": batch_no,
        "fileName": str(filename),
        "total": int(total_rows),
        "valid": max(int(total_rows) - invalid_count, 0),
        "invalid": int(invalid_count),
        "errors": errors,
        "roleTemplateVersion": report.get("roleTemplateVersion"),
        "entities": report.get("entities") or {},
        "stagingDigest": str(staging_digest),
    }


def build_staging_error_workbook(*, tenant_id: int, job_id: int) -> bytes:
    """Stream authoritative ImportRowError rows to xlsx without a 20K raw-row map."""
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("师生账号导入错误")
    ws.append(["Excel行号", "账号类型", "工号/学号", "姓名", "对象", "错误字段", "错误原因"])
    db = get_sessionmaker()()
    try:
        last_id = 0
        while True:
            errors = list(db.scalars(select(ImportRowError).where(
                ImportRowError.tenant_id == int(tenant_id),
                ImportRowError.import_job_id == int(job_id),
                ImportRowError.id > last_id,
                ImportRowError.is_deleted.is_(False),
            ).order_by(ImportRowError.id).limit(STAGING_CHUNK_SIZE)).all())
            if not errors:
                break
            row_nos = {int(item.row_no) for item in errors if item.row_no}
            staged = list(db.scalars(select(IdentityImportStagingRow).where(
                IdentityImportStagingRow.tenant_id == int(tenant_id),
                IdentityImportStagingRow.import_job_id == int(job_id),
                IdentityImportStagingRow.row_no.in_(row_nos),
                IdentityImportStagingRow.is_deleted.is_(False),
            )).all()) if row_nos else []
            by_row = {int(row.row_no): row for row in staged}
            for item in errors:
                row = by_row.get(int(item.row_no or 0))
                payload = dict(row.payload_json or {}) if row else {}
                entity = str(row.entity_type if row else (item.raw_snapshot_json or {}).get("entity") or "").upper()
                account_no = payload.get("studentNo") or payload.get("loginName") or ""
                ws.append([
                    int(item.row_no or 0) or "全局",
                    entity,
                    account_no,
                    payload.get("name") or "",
                    (item.raw_snapshot_json or {}).get("entity") or "",
                    item.field_code or "",
                    item.error_message,
                ])
            last_id = int(errors[-1].id)
            db.expunge_all()
    finally:
        db.close()
    buffer = io.BytesIO()
    wb.save(buffer)
    wb.close()
    return buffer.getvalue()

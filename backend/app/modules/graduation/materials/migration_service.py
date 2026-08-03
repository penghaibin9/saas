"""Explicit, resumable migration of legacy graduation attachment arrays.

The mapper only converts record types whose meaning is unambiguous.  It never
uses attachment order or numeric suffixes to invent material semantics.
"""
from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import GraduationFinal, GraduationGuidance, GraduationProposal, GraduationStudent, GraduationTopic
from app.models.graduation_material import GraduationMaterialBackfillCheckpoint
from app.services.db_service import _tid, session
from app.services.message_identity import resolve_message_user_id

from .command_service import adopt_legacy_file_in_session


MIGRATION_KEY = "GRADUATION_MATERIAL_DOMAIN_CLOSEOUT_V2"
_MODELS = {
    "PROPOSAL": GraduationProposal,
    "FINAL": GraduationFinal,
    "GUIDANCE": GraduationGuidance,
    "TOPIC": GraduationTopic,
}


def _actor_id(user: dict) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _file_ids(value) -> list[int]:
    result: list[int] = []
    for raw in value or []:
        candidate = raw.get("fileId") if isinstance(raw, dict) else raw
        if str(candidate or "").isdigit() and int(candidate) not in result:
            result.append(int(candidate))
    return result


def _students(db, model_name: str, record) -> list[GraduationStudent]:
    if model_name in {"PROPOSAL", "FINAL", "GUIDANCE"}:
        row = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(record.gd_student_id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        )).first()
        return [row] if row else []
    return list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id == int(record.id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.id)).all())


def _mapping(model_name: str, record, file_ids: list[int]) -> list[dict]:
    if not file_ids:
        return []
    if model_name == "PROPOSAL" and len(file_ids) == 1:
        return [{"fileId": file_ids[0], "materialCode": "PROPOSAL_REPORT", "confidence": "HIGH",
                 "reason": "开题记录唯一附件可由业务记录类型确定", "manualReview": False}]
    if model_name == "FINAL" and len(file_ids) == 1:
        code = "THESIS_FINAL" if str(record.final_type or "") == "定稿" else "THESIS_DRAFT"
        return [{"fileId": file_ids[0], "materialCode": code, "confidence": "HIGH",
                 "reason": f"成果记录类型={record.final_type or '初稿'}且仅有一个主文件", "manualReview": False}]
    reason = (
        "同一业务记录存在多个附件，原数据没有材料语义，禁止按附件序号猜测"
        if len(file_ids) > 1 else
        f"{model_name} 历史附件无法无歧义映射到单一规则材料代码"
    )
    return [{"fileId": file_id, "materialCode": None, "confidence": "LOW",
             "reason": reason, "manualReview": True} for file_id in file_ids]


def _xlsx(rows: list[dict]) -> dict:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("历史附件迁移差异")
    columns = [
        "sourceRecordType", "sourceRecordId", "gdStudentId", "attachmentIndex", "fileId",
        "targetMaterialCode", "mappingReason", "confidence", "manualReview", "status", "error",
    ]
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column, "") for column in columns])
    stream = BytesIO()
    workbook.save(stream)
    return {
        "fileName": f"graduation-material-migration-diff-{datetime.utcnow():%Y%m%d%H%M%S}.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "base64": base64.b64encode(stream.getvalue()).decode("ascii"),
    }


def backfill_legacy(
    user: dict,
    *,
    page_size: int = 200,
    cursor_model: str = "PROPOSAL",
    cursor_id: int | None = None,
    dry_run: bool = False,
    retry: bool = False,
    output_format: str = "JSON",
) -> dict:
    model_name = str(cursor_model or "PROPOSAL").upper()
    model = _MODELS.get(model_name)
    if not model:
        raise AppException("VALIDATION_ERROR", "cursorModel 仅支持 PROPOSAL/FINAL/GUIDANCE/TOPIC")
    size = min(1000, max(1, int(page_size or 200)))
    fmt = str(output_format or "JSON").upper()
    if fmt not in {"JSON", "XLSX"}:
        raise AppException("VALIDATION_ERROR", "outputFormat 仅支持 JSON/XLSX")
    with session() as db:
        checkpoint = db.scalars(select(GraduationMaterialBackfillCheckpoint).where(
            GraduationMaterialBackfillCheckpoint.tenant_id == _tid(),
            GraduationMaterialBackfillCheckpoint.migration_key == MIGRATION_KEY,
            GraduationMaterialBackfillCheckpoint.is_deleted.is_(False),
        ).with_for_update()).first() if not dry_run else None
        start = max(0, int(cursor_id if cursor_id is not None else (
            0 if retry else checkpoint.cursor_id if checkpoint and checkpoint.cursor_model == model_name else 0
        )))
        records = list(db.scalars(select(model).where(
            model.tenant_id == _tid(), model.id > start, model.is_deleted.is_(False),
        ).order_by(model.id).limit(size)).all())
        if not dry_run and not checkpoint:
            checkpoint = GraduationMaterialBackfillCheckpoint(
                tenant_id=_tid(), migration_key=MIGRATION_KEY, status="PENDING", dry_run=False,
                cursor_model=model_name, cursor_id=start, page_size=size, created_by=_actor_id(user),
            )
            db.add(checkpoint)
            db.flush()
        differences: list[dict] = []
        converted = skipped = failed = manual = 0
        for record in records:
            ids = _file_ids(getattr(record, "attachments_json", None))
            mappings = _mapping(model_name, record, ids)
            students = _students(db, model_name, record)
            if not students and ids:
                mappings = [{**item, "manualReview": True, "confidence": "LOW",
                             "reason": "未找到有效毕业设计学生"} for item in mappings]
            for student in students or [None]:
                for index, item in enumerate(mappings, start=1):
                    diff = {
                        "sourceRecordType": model_name, "sourceRecordId": str(record.id),
                        "gdStudentId": str(student.id) if student else "", "attachmentIndex": index,
                        "fileId": str(item["fileId"]), "targetMaterialCode": item["materialCode"],
                        "mappingReason": item["reason"], "confidence": item["confidence"],
                        "manualReview": bool(item["manualReview"]), "status": "MANUAL_REVIEW", "error": "",
                    }
                    if item["manualReview"] or not student:
                        manual += 1
                    elif dry_run:
                        diff["status"] = "WOULD_CONVERT"
                        converted += 1
                    else:
                        try:
                            with db.begin_nested():
                                outcome = adopt_legacy_file_in_session(
                                    db, student, str(item["materialCode"]), int(item["fileId"]),
                                    source_record_type=model_name, source_record_id=str(record.id), user=user,
                                    approved=str(record.status or "").upper() == "APPROVED",
                                    binding_metadata={
                                        "legacyAttachmentIndex": index, "mappingReason": item["reason"],
                                        "mappingConfidence": item["confidence"], "manualReview": False,
                                    },
                                )
                            diff["status"] = outcome["status"]
                            if outcome["status"] == "CONVERTED": converted += 1
                            else: skipped += 1
                        except Exception as exc:
                            failed += 1
                            diff["status"] = "FAILED"
                            diff["error"] = str(exc)[:500]
                    differences.append(diff)
            if not mappings:
                skipped += 1
            if checkpoint:
                checkpoint.cursor_id = int(record.id)
        has_more = len(records) == size
        if checkpoint:
            checkpoint.status = "PARTIAL_FAILED" if failed else ("RUNNING" if has_more else "COMPLETED")
            checkpoint.cursor_model = model_name
            checkpoint.page_size = size
            checkpoint.scanned_rows = int(checkpoint.scanned_rows or 0) + len(records)
            checkpoint.converted_rows = int(checkpoint.converted_rows or 0) + converted
            checkpoint.skipped_rows = int(checkpoint.skipped_rows or 0) + skipped
            checkpoint.failed_rows = int(checkpoint.failed_rows or 0) + failed
            checkpoint.diff_report_json = {"lastPage": differences[-100:], "manualReview": manual}
            checkpoint.started_at = checkpoint.started_at or datetime.utcnow()
            checkpoint.finished_at = None if has_more else datetime.utcnow()
            db.commit()
        result = {
            "migrationKey": MIGRATION_KEY, "cursorModel": model_name,
            "nextCursorId": int(records[-1].id) if records else start, "pageSize": size,
            "dryRun": bool(dry_run), "retry": bool(retry), "scanned": len(records),
            "converted": converted, "skipped": skipped, "failed": failed,
            "manualReview": manual, "hasMore": has_more,
            "status": "DRY_RUN" if dry_run else checkpoint.status, "differences": differences,
        }
        if fmt == "XLSX":
            result["differenceReport"] = _xlsx(differences)
        return result


__all__ = ["backfill_legacy"]

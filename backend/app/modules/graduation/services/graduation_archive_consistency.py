"""毕业设计归档的真实文件证据、批次规则和预览执行一致性。

- manifest 纳入任务书正文哈希、学生确认哈希、开题/定稿附件 FileObject.sha256；
- 归档必备项可由 batch.rules_config.archive.requiredItems 配置；
- 批量预览返回签名 previewToken，执行时在同一事务锁定并重算快照，变化即 409。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.models import (
    FileObject,
    GraduationArchiveRecord,
    GraduationBatch,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationGrade,
    GraduationMidterm,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTaskBook,
    PortalSignRecord,
)
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, can_access_student
from app.services.db_service import _iso, _tid, session

_INSTALLED = False
_ORIGINAL_CHECK = None
_DEFAULT_REQUIRED = ["taskbook", "proposal", "midterm", "final", "review", "defenseScore", "grade"]


def _json_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _batch_rules(db, student: GraduationStudent) -> dict:
    batch = db.get(GraduationBatch, student.batch_id) if student.batch_id else None
    rules = (batch.rules_config or {}) if batch else {}
    archive = rules.get("archive") if isinstance(rules, dict) else None
    return archive if isinstance(archive, dict) else {}


def _required_items(db, student: GraduationStudent) -> list[str]:
    configured = _batch_rules(db, student).get("requiredItems")
    if not isinstance(configured, list) or not configured:
        return list(_DEFAULT_REQUIRED)
    allowed = set(_DEFAULT_REQUIRED)
    values = [str(item) for item in configured if str(item) in allowed]
    return values or list(_DEFAULT_REQUIRED)


def _file_evidence(db, file_ids) -> tuple[list[dict], list[str]]:
    normalized = []
    for raw in file_ids or []:
        value = raw.get("fileId") or raw.get("id") if isinstance(raw, dict) else raw
        if value not in (None, ""):
            try:
                fid = int(value)
            except (TypeError, ValueError):
                continue
            if fid not in normalized:
                normalized.append(fid)
    if not normalized:
        return [], []
    rows = {row.id: row for row in db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id.in_(normalized),
        FileObject.is_deleted.is_(False),
    )).all()}
    evidence, errors = [], []
    for fid in normalized:
        row = rows.get(fid)
        if not row:
            errors.append(f"文件#{fid}不存在或已删除")
            continue
        if row.status not in ("AVAILABLE", "STORED"):
            errors.append(f"文件#{fid}状态为{row.status}，不可归档")
        if not row.sha256 or len(row.sha256) != 64:
            errors.append(f"文件#{fid}缺少SHA-256")
        evidence.append({
            "fileId": str(row.id), "name": row.file_name, "size": row.size_bytes,
            "sha256": row.sha256, "status": row.status, "mime": row.mime_type,
        })
    return evidence, errors


def manifest_payload(db, student: GraduationStudent, archive_batch_no: str) -> dict:
    taskbook = db.scalars(select(GraduationTaskBook).where(
        GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == student.id,
        GraduationTaskBook.is_deleted.is_(False),
    ).order_by(GraduationTaskBook.id.desc())).first()
    proposal = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == student.id,
        GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False),
    ).order_by(GraduationProposal.id.desc())).first()
    final = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
        GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.id.desc())).first()
    midterm = db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == student.id,
        GraduationMidterm.is_deleted.is_(False),
    ).order_by(GraduationMidterm.id.desc())).first()
    reviews = db.scalars(select(GraduationReview).where(
        GraduationReview.tenant_id == _tid(), GraduationReview.gd_student_id == student.id,
        GraduationReview.gd_final_id == (final.id if final else -1),
        GraduationReview.is_deleted.is_(False),
    ).order_by(GraduationReview.id)).all()
    scores = db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == student.id,
        GraduationDefenseScore.is_deleted.is_(False),
    ).order_by(GraduationDefenseScore.round_no, GraduationDefenseScore.id)).all()
    grade = db.scalars(select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == student.id,
        GraduationGrade.is_deleted.is_(False),
    )).first()

    proposal_files, proposal_errors = _file_evidence(db, proposal.attachments_json if proposal else [])
    final_files, final_errors = _file_evidence(db, final.attachments_json if final else [])
    taskbook_snapshot = None
    sign = None
    if taskbook:
        taskbook_snapshot = {
            "id": str(taskbook.id), "version": int(taskbook.taskbook_version or 1),
            "status": taskbook.status, "objective": taskbook.objective or "",
            "content": taskbook.content or "", "progressPlan": taskbook.progress_plan or "",
            "outcomeRequirement": taskbook.outcome_requirement or "",
            "issuedAt": _iso(taskbook.issued_at), "confirmedAt": _iso(taskbook.confirmed_at),
        }
        sign = db.scalars(select(PortalSignRecord).where(
            PortalSignRecord.tenant_id == _tid(),
            PortalSignRecord.biz_type == "GRADUATION_TASKBOOK",
            PortalSignRecord.biz_id == f"{student.id}:v{int(taskbook.taskbook_version or 1)}",
        ).order_by(PortalSignRecord.id.desc())).first()

    payload = {
        "tenantId": str(_tid()), "gdStudentId": str(student.id),
        "studentMasterId": str(student.student_id or ""),
        "batchId": str(student.batch_id or ""), "archiveBatchNo": archive_batch_no,
        "requiredItems": _required_items(db, student),
        "taskbook": {
            "snapshotHash": _json_hash(taskbook_snapshot) if taskbook_snapshot else None,
            "confirmationHash": sign.content_hash if sign else None,
            "signId": str(sign.id) if sign else None,
        },
        "proposal": {
            "id": str(proposal.id) if proposal else None, "version": proposal.version if proposal else None,
            "status": proposal.status if proposal else None, "files": proposal_files,
        },
        "final": {
            "id": str(final.id) if final else None, "version": final.version if final else None,
            "status": final.status if final else None, "files": final_files,
        },
        "midterm": {
            "id": str(midterm.id) if midterm else None, "status": midterm.status if midterm else None,
        },
        "reviews": [{
            "id": str(row.id), "reviewerMentorId": str(row.reviewer_mentor_id or ""),
            "status": row.status, "score": row.score, "version": row.version,
        } for row in reviews],
        "defenseScores": [{
            "id": str(row.id), "identity": row.judge_identity, "round": row.round_no,
            "status": row.status, "score": row.score, "absent": bool(row.absent), "version": row.version,
        } for row in scores],
        "grade": {
            "id": str(grade.id) if grade else None, "status": grade.status if grade else None,
            "score": grade.total_score if grade else None, "sourceHash": grade.source_snapshot_hash if grade else None,
            "version": grade.version if grade else None,
        },
        "fileErrors": proposal_errors + final_errors,
    }
    payload["manifestHash"] = _json_hash(payload)
    return payload


def _manifest_hash(db, student: GraduationStudent, archive_batch_no: str) -> str:
    payload = manifest_payload(db, student, archive_batch_no)
    if payload["fileErrors"]:
        raise AppException("DATA_CONFLICT", "归档文件证据不完整：" + "；".join(payload["fileErrors"][:5]))
    if not payload["final"]["files"]:
        raise AppException("DATA_CONFLICT", "正式定稿没有可核验的文件证据，不能备案")
    if not payload["taskbook"]["confirmationHash"]:
        raise AppException("DATA_CONFLICT", "任务书缺少学生本人确认哈希，不能备案")
    return payload["manifestHash"]


def _rule_check(db, student: GraduationStudent):
    checklist, _ = _ORIGINAL_CHECK(db, student)
    required = set(_required_items(db, student))
    normalized = []
    for item in checklist:
        row = dict(item)
        row["required"] = row.get("item") in required
        normalized.append(row)
    missing = [row["label"] for row in normalized if row["required"] and not row.get("present")]
    payload = manifest_payload(db, student, "PREVIEW")
    if "taskbook" in required and not payload["taskbook"]["confirmationHash"]:
        missing.append("任务书学生确认哈希")
    if "final" in required:
        if not payload["final"]["files"]:
            missing.append("成果定稿文件")
        missing.extend(payload["fileErrors"])
    return normalized, list(dict.fromkeys(missing))


def _token_payload(mode: str, batch: GraduationBatch, snapshot: dict) -> dict:
    user = get_current_user_ctx() or {}
    return {
        "mode": mode, "tenant": str(_tid()), "batchId": str(batch.id),
        "actor": str(user.get("userId") or ""),
        "scope": {
            "dataScope": user.get("dataScope"), "collegeId": user.get("collegeId"),
            "majorId": user.get("majorId"),
        },
        "snapshotHash": _json_hash(snapshot), "exp": int(time.time()) + 10 * 60,
    }


def _sign_token(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).rstrip(b"=")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def _verify_token(token: str | None, expected: dict) -> None:
    if not token or "." not in token:
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    try:
        encoded, supplied = token.split(".", 1)
        expected_sig = base64.urlsafe_b64encode(hmac.new(
            settings.jwt_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256,
        ).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(supplied, expected_sig):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise AppException("VALIDATION_ERROR", "归档预览凭证无效，请重新预览") from None
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppException("DATA_CONFLICT", "归档预览已过期，请重新预览")
    for key in ("mode", "tenant", "batchId", "actor", "scope", "snapshotHash"):
        if payload.get(key) != expected.get(key):
            raise AppException("DATA_CONFLICT", "归档数据或操作者已变化，请重新预览")


def _snapshot(db, batch: GraduationBatch, mode: str, *, lock: bool = False) -> dict:
    from app.modules.graduation.services import graduation_archive_service as svc
    scope_ids = set(accessible_student_ids(db, _tid(), batch_id=batch.id))
    student_query = select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == batch.id,
        GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.id.in_(scope_ids or [-1]),
    ).order_by(GraduationStudent.id)
    if lock:
        student_query = student_query.with_for_update()
    students = db.scalars(student_query).all()
    result = []
    for student in students:
        if not can_access_student(db, student):
            continue
        archive_query = select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == student.id,
            GraduationArchiveRecord.is_deleted.is_(False),
        )
        if lock:
            archive_query = archive_query.with_for_update()
        archive = db.scalars(archive_query).first()
        if mode == "FILE" and (not archive or archive.status != "SUBMITTED"):
            continue
        checklist, missing = svc._check_completeness(db, student)
        result.append({
            "studentId": str(student.id), "studentVersion": int(student.version or 0),
            "archiveId": str(archive.id) if archive else None,
            "archiveVersion": int(archive.version or 0) if archive else 0,
            "archiveStatus": archive.status if archive else "NOT_GENERATED",
            "missing": missing, "openRisks": svc._count_open_risks(db, student),
            "manifestHash": manifest_payload(db, student, "PREVIEW")["manifestHash"],
        })
    return {"mode": mode, "batchId": str(batch.id), "rows": result}


def _preview(mode: str, batch_id) -> dict:
    from app.modules.graduation.services import graduation_archive_service as svc
    with session() as db:
        batch = svc._require_batch(db, batch_id)
        snapshot = _snapshot(db, batch, mode)
        executable = sum(1 for row in snapshot["rows"] if not row["missing"] and row["openRisks"] == 0
                         and (mode != "GENERATE" or row["archiveStatus"] not in ("SUBMITTED", "FILED")))
        payload = _token_payload(mode, batch, snapshot)
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "candidateCount": len(snapshot["rows"]), "executableCount": executable,
            "skippedCount": len(snapshot["rows"]) - executable,
            "hasAbnormal": executable != len(snapshot["rows"]),
            "snapshotHash": payload["snapshotHash"], "previewToken": _sign_token(payload),
            "expiresInSeconds": 600, "generatedAt": datetime.now(timezone.utc).isoformat(),
        }


def preview_batch_generate(batch_id=None) -> dict:
    return _preview("GENERATE", batch_id)


def preview_batch_file(batch_id=None) -> dict:
    return _preview("FILE", batch_id)


def batch_generate_submit(batch_id=None, preview_token: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_archive_service as svc
    with session() as db:
        batch = svc._require_batch(db, batch_id)
        snapshot = _snapshot(db, batch, "GENERATE", lock=True)
        _verify_token(preview_token, _token_payload("GENERATE", batch, snapshot))
        submitted = skipped = 0
        for snap in snapshot["rows"]:
            student = db.get(GraduationStudent, int(snap["studentId"]))
            archive = svc._get_or_create(db, student, for_update=True)
            if archive.status in ("FILED", "SUBMITTED"):
                skipped += 1
                continue
            checklist, missing = svc._check_completeness(db, student)
            archive.checklist_json, archive.missing_items = checklist, missing
            archive.generated_at = datetime.now(timezone.utc)
            if missing or svc._count_open_risks(db, student) > 0:
                archive.status = "PENDING_SUBMIT"
                skipped += 1
            else:
                archive.status = "SUBMITTED"
                archive.submitted_at = datetime.now(timezone.utc)
                submitted += 1
            archive.version = int(archive.version or 0) + 1
        svc._audit(db, f"batch-gen-{batch.id}", "批量生成并提交归档",
                   detail=f"batchId={batch.id};submitted={submitted};skipped={skipped};preview={_json_hash(snapshot)}")
        db.commit()
        return {"submitted": submitted, "skipped": skipped, "batchId": str(batch.id),
                "batchName": batch.batch_name}


def batch_file(archive_batch_no: str | None = None, batch_id=None, preview_token: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_archive_service as svc
    with session() as db:
        batch = svc._require_batch(db, batch_id)
        snapshot = _snapshot(db, batch, "FILE", lock=True)
        _verify_token(preview_token, _token_payload("FILE", batch, snapshot))
        operator, _ = svc._op()
        archive_no = archive_batch_no or f"GDARCH-{datetime.now():%Y%m%d}"
        filed = skipped = 0
        for snap in snapshot["rows"]:
            student = db.get(GraduationStudent, int(snap["studentId"]))
            archive = db.get(GraduationArchiveRecord, int(snap["archiveId"]))
            if not student or not archive or archive.status != "SUBMITTED":
                skipped += 1
                continue
            checklist, missing = svc._check_completeness(db, student)
            if missing or svc._count_open_risks(db, student) > 0:
                skipped += 1
                continue
            archive.checklist_json, archive.missing_items = checklist, missing
            archive.status = "FILED"
            archive.verified_by = operator
            archive.filed_at = datetime.now(timezone.utc)
            archive.archive_batch_no = archive_no
            archive.manifest_hash = svc._manifest_hash(db, student, archive_no)
            archive.version = int(archive.version or 0) + 1
            if student.stage != "ARCHIVED":
                student.stage = "ARCHIVED"
                student.version = int(student.version or 0) + 1
            svc._audit(db, archive.id, "批量核验归档",
                       detail=f"batchId={batch.id};archiveBatchNo={archive_no};manifest={archive.manifest_hash}")
            filed += 1
        svc._audit(db, f"batch-file-{batch.id}", "批量核验归档汇总",
                   detail=f"filed={filed};skipped={skipped};preview={_json_hash(snapshot)}")
        db.commit()
        return {"filed": filed, "skipped": skipped, "archiveBatchNo": archive_no,
                "batchId": str(batch.id), "batchName": batch.batch_name}


def install_archive_consistency() -> None:
    global _INSTALLED, _ORIGINAL_CHECK
    if _INSTALLED:
        return
    _INSTALLED = True
    from app.modules.graduation.services import graduation_archive_service as svc
    _ORIGINAL_CHECK = svc._check_completeness
    svc._check_completeness = _rule_check
    svc._manifest_hash = _manifest_hash
    svc.preview_batch_generate = preview_batch_generate
    svc.preview_batch_file = preview_batch_file
    svc.batch_generate_submit = batch_generate_submit
    svc.batch_file = batch_file

"""Production-scale graduation archive batch snapshot.

The public archive batch commands must inspect the same tenant/batch/dataScope truth as
single-row commands without materializing the full tenant into Python or issuing N queries
per student. This module builds the signed preview snapshot with a bounded set of SQL
queries and locks the same evidence rows when the snapshot is revalidated for execution.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import (
    FileObject,
    GraduationArchiveRecord,
    GraduationDefenseScore,
    GraduationFinal,
    GraduationGrade,
    GraduationMidterm,
    GraduationProposal,
    GraduationReview,
    GraduationRiskCase,
    GraduationStudent,
    GraduationTaskBook,
    PortalSignRecord,
)
from app.modules.graduation.services.graduation_archive_data_quality import (
    identity_anomaly_reasons,
    readonly_missing_markers,
)
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _iso, _tid, session

_DEFAULT_REQUIRED = ["taskbook", "proposal", "midterm", "final", "review", "defenseScore", "grade"]
_CHECKLIST_ITEMS = [
    ("taskbook", "任务书（已确认）"),
    ("proposal", "开题报告（已通过）"),
    ("midterm", "中期检查（已通过）"),
    ("final", "成果定稿（已通过）"),
    ("review", "教师评阅（已完成）"),
    ("defenseScore", "答辩评分（已确认）"),
    ("grade", "成绩（已发布）"),
]


def _json_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _locked(stmt, lock: bool):
    return stmt.with_for_update() if lock else stmt


def _rows(db, stmt, *, lock: bool):
    return list(db.scalars(_locked(stmt, lock)).all())


def _group(rows) -> dict[int, list]:
    grouped: dict[int, list] = defaultdict(list)
    for row in rows:
        grouped[int(row.gd_student_id)].append(row)
    return grouped


def _latest(rows):
    return max(rows or [], key=lambda row: int(row.id or 0), default=None)


def _required_items(batch) -> list[str]:
    rules = (batch.rules_config or {}) if isinstance(batch.rules_config, dict) else {}
    archive = rules.get("archive") if isinstance(rules, dict) else None
    configured = archive.get("requiredItems") if isinstance(archive, dict) else None
    if not isinstance(configured, list) or not configured:
        return list(_DEFAULT_REQUIRED)
    allowed = set(_DEFAULT_REQUIRED)
    values = [str(item) for item in configured if str(item) in allowed]
    return values or list(_DEFAULT_REQUIRED)


def _attachment_ids(value) -> list[int]:
    ids: list[int] = []
    for raw in value or []:
        candidate = (raw.get("fileId") or raw.get("id")) if isinstance(raw, dict) else raw
        if candidate in (None, ""):
            continue
        try:
            fid = int(candidate)
        except (TypeError, ValueError):
            continue
        if fid not in ids:
            ids.append(fid)
    return ids


def _file_evidence(file_ids: list[int], file_map: dict[int, FileObject]) -> tuple[list[dict], list[str]]:
    evidence: list[dict] = []
    errors: list[str] = []
    for fid in file_ids:
        row = file_map.get(int(fid))
        if not row:
            errors.append(f"文件#{fid}不存在或已删除")
            continue
        if row.status not in ("AVAILABLE", "STORED"):
            errors.append(f"文件#{fid}状态为{row.status}，不可归档")
        if not row.sha256 or len(str(row.sha256)) != 64:
            errors.append(f"文件#{fid}缺少SHA-256")
        evidence.append({
            "fileId": str(row.id),
            "name": row.file_name,
            "size": row.size_bytes,
            "sha256": row.sha256,
            "status": row.status,
            "mime": row.mime_type,
        })
    return evidence, errors


def row_block_reasons(row: dict, mode: str) -> list[str]:
    """Single executable truth shared by preview and execution."""
    reasons: list[str] = []
    if row.get("dataAnomaly"):
        reasons.append("dirty_data")
    real_missing = [m for m in (row.get("missing") or []) if not str(m).startswith("历史主档异常：")]
    if real_missing:
        reasons.append("missing_materials")
    if int(row.get("openRisks") or 0) > 0:
        reasons.append("open_risks")
    if mode == "GENERATE" and row.get("archiveStatus") in ("SUBMITTED", "FILED"):
        reasons.append("already_submitted")
    return reasons


def build_snapshot(db, batch, mode: str, *, lock: bool = False) -> dict:
    """Build one signed batch snapshot with constant-query bulk prefetch."""
    tid = _tid()
    scope = student_scope_select(db, tid, batch_id=batch.id)
    student_stmt = select(GraduationStudent).where(
        GraduationStudent.tenant_id == tid,
        GraduationStudent.batch_id == batch.id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.id.in_(scope),
    ).order_by(GraduationStudent.id)
    students = _rows(db, student_stmt, lock=lock)
    ids = [int(student.id) for student in students]
    if not ids:
        return {"mode": mode, "batchId": str(batch.id), "rows": []}

    archive_rows = _rows(db, select(GraduationArchiveRecord).where(
        GraduationArchiveRecord.tenant_id == tid,
        GraduationArchiveRecord.gd_student_id.in_(ids),
        GraduationArchiveRecord.is_deleted.is_(False),
    ).order_by(GraduationArchiveRecord.gd_student_id, GraduationArchiveRecord.id), lock=lock)
    archives = {int(row.gd_student_id): row for row in archive_rows}

    taskbooks = _group(_rows(db, select(GraduationTaskBook).where(
        GraduationTaskBook.tenant_id == tid,
        GraduationTaskBook.gd_student_id.in_(ids),
        GraduationTaskBook.is_deleted.is_(False),
    ).order_by(GraduationTaskBook.gd_student_id, GraduationTaskBook.id), lock=lock))
    proposals = _group(_rows(db, select(GraduationProposal).where(
        GraduationProposal.tenant_id == tid,
        GraduationProposal.gd_student_id.in_(ids),
        GraduationProposal.is_deleted.is_(False),
    ).order_by(GraduationProposal.gd_student_id, GraduationProposal.id), lock=lock))
    finals = _group(_rows(db, select(GraduationFinal).where(
        GraduationFinal.tenant_id == tid,
        GraduationFinal.gd_student_id.in_(ids),
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.gd_student_id, GraduationFinal.id), lock=lock))
    midterms = _group(_rows(db, select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == tid,
        GraduationMidterm.gd_student_id.in_(ids),
    ).order_by(GraduationMidterm.gd_student_id, GraduationMidterm.id), lock=lock))
    reviews = _group(_rows(db, select(GraduationReview).where(
        GraduationReview.tenant_id == tid,
        GraduationReview.gd_student_id.in_(ids),
        GraduationReview.is_deleted.is_(False),
    ).order_by(GraduationReview.gd_student_id, GraduationReview.id), lock=lock))
    scores = _group(_rows(db, select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == tid,
        GraduationDefenseScore.gd_student_id.in_(ids),
        GraduationDefenseScore.is_deleted.is_(False),
    ).order_by(GraduationDefenseScore.gd_student_id, GraduationDefenseScore.round_no, GraduationDefenseScore.id), lock=lock))
    grades = _group(_rows(db, select(GraduationGrade).where(
        GraduationGrade.tenant_id == tid,
        GraduationGrade.gd_student_id.in_(ids),
        GraduationGrade.is_deleted.is_(False),
    ).order_by(GraduationGrade.gd_student_id, GraduationGrade.id), lock=lock))
    risk_rows = _rows(db, select(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == tid,
        GraduationRiskCase.gd_student_id.in_(ids),
        GraduationRiskCase.is_deleted.is_(False),
        GraduationRiskCase.status.in_(("OPEN", "PROCESSING")),
    ).order_by(GraduationRiskCase.gd_student_id, GraduationRiskCase.id), lock=lock)
    risk_counts: dict[int, int] = defaultdict(int)
    for risk in risk_rows:
        risk_counts[int(risk.gd_student_id)] += 1

    selected_taskbooks = {sid: _latest(rows) for sid, rows in taskbooks.items()}
    selected_proposals = {
        sid: _latest([row for row in rows if row.status == "APPROVED"])
        for sid, rows in proposals.items()
    }
    selected_finals = {
        sid: _latest([row for row in rows if row.final_type == "定稿" and row.status == "APPROVED"])
        for sid, rows in finals.items()
    }
    selected_midterms = {sid: _latest(rows) for sid, rows in midterms.items()}
    selected_grades = {sid: _latest(rows) for sid, rows in grades.items()}

    all_file_ids: list[int] = []
    for record in [*selected_proposals.values(), *selected_finals.values()]:
        if record:
            for fid in _attachment_ids(record.attachments_json):
                if fid not in all_file_ids:
                    all_file_ids.append(fid)
    file_rows = _rows(db, select(FileObject).where(
        FileObject.tenant_id == tid,
        FileObject.id.in_(all_file_ids or [-1]),
        FileObject.is_deleted.is_(False),
    ).order_by(FileObject.id), lock=lock) if all_file_ids else []
    file_map = {int(row.id): row for row in file_rows}

    sign_ids = [
        f"{sid}:v{int(taskbook.taskbook_version or 1)}"
        for sid, taskbook in selected_taskbooks.items() if taskbook is not None
    ]
    sign_rows = _rows(db, select(PortalSignRecord).where(
        PortalSignRecord.tenant_id == tid,
        PortalSignRecord.biz_type == "GRADUATION_TASKBOOK",
        PortalSignRecord.biz_id.in_(sign_ids or ["__none__"]),
    ).order_by(PortalSignRecord.biz_id, PortalSignRecord.id), lock=lock) if sign_ids else []
    signs: dict[str, PortalSignRecord] = {}
    for sign in sign_rows:
        current = signs.get(str(sign.biz_id))
        if current is None or int(sign.id) > int(current.id):
            signs[str(sign.biz_id)] = sign

    required_list = _required_items(batch)
    required = set(required_list)
    result: list[dict] = []
    for student in students:
        sid = int(student.id)
        archive = archives.get(sid)
        if mode == "FILE" and (not archive or archive.status != "SUBMITTED"):
            continue

        tb = selected_taskbooks.get(sid)
        proposal = selected_proposals.get(sid)
        final = selected_finals.get(sid)
        midterm = selected_midterms.get(sid)
        grade = selected_grades.get(sid)
        student_reviews = reviews.get(sid, [])
        final_reviews = [row for row in student_reviews if final and row.gd_final_id == final.id]
        student_scores = scores.get(sid, [])
        sign_key = f"{sid}:v{int(tb.taskbook_version or 1)}" if tb else ""
        sign = signs.get(sign_key)
        proposal_files, proposal_errors = _file_evidence(
            _attachment_ids(proposal.attachments_json) if proposal else [], file_map
        )
        final_files, final_errors = _file_evidence(
            _attachment_ids(final.attachments_json) if final else [], file_map
        )

        present = {
            "taskbook": bool(tb and tb.status == "CONFIRMED"),
            "proposal": bool(proposal),
            "midterm": bool(midterm and midterm.status in ("CHECKED_PASS", "RECTIFIED_PASS")),
            "final": bool(final),
            "review": any(row.status == "COMPLETED" for row in final_reviews),
            "defenseScore": any(row.status == "CONFIRMED" for row in student_scores),
            "grade": bool(grade and grade.status == "PUBLISHED"),
        }
        checklist = [
            {"item": key, "label": label, "present": present[key], "required": key in required}
            for key, label in _CHECKLIST_ITEMS
        ]
        missing = [row["label"] for row in checklist if row["required"] and not row["present"]]
        if "taskbook" in required and not (sign and sign.content_hash):
            missing.append("任务书学生确认哈希")
        if "final" in required:
            if not final_files:
                missing.append("成果定稿文件")
            missing.extend(proposal_errors + final_errors)

        taskbook_snapshot = None
        if tb:
            taskbook_snapshot = {
                "id": str(tb.id), "version": int(tb.taskbook_version or 1),
                "status": tb.status, "objective": tb.objective or "", "content": tb.content or "",
                "progressPlan": tb.progress_plan or "", "outcomeRequirement": tb.outcome_requirement or "",
                "issuedAt": _iso(tb.issued_at), "confirmedAt": _iso(tb.confirmed_at),
            }
        manifest = {
            "tenantId": str(tid), "gdStudentId": str(sid),
            "studentMasterId": str(student.student_id or ""),
            "batchId": str(student.batch_id or ""), "archiveBatchNo": "PREVIEW",
            "requiredItems": list(required_list),
            "taskbook": {
                "snapshotHash": _json_hash(taskbook_snapshot) if taskbook_snapshot else None,
                "confirmationHash": sign.content_hash if sign else None,
                "signId": str(sign.id) if sign else None,
            },
            "proposal": {
                "id": str(proposal.id) if proposal else None,
                "version": proposal.version if proposal else None,
                "status": proposal.status if proposal else None,
                "files": proposal_files,
            },
            "final": {
                "id": str(final.id) if final else None,
                "version": final.version if final else None,
                "status": final.status if final else None,
                "files": final_files,
            },
            "midterm": {"id": str(midterm.id) if midterm else None, "status": midterm.status if midterm else None},
            "reviews": [{
                "id": str(row.id), "reviewerMentorId": str(row.reviewer_mentor_id or ""),
                "status": row.status, "score": row.score, "version": row.version,
            } for row in final_reviews],
            "defenseScores": [{
                "id": str(row.id), "identity": row.judge_identity, "round": row.round_no,
                "status": row.status, "score": row.score, "absent": bool(row.absent), "version": row.version,
            } for row in student_scores],
            "grade": {
                "id": str(grade.id) if grade else None, "status": grade.status if grade else None,
                "score": grade.total_score if grade else None,
                "sourceHash": grade.source_snapshot_hash if grade else None,
                "version": grade.version if grade else None,
            },
            "fileErrors": proposal_errors + final_errors,
        }
        manifest["manifestHash"] = _json_hash(manifest)
        anomaly_reasons = identity_anomaly_reasons(student)
        readonly_markers = readonly_missing_markers(student)
        result.append({
            "studentId": str(sid), "studentVersion": int(student.version or 0),
            "archiveId": str(archive.id) if archive else None,
            "archiveVersion": int(archive.version or 0) if archive else 0,
            "archiveStatus": archive.status if archive else "NOT_GENERATED",
            "checklist": checklist,
            "missing": list(dict.fromkeys([*missing, *readonly_markers])),
            "dataAnomaly": bool(anomaly_reasons), "anomalyReasons": anomaly_reasons,
            "openRisks": int(risk_counts.get(sid, 0)),
            "manifestHash": manifest["manifestHash"],
        })
    return {"mode": mode, "batchId": str(batch.id), "rows": result}


def preview_batch_generate(batch_id=None) -> dict:
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as service

    with session() as db:
        batch = service._require_batch(db, batch_id)
        snapshot = build_snapshot(db, batch, "GENERATE")
        skip_reasons: dict[str, int] = {}
        executable = 0
        for row in snapshot["rows"]:
            reasons = row_block_reasons(row, "GENERATE")
            if reasons:
                for reason in reasons:
                    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            else:
                executable += 1
        payload = consistency._token_payload("GENERATE", batch, snapshot)
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "candidateCount": len(snapshot["rows"]), "executableCount": executable,
            "skippedCount": len(snapshot["rows"]) - executable,
            "skipReasons": [{"reason": key, "count": count} for key, count in sorted(skip_reasons.items()) if count],
            "hasAbnormal": executable != len(snapshot["rows"]),
            "snapshotHash": payload["snapshotHash"], "previewToken": consistency._sign_token(payload),
            "expiresInSeconds": 600, "generatedAt": datetime.now(timezone.utc).isoformat(),
        }


def batch_generate_submit(batch_id=None, preview_token: str | None = None) -> dict:
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as service

    with session() as db:
        batch = service._require_batch(db, batch_id)
        snapshot = build_snapshot(db, batch, "GENERATE", lock=True)
        consistency._verify_token(preview_token, consistency._token_payload("GENERATE", batch, snapshot))
        student_ids = [int(row["studentId"]) for row in snapshot["rows"]]
        students = {int(row.id): row for row in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(student_ids or [-1])
        )).all()}
        archive_ids = [int(row["archiveId"]) for row in snapshot["rows"] if row.get("archiveId")]
        archives_by_id = {int(row.id): row for row in db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(), GraduationArchiveRecord.id.in_(archive_ids or [-1])
        )).all()} if archive_ids else {}
        submitted = skipped = dirty_skipped = 0
        now = datetime.now(timezone.utc)
        for snap in snapshot["rows"]:
            reasons = row_block_reasons(snap, "GENERATE")
            if reasons:
                skipped += 1
                if "dirty_data" in reasons:
                    dirty_skipped += 1
                    continue
            student = students.get(int(snap["studentId"]))
            if not student:
                skipped += 1
                continue
            archive = archives_by_id.get(int(snap["archiveId"])) if snap.get("archiveId") else None
            if archive is None:
                archive = GraduationArchiveRecord(
                    tenant_id=_tid(), gd_student_id=student.id, status="NOT_GENERATED",
                )
                db.add(archive)
                db.flush()
                archives_by_id[int(archive.id)] = archive
            if archive.status in ("SUBMITTED", "FILED"):
                continue
            archive.checklist_json = snap.get("checklist") or []
            archive.missing_items = [
                item for item in (snap.get("missing") or []) if not str(item).startswith("历史主档异常：")
            ]
            archive.generated_at = now
            if reasons:
                archive.status = "PENDING_SUBMIT"
            else:
                archive.status = "SUBMITTED"
                archive.submitted_at = now
                submitted += 1
            archive.version = int(archive.version or 0) + 1
        service._audit(
            db, f"batch-gen-{batch.id}", "批量生成并提交归档",
            detail=(f"batchId={batch.id};submitted={submitted};skipped={skipped};"
                    f"dirtySkipped={dirty_skipped};preview={consistency._json_hash(snapshot)}"),
        )
        db.commit()
        return {
            "submitted": submitted, "skipped": skipped, "dirtySkipped": dirty_skipped,
            "batchId": str(batch.id), "batchName": batch.batch_name,
        }

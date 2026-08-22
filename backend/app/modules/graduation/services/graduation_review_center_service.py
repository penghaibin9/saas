"""W7.3 graduation Review Center read projection.

This module is deliberately read-only. Proposal, Final and GraduationReview stay the
only status authorities; Review Center only projects their current state together
with Material/FileVersion/FileObject evidence and append-only review feedback.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, inspect as sa_inspect, select, text

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationFinal,
    GraduationPlagiarismCheck,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTopic,
)
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session
from app.services.file_scan_constants import READY_SCAN_STATES

CASE_TYPES = {"PROPOSAL", "FINAL_DRAFT", "FINAL", "FORMAL_REVIEW"}
STATUS_GROUPS = {"WAITING", "IN_REVIEW", "RETURNED", "DONE", "BLOCKED"}
MATERIAL_CODE = {
    "PROPOSAL": "PROPOSAL_REPORT",
    "FINAL_DRAFT": "THESIS_DRAFT",
    "FINAL": "THESIS_FINAL",
    "FORMAL_REVIEW": "THESIS_FINAL",
}
FEEDBACK_STAGE = {
    "PROPOSAL": "PROPOSAL",
    "FINAL_DRAFT": "FINAL",
    "FINAL": "FINAL",
    "FORMAL_REVIEW": "FORMAL",
}
STATUS_LABELS = {
    "PENDING_REVIEW": "待审核",
    "APPROVED": "已通过",
    "REJECTED": "已退回",
    "ASSIGNED": "待评阅",
    "REVIEWING": "评阅中",
    "COMPLETED": "已完成",
    "RETURNED": "已退回重评",
}
SORTS = {"LATEST", "EARLIEST", "STUDENT_NO", "STATUS"}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_value(value: Any, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return default
    return default


def _blocking(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _file_ready(row: FileObject | None) -> bool:
    if not row or row.is_deleted or str(row.status or "").upper() != "AVAILABLE":
        return False
    return str(row.scan_status or "").upper() in READY_SCAN_STATES


def _status_group(case_type: str, status: str) -> str:
    value = str(status or "").upper()
    if case_type == "FORMAL_REVIEW":
        return {
            "ASSIGNED": "WAITING",
            "REVIEWING": "IN_REVIEW",
            "RETURNED": "RETURNED",
            "COMPLETED": "DONE",
        }.get(value, "BLOCKED")
    return {
        "PENDING_REVIEW": "WAITING",
        "REJECTED": "RETURNED",
        "APPROVED": "DONE",
    }.get(value, "BLOCKED")


def _feedback_table_available(db) -> bool:
    try:
        inspector = sa_inspect(db.bind)
        return bool(inspector.has_table("t_gd_review_feedback"))
    except Exception:  # noqa: BLE001 - projection must not invent feedback if metadata is unavailable
        return False


def _load_feedback(db, batch_id: int) -> list[dict]:
    """Load W7.2 evidence once per projection; 5000+ rows remain bounded to one batch query."""
    if not _feedback_table_available(db):
        return []
    inspector = sa_inspect(db.bind)
    columns = {str(c["name"]) for c in inspector.get_columns("t_gd_review_feedback")}
    required = {"tenant_id", "stage", "source_record_id", "created_at"}
    if not required.issubset(columns):
        return []
    where = "tenant_id = :tenant_id"
    params: dict[str, Any] = {"tenant_id": int(_tid())}
    if "batch_id" in columns:
        where += " AND batch_id = :batch_id"
        params["batch_id"] = int(batch_id)
    rows = db.execute(text(
        f"SELECT * FROM t_gd_review_feedback WHERE {where} ORDER BY created_at DESC, id DESC"
    ), params).mappings().all()
    return [dict(row) for row in rows]


def _feedback_public(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": str(row.get("id")) if row.get("id") is not None else None,
        "stage": str(row.get("stage") or ""),
        "sourceRecordId": str(row.get("source_record_id") or ""),
        "reviewId": str(row.get("review_id")) if row.get("review_id") is not None else None,
        "materialId": str(row.get("material_id")) if row.get("material_id") is not None else None,
        "fileVersionId": str(row.get("file_version_id")) if row.get("file_version_id") is not None else None,
        "sourceSha256": row.get("source_sha256"),
        "roundNo": int(row.get("round_no") or 0) or None,
        "categories": _json_value(row.get("categories"), []),
        "issues": _json_value(row.get("issues"), []),
        "summary": str(row.get("summary") or ""),
        "result": str(row.get("result") or ""),
        "reviewerUserId": str(row.get("reviewer_user_id")) if row.get("reviewer_user_id") is not None else None,
        "reviewerMentorId": str(row.get("reviewer_mentor_id")) if row.get("reviewer_mentor_id") is not None else None,
        "createdAt": _iso(row.get("created_at")),
        "idempotencyKey": str(row.get("idempotency_key") or "") or None,
        "isSuperseded": bool(row.get("is_superseded")) if row.get("is_superseded") is not None else False,
    }


def _feedback_indexes(rows: list[dict]) -> tuple[dict[tuple[str, str], dict], dict[tuple[str, str], list[dict]]]:
    latest: dict[tuple[str, str], dict] = {}
    history: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (str(row.get("stage") or "").upper(), str(row.get("source_record_id") or ""))
        if not key[0] or not key[1]:
            continue
        latest.setdefault(key, row)  # rows are newest first
        history.setdefault(key, []).append(row)
    for key in history:
        history[key] = list(reversed(history[key]))
    return latest, history


def _formal_snapshots(db, review_ids: list[int]) -> dict[int, dict]:
    """Read W7.1 snapshot columns without creating a second ORM/state authority."""
    if not review_ids:
        return {}
    inspector = sa_inspect(db.bind)
    columns = {str(c["name"]) for c in inspector.get_columns("t_gd_review")}
    wanted = {"material_id", "file_version_id", "source_sha256", "started_at"}
    if not wanted.issubset(columns):
        return {}
    stmt = text(
        "SELECT id, material_id, file_version_id, source_sha256, started_at "
        "FROM t_gd_review WHERE tenant_id = :tenant_id AND id IN :ids AND is_deleted = 0"
    ).bindparams(bindparam("ids", expanding=True))
    rows = db.execute(stmt, {"tenant_id": int(_tid()), "ids": review_ids}).mappings().all()
    return {int(row["id"]): dict(row) for row in rows}


def _record_queries(db, scope_ids: list[int], case_type: str | None = None, record_id: int | None = None):
    proposals: list[GraduationProposal] = []
    finals: list[GraduationFinal] = []
    reviews: list[GraduationReview] = []
    if not scope_ids:
        return proposals, finals, reviews

    if case_type in (None, "PROPOSAL"):
        q = select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(),
            GraduationProposal.gd_student_id.in_(scope_ids),
            GraduationProposal.is_deleted.is_(False),
        )
        if record_id is not None:
            q = q.where(GraduationProposal.id == int(record_id))
        proposals = list(db.scalars(q.order_by(GraduationProposal.id.desc())).all())

    if case_type in (None, "FINAL_DRAFT", "FINAL"):
        q = select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id.in_(scope_ids),
            GraduationFinal.is_deleted.is_(False),
        )
        if case_type == "FINAL_DRAFT":
            q = q.where(GraduationFinal.final_type == "初稿")
        elif case_type == "FINAL":
            q = q.where(GraduationFinal.final_type == "定稿")
        if record_id is not None:
            q = q.where(GraduationFinal.id == int(record_id))
        finals = list(db.scalars(q.order_by(GraduationFinal.id.desc())).all())

    if case_type in (None, "FORMAL_REVIEW"):
        q = select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(),
            GraduationReview.gd_student_id.in_(scope_ids),
            GraduationReview.is_deleted.is_(False),
        )
        if record_id is not None:
            q = q.where(GraduationReview.id == int(record_id))
        reviews = list(db.scalars(q.order_by(GraduationReview.id.desc())).all())
    return proposals, finals, reviews


def _latest_plagiarism(db, final_ids: list[int]) -> dict[int, GraduationPlagiarismCheck]:
    if not final_ids:
        return {}
    rows = db.scalars(select(GraduationPlagiarismCheck).where(
        GraduationPlagiarismCheck.tenant_id == _tid(),
        GraduationPlagiarismCheck.gd_final_id.in_(final_ids),
        GraduationPlagiarismCheck.is_deleted.is_(False),
    ).order_by(GraduationPlagiarismCheck.gd_final_id, GraduationPlagiarismCheck.id.desc())).all()
    result: dict[int, GraduationPlagiarismCheck] = {}
    for row in rows:
        if row.gd_final_id is not None:
            result.setdefault(int(row.gd_final_id), row)
    return result


def _file_descriptor(version: FileVersion | None, file_object: FileObject | None, *, snapshot_sha: str | None = None) -> dict | None:
    if not version:
        return None
    return {
        "fileId": str(file_object.id) if file_object else None,
        "fileVersionId": str(version.id),
        "versionNo": int(version.version_no or 0),
        "fileName": file_object.file_name if file_object else None,
        "mimeType": file_object.mime_type if file_object else None,
        "sizeBytes": int(file_object.size_bytes or 0) if file_object else None,
        "versionStatus": str(version.status or ""),
        "fileStatus": str(file_object.status or "") if file_object else None,
        "scanStatus": str(file_object.scan_status or "") if file_object else None,
        "sourceSha256": snapshot_sha or (str(file_object.sha256 or "") if file_object else None),
        "objectSha256": str(file_object.sha256 or "") if file_object else None,
        "shaMatchesObject": bool(
            not snapshot_sha or (file_object and str(file_object.sha256 or "").lower() == str(snapshot_sha).lower())
        ),
    }


def _allowed_actions(case_type: str, status: str, ready: bool) -> list[str]:
    value = str(status or "").upper()
    if case_type in {"PROPOSAL", "FINAL_DRAFT", "FINAL"}:
        return ["REVIEW"] if value == "PENDING_REVIEW" and ready else []
    if value in {"ASSIGNED", "RETURNED"} and ready:
        return ["START", "SUBMIT"]
    if value == "REVIEWING" and ready:
        return ["SUBMIT"]
    if value == "COMPLETED":
        return ["RETURN"]
    return []


def _project_bundle(
    db,
    batch_id: int,
    *,
    case_type: str | None = None,
    record_id: int | None = None,
) -> tuple[list[dict], dict]:
    scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
    proposals, finals, reviews = _record_queries(db, scope_ids, case_type=case_type, record_id=record_id)
    record_student_ids = {
        int(row.gd_student_id)
        for row in [*proposals, *finals, *reviews]
        if row.gd_student_id is not None
    }
    students = list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.id.in_(record_student_ids or [-1]),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.is_deleted.is_(False),
    )).all())
    student_map = {int(row.id): row for row in students}

    topic_ids = {int(s.topic_id) for s in students if s.topic_id is not None}
    topic_rows = list(db.scalars(select(GraduationTopic).where(
        GraduationTopic.tenant_id == _tid(),
        GraduationTopic.id.in_(topic_ids or [-1]),
        GraduationTopic.is_deleted.is_(False),
    )).all())
    topic_map = {int(row.id): row for row in topic_rows}

    material_rows = list(db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(batch_id),
        GraduationStudentMaterial.gd_student_id.in_(record_student_ids or [-1]),
        GraduationStudentMaterial.material_code.in_(tuple(set(MATERIAL_CODE.values()))),
        GraduationStudentMaterial.is_deleted.is_(False),
    )).all())
    material_map = {(int(row.gd_student_id), str(row.material_code)): row for row in material_rows}
    material_id_map = {int(row.id): row for row in material_rows}

    feedback_rows = _load_feedback(db, int(batch_id))
    feedback_latest, feedback_history = _feedback_indexes(feedback_rows)
    formal_snapshots = _formal_snapshots(db, [int(row.id) for row in reviews])

    version_ids = {
        int(row.current_version_id)
        for row in material_rows
        if row.current_version_id is not None
    }
    for snap in formal_snapshots.values():
        if snap.get("file_version_id") is not None:
            version_ids.add(int(snap["file_version_id"]))
    for feedback in feedback_rows:
        value = feedback.get("file_version_id")
        if value not in (None, "") and str(value).isdigit():
            version_ids.add(int(value))

    versions = list(db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(),
        FileVersion.id.in_(version_ids or [-1]),
        FileVersion.is_deleted.is_(False),
    )).all())
    version_map = {int(row.id): row for row in versions}
    file_object_ids = {int(row.file_object_id) for row in versions if row.file_object_id is not None}
    file_objects = list(db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(),
        FileObject.id.in_(file_object_ids or [-1]),
        FileObject.is_deleted.is_(False),
    )).all())
    file_map = {int(row.id): row for row in file_objects}

    final_ids = {int(row.id) for row in finals}
    final_ids.update(int(row.gd_final_id) for row in reviews if row.gd_final_id is not None)
    plag_map = _latest_plagiarism(db, sorted(final_ids))

    tasks: list[dict] = []

    def build(
        *,
        case: str,
        record,
        student: GraduationStudent,
        status: str,
        submitted_at=None,
        reviewed_at=None,
        assigned_at=None,
        reviewer_name: str | None = None,
        reviewer_mentor_id: int | None = None,
        score: int | None = None,
        gd_final_id: int | None = None,
    ) -> dict:
        topic = topic_map.get(int(student.topic_id)) if student.topic_id is not None else None
        material = material_map.get((int(student.id), MATERIAL_CODE[case]))
        feedback_key = (FEEDBACK_STAGE[case], str(record.id))
        feedback = feedback_latest.get(feedback_key)
        feedback_public = _feedback_public(feedback)
        snapshot = formal_snapshots.get(int(record.id), {}) if case == "FORMAL_REVIEW" else {}

        frozen_material_id = None
        frozen_version_id = None
        snapshot_sha = None
        if feedback:
            if feedback.get("material_id") not in (None, "") and str(feedback.get("material_id")).isdigit():
                frozen_material_id = int(feedback["material_id"])
            if feedback.get("file_version_id") not in (None, "") and str(feedback.get("file_version_id")).isdigit():
                frozen_version_id = int(feedback["file_version_id"])
            snapshot_sha = str(feedback.get("source_sha256") or "") or None
        if case == "FORMAL_REVIEW":
            if snapshot.get("material_id") not in (None, ""):
                frozen_material_id = int(snapshot["material_id"])
            if snapshot.get("file_version_id") not in (None, ""):
                frozen_version_id = int(snapshot["file_version_id"])
            snapshot_sha = str(snapshot.get("source_sha256") or snapshot_sha or "") or None
            if frozen_material_id and frozen_material_id in material_id_map:
                material = material_id_map[frozen_material_id]

        current_version_id = int(material.current_version_id) if material and material.current_version_id else None
        if frozen_version_id is None:
            frozen_version_id = current_version_id
        evidence_version = version_map.get(int(frozen_version_id)) if frozen_version_id else None
        evidence_file = file_map.get(int(evidence_version.file_object_id)) if evidence_version and evidence_version.file_object_id else None
        current_version = version_map.get(int(current_version_id)) if current_version_id else None
        current_file = file_map.get(int(current_version.file_object_id)) if current_version and current_version.file_object_id else None

        blockers: list[dict] = []
        if not material:
            blockers.append(_blocking("MATERIAL_MISSING", "业务记录未绑定权威材料项"))
        if not frozen_version_id:
            blockers.append(_blocking("FILE_VERSION_MISSING", "业务记录缺少可评阅 FileVersion"))
        if frozen_version_id and not evidence_version:
            blockers.append(_blocking("FILE_VERSION_INVALID", "评阅 FileVersion 不存在或不属于当前租户"))
        if evidence_version:
            allowed_version_states = {"APPROVED"} if case == "FORMAL_REVIEW" else {"SUBMITTED", "APPROVED"}
            if str(evidence_version.status or "").upper() not in allowed_version_states:
                blockers.append(_blocking("FILE_VERSION_NOT_REVIEWABLE", "FileVersion 当前状态不可评阅"))
        if evidence_version and not _file_ready(evidence_file):
            blockers.append(_blocking("FILE_NOT_READY", "文件未通过公共文件中心可用性/安全门禁"))
        if snapshot_sha and evidence_file and str(evidence_file.sha256 or "").lower() != snapshot_sha.lower():
            blockers.append(_blocking("SOURCE_SHA_CONFLICT", "冻结 SHA-256 与 FileObject 当前证据不一致"))

        version_conflict = bool(
            frozen_version_id and current_version_id and int(frozen_version_id) != int(current_version_id)
        )
        if case == "FORMAL_REVIEW" and version_conflict and _status_group(case, status) in {"WAITING", "IN_REVIEW"}:
            blockers.append(_blocking("CANONICAL_VERSION_CHANGED", "任务冻结版本与当前 canonical 版本不一致"))
        if case == "FORMAL_REVIEW" and not snapshot and not feedback:
            blockers.append(_blocking("FROZEN_EVIDENCE_MISSING", "正式评阅缺少 W7.1 冻结版本快照"))
        if case == "FORMAL_REVIEW" and not reviewer_mentor_id:
            blockers.append(_blocking("REVIEWER_ID_MISSING", "正式评阅缺少稳定 reviewerMentorId"))

        plag = plag_map.get(int(gd_final_id)) if gd_final_id else None
        if case == "FINAL" and str(status or "").upper() == "PENDING_REVIEW":
            if not plag or str(plag.status or "").upper() != "DONE":
                blockers.append(_blocking("PLAGIARISM_PENDING", "定稿查重尚未完成"))
            elif bool(plag.over_threshold) and str(plag.dispute_status or "").upper() != "APPROVED":
                blockers.append(_blocking("PLAGIARISM_BLOCKED", "查重超标且未通过特例审批"))

        ready = not blockers
        base_group = _status_group(case, status)
        status_group = "BLOCKED" if blockers and base_group in {"WAITING", "IN_REVIEW"} else base_group
        evidence = _file_descriptor(evidence_version, evidence_file, snapshot_sha=snapshot_sha)
        current = _file_descriptor(current_version, current_file)
        sort_at = reviewed_at or getattr(record, "reviewed_at", None) or submitted_at or assigned_at or getattr(record, "created_at", None)

        return {
            "caseKey": f"{case}:{record.id}",
            "caseType": case,
            "recordId": str(record.id),
            "batchId": str(batch_id),
            "gdStudentId": str(student.id),
            "studentId": str(student.student_id) if student.student_id is not None else None,
            "studentNo": student.student_no or "",
            "studentName": student.name or "",
            "classId": student.class_id,
            "className": student.class_name,
            "collegeId": student.college_id,
            "majorId": student.major_id,
            "majorName": getattr(topic, "major_name", None) if topic else None,
            "topicId": str(student.topic_id) if student.topic_id is not None else None,
            "topicTitle": student.topic_title or (topic.title if topic else ""),
            "advisorName": student.advisor_name or (topic.advisor_name if topic else ""),
            "reviewerName": reviewer_name or "",
            "reviewerMentorId": str(reviewer_mentor_id) if reviewer_mentor_id is not None else (
                feedback_public.get("reviewerMentorId") if feedback_public else None
            ),
            "status": str(status or ""),
            "statusLabel": STATUS_LABELS.get(str(status or "").upper(), str(status or "")),
            "statusGroup": status_group,
            "submittedAt": _iso(submitted_at),
            "reviewedAt": _iso(reviewed_at),
            "assignedAt": _iso(assigned_at),
            "startedAt": _iso(snapshot.get("started_at")) if case == "FORMAL_REVIEW" else None,
            "materialId": str(material.id) if material else (str(frozen_material_id) if frozen_material_id else None),
            "fileId": evidence.get("fileId") if evidence else None,
            "fileVersionId": evidence.get("fileVersionId") if evidence else (str(frozen_version_id) if frozen_version_id else None),
            "versionNo": evidence.get("versionNo") if evidence else None,
            "sourceSha256": snapshot_sha or (evidence.get("sourceSha256") if evidence else None),
            "reviewReady": ready,
            "versionConflict": version_conflict,
            "blockingReasons": blockers,
            "score": score,
            "latestFeedback": feedback_public,
            "allowedActions": _allowed_actions(case, status, ready),
            "canonicalFile": current,
            "_sortAt": sort_at,
            "_gdFinalId": gd_final_id,
            "_feedbackKey": feedback_key,
        }

    for row in proposals:
        student = student_map.get(int(row.gd_student_id))
        if student:
            tasks.append(build(
                case="PROPOSAL", record=row, student=student, status=row.status,
                submitted_at=row.submit_at, reviewed_at=row.review_time,
                reviewer_name=row.reviewer,
            ))
    for row in finals:
        student = student_map.get(int(row.gd_student_id))
        if student:
            case = "FINAL" if row.final_type == "定稿" else "FINAL_DRAFT"
            tasks.append(build(
                case=case, record=row, student=student, status=row.status,
                submitted_at=row.submit_at, reviewed_at=row.review_time,
                reviewer_name=row.reviewer, gd_final_id=int(row.id),
            ))
    for row in reviews:
        student = student_map.get(int(row.gd_student_id))
        if student:
            tasks.append(build(
                case="FORMAL_REVIEW", record=row, student=student, status=row.status,
                submitted_at=None, reviewed_at=row.reviewed_at, assigned_at=row.assigned_at,
                reviewer_name=row.reviewer_name, reviewer_mentor_id=row.reviewer_mentor_id,
                score=row.score, gd_final_id=int(row.gd_final_id) if row.gd_final_id else None,
            ))

    return tasks, {
        "studentMap": student_map,
        "materialMap": material_id_map,
        "versionMap": version_map,
        "fileMap": file_map,
        "feedbackHistory": feedback_history,
        "plagiarism": plag_map,
    }


def _public_task(row: dict) -> dict:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _validate_case_type(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().upper()
    if normalized not in CASE_TYPES:
        raise AppException("VALIDATION_ERROR", "caseType 不支持")
    return normalized


def _validate_status_group(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().upper()
    if normalized not in STATUS_GROUPS:
        raise AppException("VALIDATION_ERROR", "statusGroup 不支持")
    return normalized


def _current_reviewer_identity(db) -> tuple[int | None, str]:
    user = get_current_user_ctx() or {}
    name = str(user.get("realName") or "").strip()
    try:
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        return (int(mentor.id), name) if mentor else (None, name)
    except Exception:  # noqa: BLE001 - reviewerOnly fails closed when stable identity is unavailable
        return None, name


def summary(batch_id: int) -> dict:
    with session() as db:
        tasks, _ = _project_bundle(db, int(batch_id))
        groups = {key: 0 for key in sorted(STATUS_GROUPS)}
        case_rows: dict[str, dict] = {
            case: {"caseType": case, "total": 0, **{key: 0 for key in sorted(STATUS_GROUPS)}}
            for case in sorted(CASE_TYPES)
        }
        ready = 0
        for row in tasks:
            group = row["statusGroup"]
            groups[group] = groups.get(group, 0) + 1
            case = row["caseType"]
            case_rows[case]["total"] += 1
            case_rows[case][group] = case_rows[case].get(group, 0) + 1
            if row["reviewReady"]:
                ready += 1
        return {
            "batchId": str(batch_id),
            "total": len(tasks),
            "reviewReadyCount": ready,
            "blockedCount": groups.get("BLOCKED", 0),
            "groups": groups,
            "caseTypes": [case_rows[key] for key in sorted(case_rows)],
        }


def list_tasks(
    *,
    batch_id: int,
    page: int,
    page_size: int,
    case_type: str | None = None,
    status_group: str | None = None,
    keyword: str | None = None,
    reviewer_only: bool = False,
    sort: str | None = None,
) -> tuple[list[dict], int]:
    normalized_case = _validate_case_type(case_type)
    normalized_group = _validate_status_group(status_group)
    sort_key = str(sort or "LATEST").strip().upper()
    if sort_key not in SORTS:
        raise AppException("VALIDATION_ERROR", "sort 不支持")
    with session() as db:
        rows, _ = _project_bundle(db, int(batch_id), case_type=normalized_case)
        if normalized_group:
            rows = [row for row in rows if row["statusGroup"] == normalized_group]
        needle = str(keyword or "").strip().lower()
        if needle:
            rows = [row for row in rows if needle in " ".join((
                str(row.get("studentName") or ""), str(row.get("studentNo") or ""),
                str(row.get("className") or ""), str(row.get("topicTitle") or ""),
            )).lower()]
        if reviewer_only:
            mentor_id, real_name = _current_reviewer_identity(db)
            rows = [row for row in rows if (
                mentor_id is not None and str(row.get("reviewerMentorId") or "") == str(mentor_id)
            ) or (
                not row.get("reviewerMentorId") and real_name and str(row.get("reviewerName") or "") == real_name
            )]

        if sort_key == "LATEST":
            rows.sort(key=lambda row: (row.get("_sortAt") or datetime.min, int(row["recordId"])), reverse=True)
        elif sort_key == "EARLIEST":
            rows.sort(key=lambda row: (row.get("_sortAt") or datetime.min, int(row["recordId"])))
        elif sort_key == "STUDENT_NO":
            rows.sort(key=lambda row: (str(row.get("studentNo") or ""), str(row.get("studentName") or ""), row["caseKey"]))
        else:
            rows.sort(key=lambda row: (row.get("statusGroup") or "", row.get("caseType") or "", row["caseKey"]))

        total = len(rows)
        start = (max(1, int(page)) - 1) * int(page_size)
        page_rows = rows[start:start + int(page_size)]
        return [_public_task(row) for row in page_rows], total


def detail(*, batch_id: int, case_type: str, record_id: int) -> dict:
    normalized_case = _validate_case_type(case_type)
    with session() as db:
        rows, context = _project_bundle(
            db, int(batch_id), case_type=normalized_case, record_id=int(record_id),
        )
        if not rows:
            raise not_found("评阅任务不存在或不在当前数据范围内")
        row = rows[0]
        material = None
        if row.get("materialId") and str(row["materialId"]).isdigit():
            material = context["materialMap"].get(int(row["materialId"]))

        version_history: list[dict] = []
        if material and material.asset_id:
            versions = list(db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(),
                FileVersion.asset_id == int(material.asset_id),
                FileVersion.is_deleted.is_(False),
            ).order_by(FileVersion.version_no.desc(), FileVersion.id.desc())).all())
            object_ids = {int(item.file_object_id) for item in versions if item.file_object_id is not None}
            objects = list(db.scalars(select(FileObject).where(
                FileObject.tenant_id == _tid(),
                FileObject.id.in_(object_ids or [-1]),
                FileObject.is_deleted.is_(False),
            )).all())
            objects_map = {int(item.id): item for item in objects}
            version_history = [
                _file_descriptor(item, objects_map.get(int(item.file_object_id)))
                for item in versions
            ]

        feedback_key = row.get("_feedbackKey")
        feedback_rows = context["feedbackHistory"].get(feedback_key, []) if feedback_key else []
        feedback_history = [_feedback_public(item) for item in feedback_rows]
        plag = context["plagiarism"].get(int(row["_gdFinalId"])) if row.get("_gdFinalId") else None
        plagiarism = None
        if plag:
            plagiarism = {
                "id": str(plag.id),
                "status": plag.status,
                "rate": plag.rate,
                "threshold": plag.threshold,
                "overThreshold": bool(plag.over_threshold),
                "disputeStatus": plag.dispute_status,
                "reportUrl": plag.report_url,
                "updatedAt": _iso(plag.updated_at),
            }

        public = _public_task(row)
        frozen_version = None
        if row.get("fileVersionId") and str(row["fileVersionId"]).isdigit():
            frozen_version = context["versionMap"].get(int(row["fileVersionId"]))
        frozen_file = None
        if frozen_version and frozen_version.file_object_id:
            frozen_file = context["fileMap"].get(int(frozen_version.file_object_id))
        return {
            "case": public,
            "student": {
                key: public.get(key)
                for key in (
                    "gdStudentId", "studentId", "studentNo", "studentName", "classId", "className",
                    "collegeId", "majorId", "majorName", "topicId", "topicTitle", "advisorName",
                )
            },
            "canonicalFile": public.get("canonicalFile"),
            "frozenFile": _file_descriptor(frozen_version, frozen_file, snapshot_sha=public.get("sourceSha256")),
            "versionHistory": version_history,
            "feedbackHistory": feedback_history,
            "plagiarism": plagiarism,
            "blockers": public.get("blockingReasons") or [],
            "allowedActions": public.get("allowedActions") or [],
        }

"""W7.2 append-only graduation review feedback evidence.

This is business evidence bound to the exact reviewed FileVersion. AuditTrail remains
separate technical audit evidence. No update/delete API is intentionally provided.
W7.6 student rejection notices are emitted transactionally from newly appended,
student-visible REJECTED evidence; delivery still belongs to the shared message outbox.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.core.context import get_current_user_ctx
from app.services.db_service import _tid
from app.services.message_identity import resolve_message_user_id


_STAGE_LABELS = {"PROPOSAL": "开题报告", "FINAL": "论文成果", "FORMAL": "正式评阅"}


def _json(value: Any, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def public_feedback(row: dict | None) -> dict | None:
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
        "categories": _json(row.get("categories"), []),
        "issues": _json(row.get("issues"), []),
        "summary": str(row.get("summary") or ""),
        "result": str(row.get("result") or ""),
        "reviewerUserId": str(row.get("reviewer_user_id")) if row.get("reviewer_user_id") is not None else None,
        "reviewerMentorId": str(row.get("reviewer_mentor_id")) if row.get("reviewer_mentor_id") is not None else None,
        "visibleToStudent": bool(row.get("visible_to_student", True)),
        "createdAt": row.get("created_at").isoformat() if hasattr(row.get("created_at"), "isoformat") else row.get("created_at"),
        "idempotencyKey": str(row.get("idempotency_key") or "") or None,
        "isSuperseded": bool(row.get("is_superseded", False)),
    }


def current_reviewer_mentor_id(db) -> int | None:
    try:
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        return int(mentor.id) if mentor else None
    except Exception:  # noqa: BLE001 - feedback can still record stable user evidence
        return None


def _user_id() -> int | None:
    value = resolve_message_user_id(get_current_user_ctx() or {})
    return int(value) if value else None


def make_idempotency_key(*, stage: str, source_record_id: int, file_version_id: int,
                         result: str, summary: str = "", categories=None, issues=None) -> str:
    payload = json.dumps({
        "stage": str(stage).upper(), "sourceRecordId": int(source_record_id),
        "fileVersionId": int(file_version_id), "result": str(result).upper(),
        "summary": str(summary or ""), "categories": categories or [], "issues": issues or [],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "w7:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_by_idempotency(db, idempotency_key: str | None) -> dict | None:
    if not idempotency_key:
        return None
    row = db.execute(text(
        "SELECT * FROM t_gd_review_feedback "
        "WHERE tenant_id=:tenant_id AND idempotency_key=:idempotency_key LIMIT 1"
    ), {"tenant_id": int(_tid()), "idempotency_key": str(idempotency_key)}).mappings().first()
    return dict(row) if row else None


def _emit_student_rejected_notice(
    db, *, gd_student_id: int, stage: str, source_record_id: int, file_version_id: int,
    round_no: int, summary: str, visible_to_student: bool,
) -> None:
    if not visible_to_student:
        return
    student_profile_id = db.execute(text(
        "SELECT student_id FROM t_gd_student "
        "WHERE tenant_id=:tenant_id AND id=:gd_student_id AND is_deleted=0 LIMIT 1"
    ), {"tenant_id": int(_tid()), "gd_student_id": int(gd_student_id)}).scalar()
    try:
        receiver_id = int(student_profile_id or 0)
    except (TypeError, ValueError):
        receiver_id = 0
    if receiver_id <= 0:
        return

    from app.modules.graduation.services import graduation_review_message_event_guard as message_guard
    from app.services.message_event_outbox_service import emit_receiver_notice

    message_guard.install()
    label = _STAGE_LABELS.get(str(stage).upper(), "毕业设计材料")
    reason = str(summary or "").strip() or "请查看评阅反馈并按要求完成整改后重新提交。"
    emit_receiver_notice(
        db,
        event_code=message_guard.EVENT_REVIEW_REJECTED,
        source_module="graduation",
        source_biz_type=f"GD_{str(stage).upper()}_REVIEW",
        source_biz_id=int(source_record_id),
        receiver_id=receiver_id,
        title=f"{label}退回整改",
        content=reason,
        receiver_as="student",
        action_key=message_guard.ACTION_STUDENT_REVIEW_FEEDBACK,
        dedup_extra=f"fv:{int(file_version_id)}:round:{int(round_no)}",
    )


def append_feedback_in_session(
    db, *, batch_id: int | None, gd_student_id: int, stage: str, source_record_id: int,
    material_id: int, file_version_id: int, source_sha256: str, result: str,
    summary: str = "", categories=None, issues=None, review_id: int | None = None,
    reviewer_mentor_id: int | None = None, visible_to_student: bool = True,
    idempotency_key: str | None = None,
) -> dict:
    stage = str(stage or "").upper()
    result = str(result or "").upper()
    categories = list(categories or [])
    issues = list(issues or [])
    key = str(idempotency_key or "").strip() or make_idempotency_key(
        stage=stage, source_record_id=int(source_record_id), file_version_id=int(file_version_id),
        result=result, summary=summary, categories=categories, issues=issues,
    )
    existing = find_by_idempotency(db, key)
    if existing:
        return existing

    round_no = int(db.execute(text(
        "SELECT COALESCE(MAX(round_no),0)+1 FROM t_gd_review_feedback "
        "WHERE tenant_id=:tenant_id AND stage=:stage AND source_record_id=:source_record_id"
    ), {"tenant_id": int(_tid()), "stage": stage, "source_record_id": int(source_record_id)}).scalar() or 1)
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(text(
        "INSERT INTO t_gd_review_feedback ("
        "tenant_id,batch_id,gd_student_id,stage,source_record_id,review_id,material_id,file_version_id,"
        "source_sha256,round_no,categories,issues,summary,result,reviewer_user_id,reviewer_mentor_id,"
        "visible_to_student,idempotency_key,is_superseded,created_at) VALUES ("
        ":tenant_id,:batch_id,:gd_student_id,:stage,:source_record_id,:review_id,:material_id,:file_version_id,"
        ":source_sha256,:round_no,:categories,:issues,:summary,:result,:reviewer_user_id,:reviewer_mentor_id,"
        ":visible_to_student,:idempotency_key,0,:created_at)"
    ), {
        "tenant_id": int(_tid()), "batch_id": int(batch_id) if batch_id is not None else None,
        "gd_student_id": int(gd_student_id), "stage": stage, "source_record_id": int(source_record_id),
        "review_id": int(review_id) if review_id is not None else None, "material_id": int(material_id),
        "file_version_id": int(file_version_id), "source_sha256": str(source_sha256), "round_no": round_no,
        "categories": json.dumps(categories, ensure_ascii=False), "issues": json.dumps(issues, ensure_ascii=False),
        "summary": str(summary or "")[:2000], "result": result, "reviewer_user_id": _user_id(),
        "reviewer_mentor_id": int(reviewer_mentor_id) if reviewer_mentor_id is not None else current_reviewer_mentor_id(db),
        "visible_to_student": 1 if visible_to_student else 0, "idempotency_key": key, "created_at": created_at,
    })
    if result == "REJECTED":
        _emit_student_rejected_notice(
            db,
            gd_student_id=int(gd_student_id),
            stage=stage,
            source_record_id=int(source_record_id),
            file_version_id=int(file_version_id),
            round_no=round_no,
            summary=str(summary or ""),
            visible_to_student=bool(visible_to_student),
        )
    return find_by_idempotency(db, key) or {"idempotency_key": key, "round_no": round_no}


def feedback_for_sources(db, keys: list[tuple[str, int]], *, history: bool = False) -> dict[tuple[str, str], Any]:
    if not keys:
        return {}
    clauses = []
    params: dict[str, Any] = {"tenant_id": int(_tid())}
    for idx, (stage, source_id) in enumerate(keys):
        clauses.append(f"(stage=:stage_{idx} AND source_record_id=:source_{idx})")
        params[f"stage_{idx}"] = str(stage).upper()
        params[f"source_{idx}"] = int(source_id)
    rows = db.execute(text(
        "SELECT * FROM t_gd_review_feedback WHERE tenant_id=:tenant_id AND (" + " OR ".join(clauses) + ") "
        "ORDER BY created_at DESC, id DESC"
    ), params).mappings().all()
    result: dict[tuple[str, str], Any] = {}
    for raw in rows:
        row = dict(raw)
        key = (str(row.get("stage") or "").upper(), str(row.get("source_record_id") or ""))
        if history:
            result.setdefault(key, []).append(public_feedback(row))
        else:
            result.setdefault(key, public_feedback(row))
    if history:
        for key in result:
            result[key] = list(reversed(result[key]))
    return result

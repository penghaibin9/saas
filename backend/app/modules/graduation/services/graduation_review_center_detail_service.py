"""W7.4 production Review Center detail hydration.

This keeps the same Review Center CTE/FileVersion/feedback projection as the queue while
fixing two detail-path invariants: the proven batch id is hydrated into the DTO before
``_public`` consumes it, and reviewer requests can use a stable task-scoped student set
instead of the generic per-student relation walk.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import bindparam, text

from app.core.exceptions import AppException, not_found
from app.modules.graduation.services import graduation_review_center_query_service as q
from app.modules.graduation.services import graduation_review_feedback_service as feedback
from app.modules.graduation.services.graduation_review_center_scope_service import reviewer_student_ids
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def detail(*, batch_id: int, case_type: str, record_id: int,
           reviewer_mentor_id: int | None = None) -> dict:
    case_type = str(case_type).upper()
    if case_type not in q.CASE_TYPES:
        raise AppException("VALIDATION_ERROR", "caseType 不支持")
    if reviewer_mentor_id is not None and case_type != "FORMAL_REVIEW":
        raise not_found("评阅任务不存在或不在当前数据范围内")

    with session() as db:
        if reviewer_mentor_id is None:
            scope_ids = accessible_student_ids(db, int(_tid()), batch_id=int(batch_id))
        else:
            scope_ids = reviewer_student_ids(
                db,
                batch_id=int(batch_id),
                reviewer_mentor_id=int(reviewer_mentor_id),
            )
        params = q._base_params(batch_id, scope_ids)
        params.update({"case_type": case_type, "record_id": int(record_id)})
        where = " WHERE case_type=:case_type AND record_id=:record_id"
        if reviewer_mentor_id is not None:
            where += " AND reviewer_mentor_id=:reviewer_mentor_id"
            params["reviewer_mentor_id"] = int(reviewer_mentor_id)
        stmt = text(q._CTE + "SELECT * FROM projected" + where + " LIMIT 1").bindparams(
            bindparam("scope_ids", expanding=True)
        )
        raw = db.execute(stmt, params).mappings().first()
        if not raw:
            raise not_found("评阅任务不存在或不在当前数据范围内")

        # The CTE proves :batch_id in every union arm but does not select it. Hydrate the
        # already-proven value before q._public accesses row['batch_id'].
        row = {**dict(raw), "batch_id": int(batch_id)}
        deadlines = q._batch_deadlines(db, int(batch_id))
        now = datetime.now(timezone.utc)
        stage = "PROPOSAL" if case_type == "PROPOSAL" else "FORMAL" if case_type == "FORMAL_REVIEW" else "FINAL"
        histories = feedback.feedback_for_sources(db, [(stage, int(record_id))], history=True)
        history = histories.get((stage, str(record_id)), [])
        latest = history[-1] if history else None
        case = q._public(row, deadlines, now, latest)

        versions = []
        if row.get("asset_id"):
            version_rows = db.execute(text(
                "SELECT fv.id file_version_id,fv.version_no,fv.status version_status,"
                "fo.id file_id,fo.file_name,fo.mime_type,fo.status file_status,fo.scan_status,fo.sha256 source_sha256 "
                "FROM t_file_version fv JOIN t_file_object fo "
                "ON fo.id=fv.file_object_id AND fo.tenant_id=fv.tenant_id AND fo.is_deleted=0 "
                "WHERE fv.tenant_id=:tenant_id AND fv.asset_id=:asset_id AND fv.is_deleted=0 "
                "ORDER BY fv.version_no ASC"
            ), {"tenant_id": int(_tid()), "asset_id": int(row["asset_id"])}).mappings().all()
            versions = [q._descriptor(dict(version)) for version in version_rows]

        plagiarism = None
        if row.get("gd_final_id"):
            plag_row = db.execute(text(
                "SELECT id,status,rate,threshold,over_threshold,dispute_status,dispute_comment,submit_at "
                "FROM t_gd_plagiarism WHERE tenant_id=:tenant_id AND gd_final_id=:fid AND is_deleted=0 "
                "ORDER BY id DESC LIMIT 1"
            ), {"tenant_id": int(_tid()), "fid": int(row["gd_final_id"])}).mappings().first()
            plagiarism = dict(plag_row) if plag_row else None

        return {
            "case": case,
            "student": {
                "gdStudentId": case["gdStudentId"], "studentName": case["studentName"],
                "studentNo": case["studentNo"], "className": case["className"],
                "majorName": case["majorName"], "topicTitle": case["topicTitle"],
                "advisorName": case["advisorName"],
            },
            "canonicalMaterial": {
                "materialId": case["materialId"], "materialCode": case["materialCode"],
                "materialName": case["materialName"],
            },
            "canonicalFile": case.get("canonicalFile"),
            "frozenFile": q._descriptor(row),
            "versionHistory": versions,
            "feedbackHistory": history,
            "plagiarism": plagiarism,
            "blockers": case["blockingReasons"],
            "allowedActions": case["allowedActions"],
            "deadlineAt": case["deadlineAt"],
            "overdue": case["overdue"],
        }


__all__ = ["detail"]

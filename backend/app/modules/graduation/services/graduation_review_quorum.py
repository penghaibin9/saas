"""One batch-rule truth for completed reviews of the current approved final."""
from __future__ import annotations

from sqlalchemy import bindparam, text

from app.core.exceptions import AppException
from app.modules.graduation.services.graduation_batch_service import DEFAULT_RULES
from app.services.db_service import _tid
from app.services.file_scan_constants import READY_SCAN_STATES


def required_reviewers(batch) -> int:
    rules = batch.rules_config if batch and isinstance(batch.rules_config, dict) else {}
    review = rules.get("review") if isinstance(rules.get("review"), dict) else {}
    raw = review.get("minReviewers", DEFAULT_RULES["review"]["minReviewers"])
    if raw is None:
        raw = DEFAULT_RULES["review"]["minReviewers"]
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        raise AppException("DATA_CONFLICT", "毕设批次评阅人数规则无效，请先核对批次规则")
    return raw


def current_evidence_review_ids(db, reviews) -> set[int]:
    """Use the W7 frozen version only while it is the canonical final material."""
    ids = [int(row.id) for row in reviews]
    if not ids:
        return set()
    stmt = text("""
        SELECT r.id FROM t_gd_review r
        JOIN t_gd_student s
          ON s.tenant_id=r.tenant_id AND s.id=r.gd_student_id AND s.is_deleted=0
        JOIN t_gd_student_material m
          ON m.tenant_id=r.tenant_id AND m.gd_student_id=r.gd_student_id
         AND m.id=r.material_id AND m.batch_id=s.batch_id
         AND m.material_code='THESIS_FINAL' AND m.source_record_type='FINAL'
         AND BINARY m.source_record_id=BINARY CAST(r.gd_final_id AS CHAR)
         AND m.current_version_id=r.file_version_id AND m.is_deleted=0
        JOIN t_file_version v
          ON v.tenant_id=r.tenant_id AND v.id=r.file_version_id
         AND v.asset_id=m.asset_id AND v.status='APPROVED'
         AND v.is_current=1 AND v.is_deleted=0
        JOIN t_file_object f
          ON f.tenant_id=r.tenant_id AND f.id=v.file_object_id
         AND BINARY f.sha256=BINARY r.source_sha256 AND f.is_deleted=0
         AND UPPER(f.status)='AVAILABLE'
         AND UPPER(COALESCE(f.scan_status,'')) IN :ready_scan_states
        WHERE r.tenant_id=:tenant_id AND r.id IN :review_ids
          AND r.file_version_id IS NOT NULL AND r.source_sha256 IS NOT NULL
          AND r.source_sha256<>''
          AND r.is_deleted=0
    """).bindparams(bindparam("review_ids", expanding=True),
                    bindparam("ready_scan_states", expanding=True))
    return {int(row[0]) for row in db.execute(stmt, {
        "tenant_id": _tid(), "review_ids": ids,
        "ready_scan_states": tuple(READY_SCAN_STATES),
    }).all()}


def completed_reviews(batch, final, reviews, evidence_ids: set[int]) -> tuple[list, int]:
    """Return one scored, active completion per stable reviewer ID."""
    required = required_reviewers(batch)
    if not final or final.final_type != "定稿" or final.status != "APPROVED" or final.is_deleted:
        return [], required
    latest_by_reviewer = {}
    for row in reviews:
        if (
            row.is_deleted or row.status != "COMPLETED"
            or row.gd_final_id != final.id or row.score is None
            or not row.reviewer_mentor_id or int(row.id) not in evidence_ids
        ):
            continue
        reviewer_id = int(row.reviewer_mentor_id)
        if reviewer_id not in latest_by_reviewer or int(row.id) > int(latest_by_reviewer[reviewer_id].id):
            latest_by_reviewer[reviewer_id] = row
    return list(latest_by_reviewer.values()), required


def require_review_count(count: int, required: int) -> None:
    if count < required:
        raise AppException(
            "DATA_CONFLICT",
            f"当前有效定稿需 {required} 名不同评阅人完成评阅，现有 {count} 名，请先补齐评阅并重新核算",
        )

"""Yiyang C08/G15 report quality rules, immutable snapshots and review facts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import (
    InternshipReportReview,
    InternshipReportRuleConfig,
    InternshipReportVersion,
)
from app.services import file_service
from app.services.db_service import _tid

DEFAULT_RULES = {
    "weeklyMinWords": 30,
    "planTaskMinWords": 10,
    "monthlyMinWords": 100,
    "summaryMinWords": 300,
    "maxImages": 9,
    "maxVideos": 3,
}


def rules_for_batch(db, batch_id) -> dict:
    row = db.scalar(select(InternshipReportRuleConfig).where(
        InternshipReportRuleConfig.tenant_id == _tid(),
        InternshipReportRuleConfig.batch_id == int(batch_id),
        InternshipReportRuleConfig.is_deleted.is_(False),
    ))
    if not row:
        return dict(DEFAULT_RULES)
    return {
        "weeklyMinWords": int(row.weekly_min_words or 30),
        "planTaskMinWords": int(row.plan_task_min_words or 10),
        "monthlyMinWords": int(row.monthly_min_words or 100),
        "summaryMinWords": int(row.summary_min_words or 300),
        "maxImages": int(row.max_images or 9),
        "maxVideos": int(row.max_videos or 3),
    }


def minimum_words(rules: dict, report_type: str) -> int:
    rt = str(report_type or "").upper()
    return {
        "DAILY": int(rules.get("weeklyMinWords") or 30),
        "MONTHLY": int(rules.get("monthlyMinWords") or 100),
        "SUMMARY": int(rules.get("summaryMinWords") or 300),
    }.get(rt, 30)


def validate_attachments(file_ids, rules: dict) -> tuple[list[str], list[dict]]:
    ids = []
    metas = []
    seen = set()
    image_count = 0
    video_count = 0
    for raw in file_ids or []:
        fid = str(raw or "").strip()
        if not fid or fid in seen:
            continue
        seen.add(fid)
        meta = file_service.get_file_meta(fid)
        if not meta:
            raise AppException("VALIDATION_ERROR", f"附件 {fid} 不存在或无权访问")
        mime = str(meta.get("mimeType") or "").lower()
        if mime.startswith("image/"):
            image_count += 1
            kind = "IMAGE"
        elif mime.startswith("video/"):
            video_count += 1
            kind = "VIDEO"
        else:
            raise AppException("VALIDATION_ERROR", "过程报告附件仅支持图片或视频")
        ids.append(fid)
        metas.append({
            "fileId": fid,
            "fileName": meta.get("fileName") or "",
            "mimeType": meta.get("mimeType") or "",
            "sizeBytes": int(meta.get("sizeBytes") or 0),
            "sha256": meta.get("sha256") or "",
            "kind": kind,
        })
    if image_count > int(rules.get("maxImages") or 9):
        raise AppException("VALIDATION_ERROR", f"图片最多 {int(rules.get('maxImages') or 9)} 张")
    if video_count > int(rules.get("maxVideos") or 3):
        raise AppException("VALIDATION_ERROR", f"视频最多 {int(rules.get('maxVideos') or 3)} 个")
    return ids, metas


def append_process_snapshot(db, *, row, record, student, content: str,
                            attachment_ids: list[str], attachment_meta: list[dict]) -> InternshipReportVersion:
    next_no = int(db.scalar(select(func.max(InternshipReportVersion.version_no)).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "PROCESS",
        InternshipReportVersion.report_id == row.id,
    )) or 0) + 1
    snap = InternshipReportVersion(
        tenant_id=_tid(),
        report_kind="PROCESS",
        report_id=row.id,
        version_no=next_no,
        internship_id=record.id,
        student_id=student.id,
        report_type=row.report_type,
        period_key=row.period_key,
        word_count=len(content),
        content_json={"content": content},
        attachment_file_ids_json=attachment_ids or [],
        attachment_meta_json=attachment_meta or [],
        submitted_at=row.submitted_at or datetime.utcnow(),
    )
    db.add(snap)
    db.flush()
    for fid in attachment_ids or []:
        file_service.bind_file_biz(
            fid, "INTERNSHIP_REPORT", str(row.id), user=None, db=db)
    return snap


def latest_process_snapshot(db, report_id) -> InternshipReportVersion | None:
    return db.scalar(select(InternshipReportVersion).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "PROCESS",
        InternshipReportVersion.report_id == int(report_id),
    ).order_by(
        InternshipReportVersion.version_no.desc(),
        InternshipReportVersion.id.desc(),
    ))


def snapshot_view(db, report_id) -> dict:
    rows = db.scalars(select(InternshipReportVersion).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "PROCESS",
        InternshipReportVersion.report_id == int(report_id),
    ).order_by(InternshipReportVersion.version_no.desc())).all()
    reviews = db.scalars(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_kind == "PROCESS",
        InternshipReportReview.report_id == int(report_id),
    ).order_by(InternshipReportReview.reviewed_at.desc())).all()
    by_version = {int(r.report_version_id): r for r in reviews}
    return {
        "versions": [{
            "id": str(v.id),
            "versionNo": int(v.version_no),
            "wordCount": int(v.word_count or 0),
            "content": (v.content_json or {}).get("content") or "",
            "attachments": v.attachment_meta_json or [],
            "submittedAt": v.submitted_at.isoformat() if v.submitted_at else "",
            "review": (
                {
                    "action": by_version[v.id].action,
                    "ratingLevel": by_version[v.id].rating_level,
                    "summaryScore": (
                        float(by_version[v.id].summary_score)
                        if by_version[v.id].summary_score is not None else None
                    ),
                    "comment": by_version[v.id].comment or "",
                    "reviewerName": by_version[v.id].reviewer_name or "",
                    "reviewedAt": (
                        by_version[v.id].reviewed_at.isoformat()
                        if by_version[v.id].reviewed_at else ""
                    ),
                } if v.id in by_version else None
            ),
        } for v in rows],
    }


def record_process_review(db, *, row, action: str, comment: str, user: dict,
                          rating_level=None, summary_score=None) -> InternshipReportReview:
    snap = latest_process_snapshot(db, row.id)
    if not snap:
        raise AppException("DATA_CONFLICT", "当前报告缺少提交版本快照，禁止无证据批阅")
    if db.scalar(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_version_id == snap.id,
    )):
        raise AppException("DATA_CONFLICT", "当前报告版本已经批阅，请刷新后重试")

    rating = None
    if rating_level not in (None, ""):
        try:
            rating = int(rating_level)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "五级评价必须是 1 到 5") from None
        if rating < 1 or rating > 5:
            raise AppException("VALIDATION_ERROR", "五级评价必须是 1 到 5")

    score = None
    if summary_score not in (None, ""):
        try:
            score = float(summary_score)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "总结评分必须是 0 到 100") from None
        if score < 0 or score > 100:
            raise AppException("VALIDATION_ERROR", "总结评分必须是 0 到 100")
        if row.report_type != "SUMMARY":
            raise AppException("VALIDATION_ERROR", "只有实习总结允许填写 0 到 100 分")

    if action == "APPROVE" and rating is None:
        raise AppException("VALIDATION_ERROR", "通过报告时必须选择五级评价")
    if action == "APPROVE" and row.report_type == "SUMMARY" and score is None:
        raise AppException("VALIDATION_ERROR", "通过实习总结时必须填写 0 到 100 分")

    review = InternshipReportReview(
        tenant_id=_tid(),
        report_kind="PROCESS",
        report_id=row.id,
        report_version_id=snap.id,
        action=action,
        rating_level=rating,
        summary_score=score,
        comment=(comment or "").strip() or None,
        reviewer_user_id=str((user or {}).get("userId") or (user or {}).get("id") or "") or None,
        reviewer_name=(user or {}).get("realName") or "系统",
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)
    db.flush()
    return review

"""Yiyang C08/G15 report quality rules, immutable snapshots and review facts."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite

from sqlalchemy import and_, case, func, or_, select

from app.core.exceptions import AppException
from app.models import (
    InternshipBatch,
    InternshipRecord,
    InternshipProcessReport,
    InternshipReportReview,
    InternshipReportRuleConfig,
    InternshipReportVersion,
    StudentProfile,
    WeeklyReport,
)
from app.services import file_service
from app.services.db_service import _iso, _tid, session

REPORT_DOCUMENT_EXTENSIONS = {"rar", "zip", "doc", "docx", "pdf", "xls", "xlsx"}
MAX_REPORT_DOCUMENTS = 9
SUBMITTED_REPORT_STATUSES = ("PENDING_REVIEW", "APPROVED", "RETURNED")

DEFAULT_RULES = {
    "dailyMinWords": 30,
    "weeklyMinWords": 30,
    "planTaskMinWords": 10,
    "monthlyMinWords": 100,
    "summaryMinWords": 300,
    "dailyRequiredCount": 0,
    "weeklyRequiredCount": 0,
    "monthlyRequiredCount": 0,
    "summaryRequiredCount": 1,
    "maxImages": 9,
    "maxVideos": 3,
}


def _non_negative_int(value, fallback: int) -> int:
    if value in (None, ""):
        return fallback
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _positive_int(value, fallback: int) -> int:
    if value in (None, ""):
        return fallback
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def required_report_counts(batch) -> dict:
    """Batch counts are authoritative; missing/zero counts never imply calendar tasks."""
    config = (batch.rules_config or {}) if batch else {}
    weekly = config.get("weeklyReport") or {}
    process = config.get("processReport") or {}
    return {
        key: _non_negative_int(value, DEFAULT_RULES[key])
        for key, value in (
            ("weeklyRequiredCount", weekly.get("requiredCount")),
            ("dailyRequiredCount", process.get("dailyRequiredCount")),
            ("monthlyRequiredCount", process.get("monthlyRequiredCount")),
            ("summaryRequiredCount", process.get("summaryRequiredCount")),
        )
    }


def rules_for_batch(db, batch_id) -> dict:
    """Single report-rule projection.

    ix0008 retains the original quality row for backward compatibility, while the batch's
    canonical rules_config owns procurement-facing per-plan counts and can override minimums.
    This avoids a second configuration workflow and keeps PC/mobile progress on the same truth.
    """
    bid = int(batch_id)
    row = db.scalar(select(InternshipReportRuleConfig).where(
        InternshipReportRuleConfig.tenant_id == _tid(),
        InternshipReportRuleConfig.batch_id == bid,
        InternshipReportRuleConfig.is_deleted.is_(False),
    ))
    rules = dict(DEFAULT_RULES)
    if row:
        rules.update({
            "weeklyMinWords": _non_negative_int(row.weekly_min_words, rules["weeklyMinWords"]),
            "planTaskMinWords": int(row.plan_task_min_words or rules["planTaskMinWords"]),
            "monthlyMinWords": int(row.monthly_min_words or rules["monthlyMinWords"]),
            "summaryMinWords": int(row.summary_min_words or rules["summaryMinWords"]),
            "maxImages": _non_negative_int(row.max_images, rules["maxImages"]),
            "maxVideos": _non_negative_int(row.max_videos, rules["maxVideos"]),
        })

    batch = db.get(InternshipBatch, bid)
    config = (batch.rules_config or {}) if batch else {}
    weekly = config.get("weeklyReport") or {}
    process = config.get("processReport") or {}

    rules["weeklyMinWords"] = _non_negative_int(
        weekly.get("minWordCount"), rules["weeklyMinWords"])
    rules.update(required_report_counts(batch))

    rules["dailyMinWords"] = _positive_int(
        process.get("dailyMinWords"), rules["dailyMinWords"])
    rules["monthlyMinWords"] = _positive_int(
        process.get("monthlyMinWords"), rules["monthlyMinWords"])
    rules["summaryMinWords"] = _positive_int(
        process.get("summaryMinWords"), rules["summaryMinWords"])
    rules["maxImages"] = _non_negative_int(
        process.get("maxImages"), rules["maxImages"])
    rules["maxVideos"] = _non_negative_int(
        process.get("maxVideos"), rules["maxVideos"])
    return rules


def minimum_words(rules: dict, report_type: str) -> int:
    rt = str(report_type or "").upper()
    return {
        "DAILY": int(rules.get("dailyMinWords") or 30),
        "MONTHLY": int(rules.get("monthlyMinWords") or 100),
        "SUMMARY": int(rules.get("summaryMinWords") or 300),
    }.get(rt, 30)


def _rating(value):
    if value in (None, ""):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not isfinite(number) or number not in (1, 2, 3, 4, 5):
            raise ValueError
        return int(number)
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", "五级评价必须是1到5的整数") from None


def validate_attachments(file_ids, rules: dict) -> tuple[list[str], list[dict]]:
    ids = []
    metas = []
    seen = set()
    image_count = 0
    video_count = 0
    document_count = 0
    for raw in file_ids or []:
        fid = str(raw or "").strip()
        if not fid or fid in seen:
            continue
        seen.add(fid)
        meta = file_service.get_file_meta(fid)
        if not meta:
            raise AppException("VALIDATION_ERROR", f"附件 {fid} 不存在或无权访问")
        mime = str(meta.get("mimeType") or "").lower()
        ext = str(meta.get("ext") or "").lower().lstrip(".")
        if mime.startswith("image/"):
            image_count += 1
            kind = "IMAGE"
        elif mime.startswith("video/"):
            video_count += 1
            kind = "VIDEO"
        elif ext in REPORT_DOCUMENT_EXTENSIONS:
            document_count += 1
            kind = "DOCUMENT"
        else:
            raise AppException(
                "VALIDATION_ERROR",
                "过程报告附件仅支持图片、视频、压缩包、文档或表格",
            )
        ids.append(fid)
        metas.append({
            "fileId": fid,
            "fileName": meta.get("fileName") or "",
            "mimeType": meta.get("mimeType") or "",
            "sizeBytes": int(meta.get("sizeBytes") or 0),
            "sha256": meta.get("sha256") or "",
            "kind": kind,
        })
    max_images = _non_negative_int(rules.get("maxImages"), DEFAULT_RULES["maxImages"])
    max_videos = _non_negative_int(rules.get("maxVideos"), DEFAULT_RULES["maxVideos"])
    if image_count > max_images:
        raise AppException("VALIDATION_ERROR", f"图片最多 {max_images} 张")
    if video_count > max_videos:
        raise AppException("VALIDATION_ERROR", f"视频最多 {max_videos} 个")
    if document_count > MAX_REPORT_DOCUMENTS:
        raise AppException("VALIDATION_ERROR", f"文档/压缩附件最多 {MAX_REPORT_DOCUMENTS} 个")
    return ids, metas



def _bind_report_file(db, file_id, *, row, record, student, kind):
    from app.core.context import get_current_user_ctx
    from app.services.file_business_binding_service import bind_file_to_business
    biz_type = 'INTERNSHIP_WEEKLY_REPORT' if kind == 'WEEKLY' else 'INTERNSHIP_REPORT'
    bind_file_to_business(db,file_id=file_id,biz_type=biz_type,biz_id=str(row.id),
        actor=get_current_user_ctx() or {},subject_type='STUDENT',subject_id=str(student.id),
        module_code='INTERNSHIP',student_id=student.id,batch_id=str(record.batch_id),
        college_id=student.college_id,class_id=student.class_id,
        scope={'internshipId':str(record.id),'studentId':str(student.id),'studentNo':student.student_no,
               'batchId':str(record.batch_id),'advisorUserId':str(record.advisor_user_id or ''),
               'businessType':biz_type,'businessId':str(row.id)},
        legacy_target_values={str(row.id),str(record.id),str(student.id),str(student.student_no)})

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
        _bind_report_file(db, fid, row=row, record=record, student=student, kind="PROCESS")
    return snap



def append_weekly_snapshot(db, *, row, record, student, content_json: dict,
                           attachment_ids: list[str], attachment_meta: list[dict]) -> InternshipReportVersion:
    next_no = int(db.scalar(select(func.max(InternshipReportVersion.version_no)).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "WEEKLY",
        InternshipReportVersion.report_id == row.id,
    )) or 0) + 1
    snap = InternshipReportVersion(
        tenant_id=_tid(),
        report_kind="WEEKLY",
        report_id=row.id,
        version_no=next_no,
        internship_id=record.id,
        student_id=student.id,
        report_type=None,
        period_key=str(row.week_number),
        word_count=int(row.word_count or 0),
        content_json=content_json or {},
        attachment_file_ids_json=attachment_ids or [],
        attachment_meta_json=attachment_meta or [],
        submitted_at=row.submitted_at or datetime.utcnow(),
    )
    db.add(snap)
    db.flush()
    for fid in attachment_ids or []:
        _bind_report_file(db, fid, row=row, record=record, student=student, kind="WEEKLY")
    return snap


def latest_weekly_snapshot(db, report_id) -> InternshipReportVersion | None:
    return db.scalar(select(InternshipReportVersion).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "WEEKLY",
        InternshipReportVersion.report_id == int(report_id),
    ).order_by(
        InternshipReportVersion.version_no.desc(),
        InternshipReportVersion.id.desc(),
    ))


def latest_review_map(db, report_kind: str, report_ids) -> dict[int, dict]:
    """Only the current submission's review; old reviews remain in immutable history."""
    ids = []
    for raw in report_ids or []:
        try:
            rid = int(raw)
        except (TypeError, ValueError):
            continue
        if rid > 0 and rid not in ids:
            ids.append(rid)
    if not ids:
        return {}
    kind = str(report_kind or "").strip().upper()
    latest = select(
        InternshipReportVersion.report_id.label("report_id"),
        func.max(InternshipReportVersion.version_no).label("version_no"),
    ).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == kind,
        InternshipReportVersion.report_id.in_(ids),
    ).group_by(InternshipReportVersion.report_id).subquery()
    rows = db.scalars(select(InternshipReportReview).join(
        InternshipReportVersion, and_(
            InternshipReportVersion.id == InternshipReportReview.report_version_id,
            InternshipReportVersion.tenant_id == _tid(),
            InternshipReportVersion.report_kind == kind,
            InternshipReportVersion.report_id == InternshipReportReview.report_id,
        ),
    ).join(latest, and_(
        latest.c.report_id == InternshipReportVersion.report_id,
        latest.c.version_no == InternshipReportVersion.version_no,
    )).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_kind == kind,
        InternshipReportReview.report_id.in_(ids),
    ).order_by(
        InternshipReportReview.reviewed_at.desc(),
        InternshipReportReview.id.desc(),
    )).all()
    out = {}
    for row in rows:
        rid = int(row.report_id)
        if rid in out:
            continue
        out[rid] = {
            "action": row.action,
            "ratingLevel": int(row.rating_level) if row.rating_level is not None else None,
            "summaryScore": float(row.summary_score) if row.summary_score is not None else None,
            "comment": row.comment or "",
            "reviewerUserId": row.reviewer_user_id or "",
            "reviewerName": row.reviewer_name or "",
            "reviewedAt": _iso(row.reviewed_at) or "",
            "reportVersionId": str(row.report_version_id),
        }
    return out


def latest_snapshot_map(db, report_kind: str, report_ids) -> dict:
    ids = list(dict.fromkeys(int(value) for value in report_ids))
    if not ids:
        return {}
    latest = select(InternshipReportVersion.report_id.label("report_id"),
        func.max(InternshipReportVersion.version_no).label("version_no")).where(
            InternshipReportVersion.tenant_id == _tid(), InternshipReportVersion.report_kind == report_kind,
            InternshipReportVersion.report_id.in_(ids)).group_by(InternshipReportVersion.report_id).subquery()
    rows = db.scalars(select(InternshipReportVersion).join(latest, and_(
        latest.c.report_id == InternshipReportVersion.report_id,
        latest.c.version_no == InternshipReportVersion.version_no)).where(
            InternshipReportVersion.tenant_id == _tid(), InternshipReportVersion.report_kind == report_kind)).all()
    return {int(row.report_id): row for row in rows}


def filter_submission_dates(query, model, start_date=None, end_date=None):
    from app.core.timeutil import local_day_bounds_utc
    try:
        start = local_day_bounds_utc(start_date)[0] if start_date else None
        end = local_day_bounds_utc(end_date)[1] if end_date else None
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "提交日期格式不正确，请选择有效日期") from None
    if start and end and start >= end:
        raise AppException("VALIDATION_ERROR", "开始日期不能晚于结束日期")
    if start:
        query = query.where(model.submitted_at >= start)
    if end:
        query = query.where(model.submitted_at < end)
    return query


def format_report_time(value):
    from app.core.timeutil import UTC, tenant_tz
    if not value:
        return ""
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(tenant_tz()).strftime("%Y-%m-%d %H:%M")


def report_review_performance(user: dict, batch_id) -> dict:
    """Auditable reviewer performance based on immutable review facts, not page counts."""
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        ).subquery()
        scoped_ids = select(scoped.c.id)

        weekly_ids = select(WeeklyReport.id).where(
            WeeklyReport.tenant_id == _tid(),
            WeeklyReport.internship_id.in_(scoped_ids),
            WeeklyReport.is_deleted.is_(False),
        )
        process_ids = select(InternshipProcessReport.id).where(
            InternshipProcessReport.tenant_id == _tid(),
            InternshipProcessReport.internship_id.in_(scoped_ids),
            InternshipProcessReport.is_deleted.is_(False),
        )

        reviews = list(db.scalars(select(InternshipReportReview).where(
            InternshipReportReview.tenant_id == _tid(),
            InternshipReportReview.report_kind == "WEEKLY",
            InternshipReportReview.report_id.in_(weekly_ids),
        )).all())
        reviews.extend(db.scalars(select(InternshipReportReview).where(
            InternshipReportReview.tenant_id == _tid(),
            InternshipReportReview.report_kind == "PROCESS",
            InternshipReportReview.report_id.in_(process_ids),
        )).all())

        buckets: dict[str, dict] = {}
        for row in reviews:
            reviewer_id = str(row.reviewer_user_id or "")
            reviewer_name = str(row.reviewer_name or "系统")
            key = reviewer_id or f"name:{reviewer_name}"
            item = buckets.setdefault(key, {
                "rowKey": key,
                "reviewerUserId": reviewer_id,
                "reviewerName": reviewer_name,
                "reviewCount": 0,
                "approvedCount": 0,
                "returnedCount": 0,
                "weeklyReviewCount": 0,
                "processReviewCount": 0,
                "ratedCount": 0,
                "ratingTotal": 0,
                "ratingDistribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                "summaryScoredCount": 0,
                "summaryScoreTotal": 0.0,
                "lastReviewedAt": "",
            })
            item["reviewCount"] += 1
            if row.action == "APPROVE":
                item["approvedCount"] += 1
            elif row.action == "RETURN":
                item["returnedCount"] += 1
            if row.report_kind == "WEEKLY":
                item["weeklyReviewCount"] += 1
            else:
                item["processReviewCount"] += 1
            if row.rating_level is not None:
                rating = int(row.rating_level)
                if 1 <= rating <= 5:
                    item["ratedCount"] += 1
                    item["ratingTotal"] += rating
                    item["ratingDistribution"][str(rating)] += 1
            if row.summary_score is not None:
                item["summaryScoredCount"] += 1
                item["summaryScoreTotal"] += float(row.summary_score)
            reviewed_at = _iso(row.reviewed_at) or ""
            if reviewed_at > item["lastReviewedAt"]:
                item["lastReviewedAt"] = reviewed_at

        items = []
        for raw in buckets.values():
            item = dict(raw)
            item["averageRating"] = (
                round(item["ratingTotal"] / item["ratedCount"], 2)
                if item["ratedCount"] else None
            )
            item["summaryAverageScore"] = (
                round(item["summaryScoreTotal"] / item["summaryScoredCount"], 2)
                if item["summaryScoredCount"] else None
            )
            item.pop("ratingTotal", None)
            item.pop("summaryScoreTotal", None)
            items.append(item)
        items.sort(key=lambda x: (-int(x["reviewCount"]), x["reviewerName"]))

        return {
            "batchId": str(batch.id),
            "batchName": getattr(batch, "batch_name", "") or "",
            "items": items,
            "total": len(items),
            "reviewFactCount": len(reviews),
            "definition": {
                "reviewCount": "不可变批阅事实数；同一报告退回后重交再次批阅会形成新的批阅事实",
                "averageRating": "仅统计已填写的1～5级评价",
                "summaryAverageScore": "仅统计实习总结已填写的0～100分",
            },
        }


def export_report_review_performance(user: dict, batch_id) -> dict:
    from app.services import xlsx_util

    data = report_review_performance(user, batch_id)
    headers = [
        "批阅教师", "批阅次数", "通过", "退回", "周报批阅", "日报/月报/总结批阅",
        "平均等级(1-5)", "1级", "2级", "3级", "4级", "5级",
        "总结评分篇数", "总结平均分", "最近批阅时间",
    ]
    rows = []
    for item in data["items"]:
        dist = item["ratingDistribution"]
        rows.append([
            item["reviewerName"], item["reviewCount"], item["approvedCount"], item["returnedCount"],
            item["weeklyReviewCount"], item["processReviewCount"],
            item["averageRating"] if item["averageRating"] is not None else "",
            dist["1"], dist["2"], dist["3"], dist["4"], dist["5"],
            item["summaryScoredCount"],
            item["summaryAverageScore"] if item["summaryAverageScore"] is not None else "",
            item["lastReviewedAt"],
        ])
    content = xlsx_util.build_ledger_xlsx(
        "报告批阅绩效",
        headers,
        rows,
        watermark=(
            "跃科岗位实习管理平台 · 报告批阅绩效 · "
            f"{(user or {}).get('realName') or '系统'} · {datetime.now():%Y-%m-%d %H:%M}"
        ),
    )
    return xlsx_util.pack_xlsx_result(
        content, "岗位实习报告批阅绩效.xlsx", len(rows),
    )


def report_obligations(
    user: dict, batch_id, *, keyword: str = "", missing_only: bool = False,
    page: int = 1, page_size: int = 50, report_type=None, record_id=None, submitted_only: bool = False,
) -> dict:
    """Per-student required/submitted/approved truth from batch rules and formal report facts."""
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    page = max(1, int(page or 1))
    page_size = min(20000, max(1, int(page_size or 50)))
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        rules = rules_for_batch(db, batch.id)
        required = {
            "daily": int(rules.get("dailyRequiredCount") or 0),
            "weekly": int(rules.get("weeklyRequiredCount") or 0),
            "monthly": int(rules.get("monthlyRequiredCount") or 0),
            "summary": int(rules.get("summaryRequiredCount") or 0),
        }

        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        ).subquery()
        scoped_ids = select(scoped.c.id)

        # Count original submitted documents, never draft rows or resubmission snapshots.
        states = SUBMITTED_REPORT_STATUSES
        weekly = select(
            WeeklyReport.internship_id.label("record_id"),
            func.count(WeeklyReport.id).label("weeklySubmitted"),
            func.sum(case((WeeklyReport.status == "APPROVED", 1), else_=0)).label("weeklyApproved"),
        ).where(WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id.in_(scoped_ids),
            WeeklyReport.is_deleted.is_(False), WeeklyReport.status.in_(states)
        ).group_by(WeeklyReport.internship_id).subquery()
        process_columns = []
        for key, kind in (("daily", "DAILY"), ("monthly", "MONTHLY"), ("summary", "SUMMARY")):
            process_columns.extend([
                func.sum(case((InternshipProcessReport.report_type == kind, 1), else_=0)).label(key + "Submitted"),
                func.sum(case((and_(InternshipProcessReport.report_type == kind,
                    InternshipProcessReport.status == "APPROVED"), 1), else_=0)).label(key + "Approved"),
            ])
        process = select(InternshipProcessReport.internship_id.label("record_id"), *process_columns).where(
            InternshipProcessReport.tenant_id == _tid(), InternshipProcessReport.internship_id.in_(scoped_ids),
            InternshipProcessReport.is_deleted.is_(False), InternshipProcessReport.status.in_(states),
        ).group_by(InternshipProcessReport.internship_id).subquery()
        count_columns = []
        missing = {}
        for key in required:
            source = weekly if key == "weekly" else process
            submitted = func.coalesce(source.c[key + "Submitted"], 0)
            count_columns.extend([submitted.label(key + "Submitted"),
                func.coalesce(source.c[key + "Approved"], 0).label(key + "Approved")])
            missing[key] = case((submitted < required[key], required[key] - submitted), else_=0)
        query = select(InternshipRecord, StudentProfile, *count_columns).join(
            StudentProfile,
            StudentProfile.id == InternshipRecord.student_id,
        ).outerjoin(weekly, weekly.c.record_id == InternshipRecord.id
        ).outerjoin(process, process.c.record_id == InternshipRecord.id).where(
            InternshipRecord.id.in_(scoped_ids),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        term = str(keyword or "").strip()
        if term:
            query = query.where(or_(
                StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True),
                InternshipRecord.advisor_name.contains(term, autoescape=True),
                InternshipRecord.enterprise_name.contains(term, autoescape=True),
                InternshipRecord.position_name.contains(term, autoescape=True),
            ))
        key = str(report_type or "").lower()
        if key and key not in required:
            raise AppException("VALIDATION_ERROR", "请选择日报、周报、月报或实习总结")
        if submitted_only:
            if not key:
                raise AppException("VALIDATION_ERROR", "查看已交名单时请选择报告类型")
            source = weekly if key == "weekly" else process
            query = query.where(func.coalesce(source.c[key + "Submitted"], 0) > 0)
        if record_id is not None:
            query = query.where(InternshipRecord.id == int(record_id))
        if missing_only:
            query = query.where((missing[key] if key else sum(missing.values())) > 0)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        totals_source = query.subquery()
        totals_columns = []
        for name in required:
            submitted = totals_source.c[name + "Submitted"]
            totals_columns.extend([func.coalesce(func.sum(submitted), 0),
                func.coalesce(func.sum(totals_source.c[name + "Approved"]), 0),
                func.coalesce(func.sum(case((submitted < required[name], required[name] - submitted), else_=0)), 0)])
        totals = db.execute(select(*totals_columns)).one()
        summary = {name: {"required": required[name] * total, "submitted": int(totals[i * 3]),
            "approved": int(totals[i * 3 + 1]), "missing": int(totals[i * 3 + 2]) if required[name] else None,
            "configured": required[name] > 0} for i, name in enumerate(required)}
        record_rows = db.execute(query.order_by(StudentProfile.student_no, StudentProfile.id, InternshipRecord.id)
            .offset((page - 1) * page_size).limit(page_size)).all()

        def metric(required_count: int, fact: dict | None) -> dict:
            submitted = int((fact or {}).get("submitted") or 0)
            approved = int((fact or {}).get("approved") or 0)
            configured = required_count > 0
            missing = max(0, required_count - submitted) if configured else None
            return {
                "configured": configured,
                "required": required_count if configured else 0,
                "submitted": submitted,
                "approved": approved,
                "missing": missing,
            }

        items = []
        for record, student, *counts in record_rows:
            facts = {name: metric(required[name], {"submitted": counts[i * 2], "approved": counts[i * 2 + 1]})
                     for i, name in enumerate(required)}
            metrics = list(facts.values())
            configured = [item for item in metrics if item["configured"]]
            missing_total = sum(int(item["missing"] or 0) for item in configured)
            required_total = sum(int(item["required"]) for item in configured)
            submitted_against_required = sum(
                min(int(item["submitted"]), int(item["required"])) for item in configured
            )
            completion_rate = (
                round(submitted_against_required * 100.0 / required_total, 1)
                if required_total else None
            )
            status = (
                "UNCONFIGURED" if not configured
                else ("MISSING" if missing_total > 0 else "COMPLETE")
            )
            row = {
                "recordId": str(record.id),
                "studentId": str(student.id),
                "studentName": student.real_name or "-",
                "studentNo": student.student_no or "-",
                "advisorName": record.advisor_name or "",
                "companyName": record.enterprise_name or "",
                "positionName": record.position_name or "",
                **facts,
                "requiredTotal": required_total,
                "submittedAgainstRequired": submitted_against_required,
                "missingTotal": missing_total,
                "completionRate": completion_rate,
                "status": status,
                "statusLabel": {
                    "UNCONFIGURED": "应交数未配置",
                    "MISSING": "存在未交",
                    "COMPLETE": "已交齐",
                }[status],
            }
            items.append(row)
        return {
            "batchId": str(batch.id),
            "batchName": getattr(batch, "batch_name", "") or "",
            "rules": required,
            "items": items,
            "summary": summary,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "missingOnly": bool(missing_only),
            "definition": {
                "submitted": "按已提交原单计数，排除草稿及删除记录；退回修改仍属于已提交过，重交不另增篇数",
                "approved": "当前正式报告状态为已通过",
                "missing": "仅在批次应交数大于0时计算；0表示学校未配置，不伪造完成率",
            },
        }


def export_report_obligations(
    user: dict, batch_id, *, keyword: str = "", missing_only: bool = False, report_type=None,
) -> dict:
    from app.services import xlsx_util

    data = report_obligations(
        user, batch_id, keyword=keyword, missing_only=missing_only,
        page=1, page_size=20000, report_type=report_type,
    )
    if int(data.get("total") or 0) > len(data.get("items") or []):
        raise AppException(
            "VALIDATION_ERROR",
            "当前应交/未交台账超过 20000 行，请缩小数据范围后再导出",
        )
    headers = [
        "学号", "姓名", "指导教师", "企业", "岗位", "状态", "完成率",
        "日报应交", "日报实交", "日报已通过", "日报未交",
        "周报应交", "周报实交", "周报已通过", "周报未交",
        "月报应交", "月报实交", "月报已通过", "月报未交",
        "总结应交", "总结实交", "总结已通过", "总结未交",
        "总应交", "按应交口径已提交", "总未交",
    ]
    rows = []
    for item in data["items"]:
        values = []
        for key in ("daily", "weekly", "monthly", "summary"):
            metric = item[key]
            values.extend([
                metric["required"] if metric["configured"] else "未配置",
                metric["submitted"],
                metric["approved"],
                metric["missing"] if metric["configured"] else "未配置",
            ])
        rows.append([
            item["studentNo"], item["studentName"], item["advisorName"],
            item["companyName"], item["positionName"], item["statusLabel"],
            (str(item["completionRate"]) + "%") if item["completionRate"] is not None else "未配置",
            *values,
            item["requiredTotal"], item["submittedAgainstRequired"], item["missingTotal"],
        ])
    content = xlsx_util.build_ledger_xlsx(
        "报告应交未交",
        headers,
        rows,
        watermark=(
            "跃科岗位实习管理平台 · 报告应交/未交台账 · "
            f"{(user or {}).get('realName') or '系统'} · {datetime.now():%Y-%m-%d %H:%M}"
        ),
    )
    return xlsx_util.pack_xlsx_result(
        content, "岗位实习报告应交未交台账.xlsx", len(rows),
    )


def remind_report_obligation(user: dict, batch_id, record_id, report_type) -> dict:
    """Remind an actual missing obligation without creating a fake unsubmitted report."""
    from app.core.exceptions import not_found
    from app.models import InternshipAuditTrail
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.services import student_account_link_service as links
    from app.services.message_event_outbox_service import emit_receiver_notice, try_process_pending_outbox

    kinds = {"DAILY": ("dailyRequiredCount", "日报"), "WEEKLY": ("weeklyRequiredCount", "周报"),
             "MONTHLY": ("monthlyRequiredCount", "月报"), "SUMMARY": ("summaryRequiredCount", "实习总结")}
    kind = str(report_type or "").upper()
    if kind not in kinds:
        raise AppException("VALIDATION_ERROR", "请选择需要催交的报告类型")
    try:
        rid = int(record_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "学生实习记录编号不正确") from None
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=True)
        query = apply_internship_record_scope(select(InternshipRecord).where(
            InternshipRecord.id == rid, InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id, InternshipRecord.is_deleted.is_(False)), user)
        record = db.scalar(query.with_for_update())
        student = db.get(StudentProfile, record.student_id) if record else None
        if not record or not student or student.tenant_id != _tid() or student.is_deleted:
            raise not_found("当前批次或指导范围内没有该学生")
        rule_key, label = kinds[kind]
        required = int(rules_for_batch(db, batch.id)[rule_key])
        model = WeeklyReport if kind == "WEEKLY" else InternshipProcessReport
        count = select(func.count(model.id)).where(model.tenant_id == _tid(),
            model.internship_id == record.id, model.is_deleted.is_(False),
            model.status.in_(SUBMITTED_REPORT_STATUSES))
        if kind != "WEEKLY":
            count = count.where(model.report_type == kind)
        submitted = int(db.scalar(count) or 0)
        if required <= submitted:
            raise AppException("DATA_CONFLICT", "该类型没有缺交报告，无需催交")
        account = links.resolve_user_id_for_student(db, tenant_id=_tid(), student_id=student.id,
            student_no=student.student_no, require_active_account=True)
        if not account:
            raise AppException("DATA_NOT_FOUND", "学生没有有效绑定账号，未发送提醒")
        now = datetime.utcnow()
        action = "REMIND_" + kind
        recent = db.scalar(select(InternshipAuditTrail.id).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == record.id,
            InternshipAuditTrail.target_type == "REPORT_OBLIGATION", InternshipAuditTrail.action == action,
            InternshipAuditTrail.occurred_at >= now - timedelta(minutes=5)))
        if recent:
            raise AppException("DATA_CONFLICT", "5分钟内已催交，请稍后再试")
        event = emit_receiver_notice(db, event_code="INTERNSHIP.REPORT_REMIND", source_module="internship",
            source_biz_type="report_obligation", source_biz_id=record.id, receiver_id=account,
            receiver_as="user", title=f"{label}缺交提醒", content=f"实习批次「{batch.batch_name}」（编号{batch.id}）{label}应交{required}篇、已交{submitted}篇，请进入该批次的报告页面补交缺少的{required - submitted}篇。",
            dedup_extra=f"{kind}:{now:%Y%m%d%H%M%S%f}")
        db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=record.id, target_type="REPORT_OBLIGATION",
            action=action, operator_name=(user or {}).get("realName") or "系统", occurred_at=now,
            detail_json={"batchId": str(batch.id), "reportType": kind, "required": required,
                         "submitted": submitted, "missing": required - submitted, "eventId": str(event.id)}))
        event_id = int(event.id)
        db.commit()
        try_process_pending_outbox(worker_id="internship-report-reminder", outbox_ids=[event_id])
        return {"recordId": str(record.id), "reportType": kind, "missing": required - submitted,
                "queued": True, "message": "催交已登记，请在站内消息查看送达情况"}


def weekly_snapshot_view(db, report_id) -> dict:
    rows = db.scalars(select(InternshipReportVersion).where(
        InternshipReportVersion.tenant_id == _tid(),
        InternshipReportVersion.report_kind == "WEEKLY",
        InternshipReportVersion.report_id == int(report_id),
    ).order_by(InternshipReportVersion.version_no.desc())).all()
    reviews = db.scalars(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_kind == "WEEKLY",
        InternshipReportReview.report_id == int(report_id),
    ).order_by(InternshipReportReview.reviewed_at.desc())).all()
    by_version = {int(r.report_version_id): r for r in reviews}
    return {
        "versions": [{
            "id": str(v.id),
            "versionNo": int(v.version_no),
            "wordCount": int(v.word_count or 0),
            "content": v.content_json or {},
            "attachments": v.attachment_meta_json or [],
            "submittedAt": _iso(v.submitted_at) or "",
            "review": ({
                "action": by_version[v.id].action,
                "ratingLevel": by_version[v.id].rating_level,
                "comment": by_version[v.id].comment or "",
                "reviewerName": by_version[v.id].reviewer_name or "",
                "reviewedAt": _iso(by_version[v.id].reviewed_at) or "",
            } if v.id in by_version else None),
        } for v in rows],
    }


def record_weekly_review(db, *, row, action: str, comment: str, user: dict,
                         rating_level=None) -> InternshipReportReview:
    snap = latest_weekly_snapshot(db, row.id)
    if not snap:
        record = db.get(InternshipRecord, row.internship_id)
        if not record:
            raise AppException("DATA_CONFLICT", "周报关联实习记录不存在")
        # 兼容 ix0008 上线前已提交、尚未批阅的周报：以当前正式行建立基线快照。
        snap = append_weekly_snapshot(
            db,
            row=row,
            record=record,
            student=type("_StudentRef", (), {"id": record.student_id})(),
            content_json={
                "workContent": row.work_content or "",
                "harvestContent": row.harvest_content or "",
                "planContent": row.plan_content or "",
            },
            attachment_ids=[],
            attachment_meta=[],
        )
    if db.scalar(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_version_id == snap.id,
    )):
        raise AppException("DATA_CONFLICT", "当前周报版本已经批阅，请刷新后重试")

    rating = _rating(rating_level)
    if action == "APPROVE" and rating is None:
        raise AppException("VALIDATION_ERROR", "通过周报时必须选择五级评价")

    review = InternshipReportReview(
        tenant_id=_tid(),
        report_kind="WEEKLY",
        report_id=row.id,
        report_version_id=snap.id,
        action=action,
        rating_level=rating,
        summary_score=None,
        comment=(comment or "").strip() or None,
        reviewer_user_id=str((user or {}).get("userId") or (user or {}).get("id") or "") or None,
        reviewer_name=(user or {}).get("realName") or "系统",
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)
    db.flush()
    return review

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
            "submittedAt": _iso(v.submitted_at) or "",
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
                    "reviewedAt": _iso(by_version[v.id].reviewed_at) or "",
                } if v.id in by_version else None
            ),
        } for v in rows],
    }


def record_process_review(db, *, row, action: str, comment: str, user: dict,
                          rating_level=None, summary_score=None) -> InternshipReportReview:
    snap = latest_process_snapshot(db, row.id)
    if not snap:
        record = db.get(InternshipRecord, row.internship_id)
        if not record:
            raise AppException("DATA_CONFLICT", "报告关联实习记录不存在")
        # 兼容 ix0008 上线前已提交、尚未批阅的过程报告：当前正式行作为基线版本。
        snap = append_process_snapshot(
            db,
            row=row,
            record=record,
            student=type("_StudentRef", (), {"id": record.student_id})(),
            content=row.content or "",
            attachment_ids=[],
            attachment_meta=[],
        )
    if db.scalar(select(InternshipReportReview).where(
        InternshipReportReview.tenant_id == _tid(),
        InternshipReportReview.report_version_id == snap.id,
    )):
        raise AppException("DATA_CONFLICT", "当前报告版本已经批阅，请刷新后重试")

    rating = _rating(rating_level)

    score = None
    if summary_score not in (None, ""):
        try:
            if isinstance(summary_score, bool):
                raise ValueError
            score = float(summary_score)
        except (TypeError, ValueError, OverflowError):
            raise AppException("VALIDATION_ERROR", "总结评分必须是 0 到 100") from None
        if not isfinite(score) or score < 0 or score > 100:
            raise AppException("VALIDATION_ERROR", "总结评分必须是 0 到 100")
        if row.report_type != "SUMMARY":
            raise AppException("VALIDATION_ERROR", "只有实习总结允许填写 0 到 100 分")

    if action == "APPROVE" and row.report_type != "SUMMARY" and rating is None:
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

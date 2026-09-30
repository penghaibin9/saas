"""Atomic import, whole-package approval, durable unbounded publication queue.

Every mutation locks the same tiny dispatch row first. That establishes a single
lock order for concurrent uploads, approval, pause and worker publication. No
network/filesystem writes occur in the publish transaction.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session
from app.models.website_news import NewsPackage, NewsArticle, NewsMedia, NewsMediaLink, NewsDispatch, NewsAudit
from app.services.website_news.package import canonical, digest, CATEGORIES

class NewsError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status

def now():
    return datetime.utcnow()

def iso(value):
    return value.isoformat(timespec="seconds") + "Z" if value else None

def dispatch(db: Session):
    row = db.scalar(select(NewsDispatch).where(NewsDispatch.id == 1).with_for_update())
    if not row:
        raise NewsError("新闻表尚未迁移，请先完成数据库升级", 503)
    return row

def package(db, pid, locked=False):
    query = select(NewsPackage).where(NewsPackage.id == pid)
    row = db.scalar(query.with_for_update() if locked else query)
    if not row:
        raise NewsError("新闻包不存在", 404)
    return row

def audit(db, p, actor, action, detail=None, article=None, event_key=None):
    db.add(NewsAudit(id=uuid4().hex, event_key=event_key or uuid4().hex,
                     package_id=p.id, article_id=article, actor=str(actor)[:64],
                     action=action, detail=detail or {}, created_at=now()))

def import_package(db, parsed, filename, actor):
    dispatch(db)
    previous = db.scalar(select(NewsPackage).where(NewsPackage.sha256 == parsed["sha256"]))
    if previous:
        return previous, True
    p = NewsPackage(id=uuid4().hex, sha256=parsed["sha256"], title=parsed["title"],
                    filename=filename[:200], imported_by=str(actor)[:64],
                    review_digest=parsed["review_digest"], state="REVIEW", version=0)
    db.add(p); db.flush()
    seen = set()
    # Check in bounded chunks; SQL IN remains comfortably below packet limits.
    candidates = [r["dedupe_key"] for r in parsed["articles"] if r["dedupe_key"]]
    for start in range(0, len(candidates), 400):
        seen.update(db.scalars(select(NewsArticle.dedupe_key).where(NewsArticle.dedupe_key.in_(candidates[start:start+400]))))
    needed_media = set()
    media_links = []
    for data in parsed["articles"]:
        row = dict(data)
        if row["dedupe_key"] in seen:
            row.update(state="DUPLICATE", issue="与包内或历史新闻正文重复，已自动跳过", dedupe_key=None)
        elif row["dedupe_key"]:
            seen.add(row["dedupe_key"])
        if row["state"] == "READY":
            needed_media.update(row["media_map"].values())
        aid = uuid4().hex
        db.add(NewsArticle(id=aid, package_id=p.id, slug="news-" + aid, updated_at=now(), **row))
        if row["state"] == "READY":
            media_links.extend((aid, mid) for mid in set(row["media_map"].values()))
    for media in parsed["assets"].values():
        if media["id"] in needed_media and not db.get(NewsMedia, media["id"]):
            db.add(NewsMedia(**media)); db.flush()
    db.flush()
    for aid, mid in media_links:
        db.add(NewsMediaLink(article_id=aid, media_id=mid))
    audit(db, p, actor, "IMPORT", {"sha256": p.sha256, "count": len(parsed["articles"])})
    db.flush()
    return p, False

def summary(db, p):
    counts = dict(db.execute(select(NewsArticle.state, func.count()).where(NewsArticle.package_id == p.id).group_by(NewsArticle.state)).all())
    first, last = db.execute(select(func.min(NewsArticle.scheduled_at), func.max(NewsArticle.scheduled_at)).where(NewsArticle.package_id == p.id)).one()
    return {"id": p.id, "title": p.title, "filename": p.filename, "state": p.state,
            "version": p.version, "reviewDigest": p.review_digest, "counts": counts,
            "total": sum(counts.values()), "createdAt": iso(p.created_at),
            "reviewedAt": iso(p.reviewed_at), "reviewedBy": p.reviewed_by,
            "scheduledStart": iso(first), "scheduledEnd": iso(last)}

def article_data(a, full=False):
    result = {"id": a.id, "ordinal": a.ordinal, "title": a.title, "summary": a.summary,
              "category": a.category, "categoryName": CATEGORIES.get(a.category, a.category),
              "state": a.state, "issue": a.issue, "url": "/news/" + a.slug,
              "scheduledAt": iso(a.scheduled_at), "publishedAt": iso(a.published_at),
              "coverUrl": "/news/media/" + a.cover_id if a.cover_id else None}
    if full:
        result.update(body=a.body, sources=a.sources, aiAssisted=a.ai_assisted, contentKind=a.content_kind)
    return result

def get_health(db):
    row = db.get(NewsDispatch, 1)
    active = bool(row and row.heartbeat_at and (now() - row.heartbeat_at).total_seconds() < 90)
    return {"running": active, "heartbeatAt": iso(row.heartbeat_at) if row else None,
            "message": "发布服务运行中" if active else "发布服务未就绪：计划会保存，服务恢复后继续，不会丢稿",
            "dailyLimit": None, "intervalMinutes": 3}

def approve(db, pid, actor, expected_version, review_digest, excluded_ids, interval_minutes=3):
    if not isinstance(expected_version, int) or isinstance(expected_version, bool):
        raise NewsError("请刷新新闻包再确认", 400)
    if not isinstance(interval_minutes, int) or isinstance(interval_minutes, bool) or not 1 <= interval_minutes <= 60:
        raise NewsError("发布间隔须为 1—60 分钟", 400)
    gate = dispatch(db)
    p = package(db, pid, True)
    signature = digest(canonical({"digest": review_digest, "excluded": sorted(set(excluded_ids)), "interval": interval_minutes}))
    if p.approval_signature == signature:
        return p, True  # Lost HTTP response / double-click: never re-schedule.
    if p.state != "REVIEW" or p.version != expected_version or p.review_digest != review_digest:
        raise NewsError("新闻包已变化或已审核，请刷新后确认")
    rows = list(db.scalars(select(NewsArticle).where(NewsArticle.package_id == pid).order_by(NewsArticle.ordinal)))
    known = {a.id for a in rows}
    if not set(excluded_ids) <= known:
        raise NewsError("待排除文章不属于当前新闻包", 400)
    eligible = [a for a in rows if a.state == "READY" and a.id not in excluded_ids]
    if not eligible:
        raise NewsError("没有可发布文章，请修复问题稿或上传新包", 400)
    current = now()
    slot = max(current + timedelta(seconds=30), gate.next_slot or current)
    for a in rows:
        if a.state != "READY":
            continue
        if a.id in excluded_ids:
            a.state = "EXCLUDED"
            a.issue = "审核时由运营人员排除"
            continue
        a.state, a.scheduled_at = "SCHEDULED", slot
        slot += timedelta(minutes=interval_minutes)
    gate.next_slot = slot
    p.state, p.reviewed_at, p.reviewed_by = "QUEUED", current, str(actor)[:64]
    p.version += 1
    p.approval_signature = signature
    audit(db, p, actor, "APPROVE_ALL", {"count": len(eligible), "excludedIds": sorted(set(excluded_ids)),
                                         "reviewDigest": review_digest, "intervalMinutes": interval_minutes,
                                         "lastSlot": iso(slot - timedelta(minutes=interval_minutes))})
    db.flush()
    return p, False

def control(db, pid, actor, expected_version, action):
    gate = dispatch(db)
    p = package(db, pid, True)
    if p.version != expected_version:
        raise NewsError("操作版本已变化，请刷新")
    if action == "pause" and p.state == "QUEUED":
        p.state = "PAUSED"
    elif action == "resume" and p.state == "PAUSED":
        rows = list(db.scalars(select(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state == "SCHEDULED").order_by(NewsArticle.ordinal)))
        slot = max(now() + timedelta(seconds=30), gate.next_slot or now())
        approval = db.scalar(select(NewsAudit).where(NewsAudit.package_id == pid, NewsAudit.action == "APPROVE_ALL").order_by(NewsAudit.created_at.desc()).limit(1))
        interval = int((approval.detail if approval else {}).get("intervalMinutes", 3))
        for a in rows:
            a.scheduled_at = slot; slot += timedelta(minutes=interval)
        gate.next_slot = slot
        p.state = "QUEUED" if rows else "COMPLETE"
    elif action == "cancel" and p.state in ("REVIEW", "QUEUED", "PAUSED"):
        for a in db.scalars(select(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state.in_(["READY", "SCHEDULED"]))):
            a.state = "EXCLUDED"; a.issue = "运营人员取消未发布新闻"
        p.state = "CANCELLED"
    else:
        raise NewsError("当前状态不支持此操作")
    p.version += 1
    audit(db, p, actor, action.upper())
    db.flush()
    return p

def withdraw(db, aid, actor):
    dispatch(db)
    a = db.get(NewsArticle, aid)
    if not a:
        raise NewsError("文章不存在", 404)
    if a.state == "WITHDRAWN":
        return a
    if a.state != "PUBLISHED":
        raise NewsError("只能下架已发布文章")
    p = package(db, a.package_id, True)
    a.state, a.updated_at = "WITHDRAWN", now()
    p.version += 1
    audit(db, p, actor, "WITHDRAW", article=aid)
    return a

def publish_due(db, at=None, chunk_size=50):
    # Called repeatedly by a persistent worker. 50 is a transaction size, NOT a daily quota.
    gate = dispatch(db)
    at = at or now()
    gate.heartbeat_at, gate.last_error = now(), ""
    rows = list(db.scalars(select(NewsArticle).join(NewsPackage, NewsArticle.package_id == NewsPackage.id).where(
        NewsArticle.state == "SCHEDULED", NewsArticle.scheduled_at <= at,
        NewsPackage.state == "QUEUED", NewsPackage.reviewed_at.is_not(None),
        NewsPackage.approval_signature.is_not(None)).order_by(NewsArticle.scheduled_at, NewsArticle.id).limit(min(max(chunk_size, 1), 200))))
    touched = {}
    for a in rows:
        p = touched.setdefault(a.package_id, package(db, a.package_id))
        a.state, a.published_at, a.updated_at = "PUBLISHED", at, at
        audit(db, p, "website-news-worker", "PUBLISH", {"scheduledAt": iso(a.scheduled_at)},
              article=a.id, event_key="PUBLISH:" + a.id)
    db.flush()
    for pid, p in touched.items():
        pending = db.scalar(select(func.count()).select_from(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state == "SCHEDULED"))
        if not pending:
            p.state = "COMPLETE"; p.version += 1
            audit(db, p, "website-news-worker", "COMPLETE")
    return len(rows)

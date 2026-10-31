"""Atomic import, whole-package approval, durable unbounded publication queue.

Every mutation locks the same tiny dispatch row first. That establishes a single
lock order for concurrent uploads, approval, pause and worker publication. No
network/filesystem writes occur in the publish transaction.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import select, func, exists, delete
from sqlalchemy.orm import Session
from website_app.news.models import NewsPackage, NewsArticle, NewsRevision, NewsMedia, NewsMediaLink, NewsDispatch, NewsAudit
from website_app.news.package import canonical, digest, CATEGORIES

METADATA_FIELDS = {'sourceType':'source_type','authorName':'author_name','editorName':'editor_name',
    'rightsBasis':'rights_basis','rightsScope':'rights_scope','rightsEvidence':'rights_evidence',
    'rightsValidUntil':'rights_valid_until','relatedProducts':'related_products'}
CONTENT_FIELDS = ('title','summary','body','category','sources','media_map','cover_id','ai_assisted','content_kind', *METADATA_FIELDS.values())
STATES = {'DRAFT':'草稿','SUBMITTED':'待审核','RETURNED':'已退回','APPROVED':'已批准，待排期',
    'READY':'校验通过','INVALID':'资料待补齐','DUPLICATE':'重复稿','SCHEDULED':'待发布','PUBLISHED':'已发布',
    'WITHDRAWN':'已下架','PAUSED':'已暂停','CANCELLED':'已取消','APPLIED':'修订已发布',
    'BASELINE':'原公开版本','LEGACY':'原有稿件，待核对','EXCLUDED':'已排除','FAILED':'发布异常，待处理'}
ACTIONS = {'IMPORT':'导入稿件','CREATE_DRAFT':'保存草稿','EDIT_DRAFT':'修改草稿','SUBMIT':'提交审核',
    'RETURN':'退回修改','APPROVE':'批准版本','SCHEDULE':'安排发布','PUBLISH':'发布文章',
    'WITHDRAW':'下架文章','RESTORE':'恢复发布','CREATE_REVISION':'创建修订','APPLY_REVISION':'发布修订','UPLOAD_MEDIA':'上传配图','SET_COVER':'选择封面',
    'PAUSE':'暂停排期','RESUME':'恢复排期','CANCEL':'取消排期','COMPLETE':'发布完成','PUBLISH_FAILED':'发布校验失败','APPROVE_ALL':'审核批量发布','EXPORT_LEDGER':'导出台账'}

def product_catalog():
    import json
    from pathlib import Path
    config = json.loads((Path(__file__).resolve().parents[3] / 'products.json').read_text(encoding='utf-8'))
    result = {p['key']:p for p in config['products'] if p.get('public')}
    for key,name in [('academic-affairs','教务系统'),('student-affairs','学工中心'),('graduation','毕业设计')]:
        result[key] = {'key':key,'name':name,'domain':'teaching','path':'/products/'+key,'public':True}
    return result

def content_digest(a):
    data = {key: iso(getattr(a,key)) if key == 'rights_valid_until' else getattr(a,key) for key in CONTENT_FIELDS}
    return digest(canonical(data))

def redigest(db, p):
    db.flush()
    rows = db.scalars(select(NewsArticle).where(NewsArticle.package_id == p.id).order_by(NewsArticle.ordinal))
    p.review_digest = digest(canonical([article_data(a,full=True) for a in rows]))

def rights_check(a, at=None):
    if a.source_type not in ('original','licensed-repost'): raise NewsError('须先核对稿件是原创还是有授权转载',400)
    if len(a.author_name.strip()) < 2 or len(a.editor_name.strip()) < 2: raise NewsError('请填写真实作者／原发布方和负责编辑',400)
    if len(a.rights_basis.strip()) < 8 or len(a.rights_scope.strip()) < 8: raise NewsError('请说明正文及配图的使用依据和范围，来源链接不等于授权',400)
    if a.source_type == 'licensed-repost' and len(a.rights_evidence.strip()) < 10: raise NewsError('转载缺少可核验的授权凭证说明，不能批准发布',400)
    if a.rights_valid_until and a.rights_valid_until <= (at or now()): raise NewsError('使用授权已经到期，不能发布',400)
    if not set(a.related_products) <= set(product_catalog()): raise NewsError('关联产品尚无已确认公开资料',400)

def sync_media_links(db,a):
    db.execute(delete(NewsMediaLink).where(NewsMediaLink.article_id == a.id))
    stored=set(db.scalars(select(NewsMedia.id).where(NewsMedia.id.in_(set(a.media_map.values())))))
    for mid in stored: db.add(NewsMediaLink(article_id=a.id,media_id=mid))

def editable_target(db,a,revision_id=None):
    if revision_id:
        row = db.get(NewsRevision,revision_id)
        if not row or row.article_id != a.id: raise NewsError('修订不属于这篇文章',404)
        if row.editorial_state in ('BASELINE','APPLIED'): raise NewsError('历史公开版本不能覆盖')
        if a.state != 'PUBLISHED': raise NewsError('原文已经下架，不能继续发布修订')
        return row
    if a.state in ('PUBLISHED','WITHDRAWN'): raise NewsError('已发布正文须先创建修订，不能直接覆盖')
    return a

def locked_target(db,aid,version,revision_id=None):
    dispatch(db)
    a = db.get(NewsArticle,aid)
    if not a: raise NewsError('文章不存在',404)
    p = package(db,a.package_id,True)
    if p.version != version: raise NewsError('内容已变化，请核对最新版本；你的输入不会被自动覆盖')
    return p, editable_target(db,a,revision_id)

def set_cover(db, aid, body, actor):
    p, a = locked_target(db, aid, body.expectedVersion, body.revisionId)
    if a.editorial_state not in ('DRAFT', 'RETURNED', 'APPROVED'):
        raise NewsError('请先返回草稿，再调整封面')
    if body.mediaId and (body.mediaId not in set(a.media_map.values()) or not db.get(NewsMedia, body.mediaId)):
        raise NewsError('封面只能选择本稿已经保存的配图', 400)
    if a.cover_id == body.mediaId: return p, a
    a.cover_id = body.mediaId
    a.editorial_state, a.approved_digest, a.updated_at = 'DRAFT', None, now()
    p.version += 1
    redigest(db, p)
    audit(db, p, actor, 'SET_COVER', {'mediaId': body.mediaId, 'revisionId': body.revisionId}, article=aid)
    db.flush()
    return p, a

def validate_ready(db,a):
    from website_app.news.editor import Draft, normalized
    from pydantic import ValidationError
    payload = {key:getattr(a,field) for key,field in METADATA_FIELDS.items()}
    payload['rightsValidUntil'] = iso(a.rights_valid_until)
    try:
        body = Draft(title=a.title,summary=a.summary,body=a.body,category=a.category,
            contentKind=a.content_kind,aiAssisted=a.ai_assisted,sources=a.sources,**payload)
    except ValidationError as exc: raise NewsError('正文、来源或责任资料校验不通过，请补齐后重新提交',400) from exc
    available = set(db.scalars(select(NewsMedia.id).where(NewsMedia.id.in_(set(a.media_map.values())))))
    row = normalized(body,a,available)
    if row['state'] != 'READY': raise NewsError(row['issue'] or '稿件资料不完整',400)
    rights_check(a)
    duplicate = db.scalar(select(NewsArticle.id).where(NewsArticle.dedupe_key == row['dedupe_key'], NewsArticle.id != (a.article_id if isinstance(a,NewsRevision) else a.id)).limit(1))
    if duplicate: raise NewsError('正文与已有文章重复，不能发布',400)
    return row

def editorial_action(db,aid,body,actor,action):
    p,a = locked_target(db,aid,body.expectedVersion,body.revisionId)
    if action in ('schedule','resume') and p.state=='PAUSED':
        raise NewsError('本新闻包已整体暂停，请先在批量工作区明确恢复整包；单篇操作不会释放其他稿件',409)
    previous = a.editorial_state
    if action == 'submit' and previous in ('DRAFT','RETURNED'):
        validate_ready(db,a); a.editorial_state='SUBMITTED';a.review_reason=''
    elif action == 'return' and previous == 'SUBMITTED':
        if len(body.reason.strip()) < 4: raise NewsError('请填写具体退回原因',400)
        a.editorial_state='RETURNED';a.review_reason=body.reason.strip()
    elif action == 'approve' and previous == 'SUBMITTED':
        validate_ready(db,a)
        if body.reviewDigest != content_digest(a): raise NewsError('审核内容已变化，请重新查看本次版本')
        a.editorial_state='APPROVED';a.approved_digest=content_digest(a)
        p.reviewed_by,p.reviewed_at=str(actor)[:64],now()
    elif action == 'schedule' and previous == 'APPROVED':
        validate_ready(db,a)
        if a.approved_digest != content_digest(a): raise NewsError('批准后内容发生变化，须重新审核')
        if not body.publishAt: raise NewsError('请选择明确的发布时间',400)
        at=body.publishAt
        if at < now()-timedelta(seconds=10): raise NewsError('排期时间已过去，请重新选择',400)
        a.scheduled_at=max(at,now());a.editorial_state='SCHEDULED';a.state='SCHEDULED'
        p.state='QUEUED';p.approval_signature=a.approved_digest
    elif action == 'pause' and previous == 'SCHEDULED': a.editorial_state='PAUSED'
    elif action == 'resume' and previous == 'PAUSED':
        validate_ready(db,a)
        if a.approved_digest != content_digest(a): raise NewsError('暂停期间内容发生变化，须重新审核')
        a.editorial_state='SCHEDULED';p.state='QUEUED'
    elif action == 'cancel' and (previous in ('SUBMITTED','APPROVED','SCHEDULED','PAUSED','FAILED','LEGACY') or previous=='CANCELLED' and not isinstance(a,NewsRevision)):
        a.editorial_state='DRAFT';a.state='READY';a.scheduled_at=None;a.approved_digest=None
    else: raise NewsError('当前状态不支持本次操作')
    p.version+=1;a.updated_at=now()
    audit(db,p,actor,action.upper(),{'version':p.version,'contentDigest':content_digest(a),'reason':body.reason,
        'revisionId':a.id if isinstance(a,NewsRevision) else None,'scheduledAt':iso(a.scheduled_at)},article=aid)
    db.flush()
    return p,a

def create_revision(db,aid,version,actor):
    dispatch(db)
    a=db.get(NewsArticle,aid)
    if not a: raise NewsError('文章不存在',404)
    p=package(db,a.package_id,True)
    if p.version != version: raise NewsError('原文版本已经变化，请刷新核对')
    if a.state != 'PUBLISHED': raise NewsError('只能为已发布文章创建修订')
    pending=db.scalar(select(NewsRevision.id).where(NewsRevision.article_id==aid,NewsRevision.editorial_state.not_in(['BASELINE','APPLIED','CANCELLED'])).limit(1))
    if pending: raise NewsError('已有未完成修订，请继续原修订')
    highest=db.scalar(select(func.max(NewsRevision.number)).where(NewsRevision.article_id==aid))
    data={key:getattr(a,key) for key in CONTENT_FIELDS}
    if highest is None:
        db.add(NewsRevision(id=uuid4().hex,article_id=aid,number=0,base_digest=content_digest(a),
            state='PUBLISHED',issue='',editorial_state='BASELINE',applied_at=a.published_at,**data))
        highest=0
    row=NewsRevision(id=uuid4().hex,article_id=aid,number=highest+1,base_digest=content_digest(a),
        state='READY',issue='',editorial_state='DRAFT',**data)
    db.add(row);p.version+=1
    audit(db,p,actor,'CREATE_REVISION',{'revisionId':row.id,'number':row.number},article=aid)
    db.flush();return p,row

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
    revision = isinstance(a,NewsRevision)
    result = {"id": a.article_id if revision else a.id, "revisionId":a.id if revision else None,
              "ordinal": getattr(a,'ordinal',1), "title": a.title, "summary": a.summary,
              "category": a.category, "categoryName": CATEGORIES.get(a.category, a.category),
              "state": a.state, "issue": a.issue, "url": "/news/" + a.slug if not revision else None,
              "editorialState":a.editorial_state,"stateName":STATES.get(a.state,'待核对'),
              "editorialStateName":STATES.get(a.editorial_state,'待核对'),"reviewReason":a.review_reason,
              "contentDigest":content_digest(a),"relatedProducts":a.related_products,
              "sourceType":a.source_type,"authorName":a.author_name,"editorName":a.editor_name,
              "scheduledAt": iso(a.scheduled_at), "publishedAt": iso(getattr(a,'published_at',None)),
              "updatedAt":iso(a.updated_at),
              "coverUrl": "/news/media/" + a.cover_id if a.cover_id else None}
    if full:
        result.update(body=a.body, sources=a.sources, aiAssisted=a.ai_assisted, contentKind=a.content_kind)
        result.update({key:iso(getattr(a,field)) if field=='rights_valid_until' else getattr(a,field) for key,field in METADATA_FIELDS.items()})
    return result

def get_health(db):
    row = db.get(NewsDispatch, 1)
    active = bool(row and not row.last_error and row.heartbeat_at and (now() - row.heartbeat_at).total_seconds() < 90)
    return {"running": active, "heartbeatAt": iso(row.heartbeat_at) if row else None,
            "message": "发布服务运行中" if active else (row.last_error if row and row.last_error else "发布服务未就绪：计划会保存，服务恢复后继续，不会丢稿"),
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
    if p.filename == '网页撰写草稿': raise NewsError('日常撰写须先提交审核、批准版本，再选择发布时间',400)
    for a in eligible: rights_check(a)
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
        a.editorial_state='SCHEDULED';a.approved_digest=content_digest(a)
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
        if db.scalar(select(NewsArticle.id).where(NewsArticle.package_id==pid, NewsArticle.state=='SCHEDULED', NewsArticle.editorial_state=='LEGACY').limit(1)):
            raise NewsError('旧排期尚未核对责任与授权，请逐篇撤回草稿、补齐依据并重新审核后，再恢复整包')
        rows = list(db.scalars(select(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state == "SCHEDULED",NewsArticle.editorial_state=='SCHEDULED').order_by(NewsArticle.ordinal)))
        slot = max(now() + timedelta(seconds=30), gate.next_slot or now())
        approval = db.scalar(select(NewsAudit).where(NewsAudit.package_id == pid, NewsAudit.action == "APPROVE_ALL").order_by(NewsAudit.created_at.desc()).limit(1))
        interval = int((approval.detail if approval else {}).get("intervalMinutes", 3))
        for a in rows:
            if p.filename != '网页撰写草稿': a.scheduled_at = slot
            a.editorial_state='SCHEDULED';slot += timedelta(minutes=interval)
        gate.next_slot = slot
        p.state = 'QUEUED'
    elif action == "cancel" and p.state in ("REVIEW", "QUEUED", "PAUSED"):
        for a in db.scalars(select(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state.in_(["READY", "SCHEDULED"]))):
            a.state = "EXCLUDED";a.editorial_state='CANCELLED'; a.issue = "运营人员取消未发布新闻"
        for r in db.scalars(select(NewsRevision).join(NewsArticle,NewsRevision.article_id==NewsArticle.id).where(NewsArticle.package_id==pid,NewsRevision.editorial_state.in_(['SCHEDULED','PAUSED']))): r.editorial_state='CANCELLED'
        p.state = "CANCELLED"
    else:
        raise NewsError("当前状态不支持此操作")
    p.version += 1
    audit(db, p, actor, action.upper())
    db.flush()
    return p

def withdraw(db, aid, actor, reason='', expected_version=None):
    dispatch(db)
    a = db.get(NewsArticle, aid)
    if not a:
        raise NewsError("文章不存在", 404)
    if a.state == "WITHDRAWN":
        return a
    if a.state != "PUBLISHED":
        raise NewsError("只能下架已发布文章")
    p = package(db, a.package_id, True)
    if expected_version is not None and p.version != expected_version: raise NewsError('文章版本已经变化，请刷新核对')
    if len(reason.strip()) < 4: raise NewsError('请填写具体下架原因',400)
    a.state, a.updated_at = "WITHDRAWN", now()
    a.editorial_state='WITHDRAWN'
    for revision in db.scalars(select(NewsRevision).where(NewsRevision.article_id==aid,NewsRevision.editorial_state.in_(['SCHEDULED','PAUSED']))):
        revision.editorial_state='CANCELLED';revision.state='EXCLUDED';revision.review_reason=('原文已下架：'+reason)[:1000]
    p.version += 1
    audit(db, p, actor, "WITHDRAW", {'reason':reason,'version':p.version},article=aid)
    return a

def publish_due(db, at=None, chunk_size=50):
    # Called repeatedly by a persistent worker. 50 is a transaction size, NOT a daily quota.
    gate = dispatch(db)
    at = at or now()
    gate.heartbeat_at, gate.last_error = now(), ""
    rows = list(db.scalars(select(NewsArticle).join(NewsPackage, NewsArticle.package_id == NewsPackage.id).where(
        NewsArticle.state == "SCHEDULED", NewsArticle.scheduled_at <= at,
        NewsPackage.state == "QUEUED", NewsPackage.reviewed_at.is_not(None),
        NewsPackage.approval_signature.is_not(None),NewsArticle.editorial_state=='SCHEDULED').order_by(NewsArticle.scheduled_at, NewsArticle.id).limit(min(max(chunk_size, 1), 200))))
    touched = {};count=0
    for a in rows:
        p = touched.setdefault(a.package_id, package(db, a.package_id))
        try:
            rights_check(a,at)
            if a.approved_digest != content_digest(a): raise NewsError('待发布版本与批准版本不一致，须重新审核')
        except NewsError as exc:
            a.editorial_state='FAILED';a.issue=str(exc)
            audit(db,p,'website-news-worker','PUBLISH_FAILED',{'reason':str(exc)},article=a.id)
            continue
        a.state, a.published_at, a.updated_at = "PUBLISHED", a.published_at or at, at
        a.editorial_state='PUBLISHED'
        count+=1
        audit(db, p, "website-news-worker", "PUBLISH", {"scheduledAt": iso(a.scheduled_at)},
              article=a.id, event_key="PUBLISH:" + a.id + ':' + str(p.version))
    revisions=list(db.scalars(select(NewsRevision).join(NewsArticle,NewsRevision.article_id==NewsArticle.id).join(NewsPackage,NewsArticle.package_id==NewsPackage.id).where(
        NewsRevision.editorial_state=='SCHEDULED',NewsRevision.scheduled_at<=at,NewsPackage.state=='QUEUED').order_by(NewsRevision.scheduled_at,NewsRevision.id).limit(min(max(chunk_size,1),200))))
    for row in revisions:
        a=db.get(NewsArticle,row.article_id);p=touched.setdefault(a.package_id,package(db,a.package_id))
        try:
            if a.state != 'PUBLISHED' or content_digest(a) != row.base_digest: raise NewsError('原公开版本已经变化，须重新建立修订')
            rights_check(row,at)
            if row.approved_digest != content_digest(row): raise NewsError('修订与批准版本不一致，须重新审核')
            validated=validate_ready(db,row)
        except NewsError as exc:
            row.editorial_state='FAILED';row.issue=str(exc)
            audit(db,p,'website-news-worker','PUBLISH_FAILED',{'reason':str(exc),'revisionId':row.id},article=a.id)
            continue
        for key in CONTENT_FIELDS: setattr(a,key,getattr(row,key))
        a.dedupe_key=validated['dedupe_key'];a.updated_at=at
        a.approved_digest=row.approved_digest
        sync_media_links(db,a)
        row.editorial_state='APPLIED';row.state='APPLIED';row.applied_at=at
        count+=1
        audit(db,p,'website-news-worker','APPLY_REVISION',{'revisionId':row.id,'number':row.number},article=a.id,event_key='APPLY_REVISION:'+row.id)
    db.flush()
    for pid, p in touched.items():
        p.version+=1
        redigest(db,p)
        pending = db.scalar(select(func.count()).select_from(NewsArticle).where(NewsArticle.package_id == pid, NewsArticle.state == "SCHEDULED"))
        pending_revisions=db.scalar(select(func.count()).select_from(NewsRevision).join(NewsArticle,NewsRevision.article_id==NewsArticle.id).where(NewsArticle.package_id==pid,NewsRevision.editorial_state.in_(['SCHEDULED','PAUSED'])))
        if not pending and not pending_revisions:
            p.state = "COMPLETE"
            audit(db, p, "website-news-worker", "COMPLETE")
    return count

def restore(db,aid,body,actor):
    dispatch(db)
    a=db.get(NewsArticle,aid)
    if not a: raise NewsError('文章不存在',404)
    p=package(db,a.package_id,True)
    if p.version!=body.expectedVersion or a.state!='WITHDRAWN': raise NewsError('文章状态或版本已经变化，请刷新核对')
    if p.state=='PAUSED': raise NewsError('本新闻包已整体暂停，请先明确恢复整包后再恢复这篇文章',409)
    validate_ready(db,a)
    if body.reviewDigest!=content_digest(a) or a.approved_digest!=content_digest(a): raise NewsError('原批准内容已经变化，不能恢复旧版本')
    if not body.publishAt or body.publishAt<now()-timedelta(seconds=10): raise NewsError('请选择有效的恢复发布时间',400)
    a.state='SCHEDULED';a.editorial_state='SCHEDULED';a.scheduled_at=max(body.publishAt,now())
    p.state='QUEUED';p.version+=1;p.approval_signature=a.approved_digest
    audit(db,p,actor,'RESTORE',{'reason':body.reason,'contentDigest':content_digest(a),'scheduledAt':iso(a.scheduled_at),'version':p.version},article=aid)
    db.flush();return p,a

"""Bounded plan picker using the same tenant/cohort authorization as plan export."""
from sqlalchemy import and_, or_, select
from app.core.exceptions import AppException
from app.core.permissions import enforce_permission
from app.models import InternshipBatch, InternshipBatchPlan
from app.modules.internship.services.internship_plan_service import _assert_plan_batch_scope
from app.services.db_service import _tid, session


def list_options(user, *, page=1, page_size=20, keyword=''):
    enforce_permission(user or {}, 'internship.plan.view')
    if type(page) is not int or not 1 <= page <= 100000:
        raise AppException('VALIDATION_ERROR', '分页参数无效')
    if type(page_size) is not int or not 1 <= page_size <= 50:
        raise AppException('VALIDATION_ERROR', '每页最多50份计划')
    keyword = str(keyword or '').strip()
    if len(keyword) > 100:
        raise AppException('VALIDATION_ERROR', '检索条件不能超过100字')
    with session() as db:
        query = select(InternshipBatchPlan, InternshipBatch).join(InternshipBatch, and_(
            InternshipBatch.id == InternshipBatchPlan.batch_id,
            InternshipBatch.tenant_id == InternshipBatchPlan.tenant_id,
        )).where(InternshipBatchPlan.tenant_id == _tid(),
                 InternshipBatchPlan.is_deleted.is_(False),
                 InternshipBatch.is_deleted.is_(False),
                 InternshipBatch.status != 'VOIDED')
        if keyword:
            query = query.where(or_(InternshipBatchPlan.title.contains(keyword, autoescape=True),
                                   InternshipBatchPlan.plan_no.contains(keyword, autoescape=True),
                                   InternshipBatch.batch_name.contains(keyword, autoescape=True)))
        candidates = db.execute(query.order_by(InternshipBatchPlan.id.desc())
                                .offset((page - 1) * page_size).limit(page_size + 1)).all()
        items = []
        for plan, batch in candidates[:page_size]:
            try:
                _assert_plan_batch_scope(db, batch, user, '选择待导出计划')
            except AppException as exc:
                if exc.http_status != 403:
                    raise
                continue
            items.append({'id': str(batch.id), 'planId': str(plan.id),
                          'batchName': batch.batch_name or '', 'planTitle': plan.title,
                          'planNo': plan.plan_no or '', 'planStatus': plan.status,
                          'majorName': plan.major_name or '', 'version': int(plan.version or 0)})
        # Do not expose unauthorized plan names or claim an accessible total from unfiltered rows.
        return {'items': items, 'page': page, 'pageSize': page_size,
                'hasMore': len(candidates) > page_size,
                'pageMayBeScopeFiltered': True}


def record_export(user, batch_ids, format_code, payload):
    """Persist the export receipt before any file bytes are released to the caller."""
    import base64
    from hashlib import sha256
    from sqlalchemy.exc import SQLAlchemyError
    from app.modules.internship.services.internship_audit_service import add_audit
    content = base64.b64decode(payload['contentBase64'], validate=True)
    ids = list(dict.fromkeys(str(int(value)) for value in batch_ids))
    detail = {'format':format_code,'batchIds':ids,'planCount':len(ids),
              'fileSha256':sha256(content).hexdigest(),'byteCount':len(content)}
    try:
        with session() as db:
            event_id = add_audit(db, target_type='PLAN_EXPORT',target_id=int(ids[0]),
                action='PLAN_BULK_EXPORT',user=user,detail=detail)
            db.commit()
    except SQLAlchemyError as exc:
        raise AppException('AUDIT_UNAVAILABLE','导出审计暂不可写入，未发放文件，请稍后重试',http_status=503) from exc
    return {**payload,'auditEventId':event_id}

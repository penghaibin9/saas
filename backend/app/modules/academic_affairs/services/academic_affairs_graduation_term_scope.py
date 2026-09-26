"""毕业批次的显式学期归属；历史空关联仅按原发生日期兼容读取。"""
from __future__ import annotations

import re
from datetime import datetime, time

from sqlalchemy import and_, false, or_

from app.core.exceptions import AppException
from app.services.db_service import _tid


def term_bounds(term):
    start = getattr(term, "start_date", None)
    end = getattr(term, "end_date", None)
    if not start or not end:
        return None, None
    return (
        datetime.combine(start.date() if isinstance(start, datetime) else start, time.min),
        datetime.combine(end.date() if isinstance(end, datetime) else end, time.max),
    )


def batch_term_condition(term):
    """同租户、未删除批次：显式学期优先，空关联才启用时间兼容。"""
    from app.models import AaGraduationAuditBatch

    if not term or not getattr(term, "id", None) or not getattr(term, "tenant_id", None):
        return false()
    start, end = term_bounds(term)
    legacy = and_(
        AaGraduationAuditBatch.term_id.is_(None),
        or_(
            and_(AaGraduationAuditBatch.generate_at >= start, AaGraduationAuditBatch.generate_at <= end),
            and_(AaGraduationAuditBatch.generate_at.is_(None),
                 AaGraduationAuditBatch.created_at >= start, AaGraduationAuditBatch.created_at <= end),
        ),
    ) if start and end else false()
    return and_(
        AaGraduationAuditBatch.tenant_id == int(term.tenant_id),
        AaGraduationAuditBatch.is_deleted.is_(False),
        or_(AaGraduationAuditBatch.term_id == int(term.id), legacy),
    )


def require_creation_term(db, raw_term_id):
    from .academic_affairs_schedule_resource_guard import lock_term

    if (not isinstance(raw_term_id, str)
            or not re.fullmatch(r"[1-9][0-9]{0,18}", raw_term_id)
            or int(raw_term_id) > 9223372036854775807):
        raise AppException("VALIDATION_ERROR", "必须选择有效学期，学期编号须为正整数字符串")
    # 与封存共用现有学期行锁；当前读刷新 Session 中可能缓存的未封存状态。
    return lock_term(db, int(raw_term_id))


def batch_term_names(db, batches):
    """一次读取本页实际关联学期；历史批次不猜测正式学期名称。"""
    from app.models import AaTerm

    ids = {int(batch.term_id) for batch in batches if getattr(batch, "term_id", None)}
    if not ids:
        return {}
    return {int(row.id): row.term_name for row in db.query(AaTerm).filter(
        AaTerm.tenant_id == _tid(), AaTerm.id.in_(ids), AaTerm.is_deleted.is_(False),
    ).all()}


def guard_batch_term_writable(db, batch_id):
    """所有普通毕业写命令共用；历史空关联不根据日期猜测写入权限。"""
    from app.models import AaGraduationAuditBatch
    from .academic_affairs_archive_core_service import guard_term_writable

    query = db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.id == int(batch_id),
        AaGraduationAuditBatch.tenant_id == _tid(), AaGraduationAuditBatch.is_deleted.is_(False),
    )
    batch = query.first()
    if not batch:
        raise AppException("DATA_NOT_FOUND", "预审批次不存在", http_status=404)
    term_id = batch.term_id
    if term_id is not None:
        term = require_creation_term(db, str(term_id))
        guard_term_writable(db, term.id)
    # 预读只定位学期；状态必须在学期→批次的固定锁序下重新核验。
    batch = query.populate_existing().with_for_update().first()
    if not batch or batch.term_id != term_id:
        raise AppException("DATA_CONFLICT", "毕业批次归属已变化，请重新读取后办理", http_status=409)
    if batch.status == "ARCHIVED":
        raise AppException("IDEMPOTENCY_CONFLICT", "该毕业批次已归档，请使用归档后纠错流程", http_status=409)
    return batch


def guard_result_term_writable(db, result_id):
    """预读仅取批次位置，锁序始终为学期→批次→结果。"""
    from app.models import AaGraduationAuditResult

    query = db.query(AaGraduationAuditResult).filter(
        AaGraduationAuditResult.id == int(result_id),
        AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.is_deleted.is_(False),
    )
    result = query.first()
    if not result:
        raise AppException("DATA_NOT_FOUND", "预审结果不存在", http_status=404)
    batch = guard_batch_term_writable(db, result.batch_id)
    result = query.populate_existing().with_for_update().first()
    if not result or result.batch_id != batch.id:
        raise AppException("DATA_CONFLICT", "毕业结果归属已变化，请重新读取后办理", http_status=409)
    return result

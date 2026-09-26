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
    from app.models import AaTerm

    if (not isinstance(raw_term_id, str)
            or not re.fullmatch(r"[1-9][0-9]{0,18}", raw_term_id)
            or int(raw_term_id) > 9223372036854775807):
        raise AppException("VALIDATION_ERROR", "必须选择有效学期，学期编号须为正整数字符串")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(raw_term_id), AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise AppException("DATA_NOT_FOUND", "学期不存在或当前学校不可访问", http_status=404)
    return term


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

    batch = db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.id == int(batch_id),
        AaGraduationAuditBatch.tenant_id == _tid(), AaGraduationAuditBatch.is_deleted.is_(False),
    ).first()
    if not batch:
        raise AppException("DATA_NOT_FOUND", "预审批次不存在", http_status=404)
    if batch.term_id is not None:
        term = require_creation_term(db, str(batch.term_id))
        guard_term_writable(db, term.id)
    return batch

"""V2-02 教学班管理写动作最终层。"""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_query_service as _base


def __getattr__(name):
    return getattr(_base, name)


def backfill_teaching_classes(user, term_id: int, dry_run=True, reason=""):
    reason_text = (reason or "").strip()
    if not dry_run and len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "执行教学班回填必须填写不少于5字的原因")

    result = _base.backfill_teaching_classes(user, int(term_id), bool(dry_run))
    if dry_run:
        return result

    from app.models import AffairsAuditTrail
    ctx = get_current_user_ctx() or {}
    with session() as db:
        db.add(AffairsAuditTrail(
            tenant_id=_tid(),
            biz_type="AA_TEACHING_CLASS",
            biz_id=int(term_id),
            action="TEACHING_CLASS_BACKFILL",
            operator=str(ctx.get("userId") or ctx.get("loginName") or ""),
            role_name=str(ctx.get("currentRoleCode") or ""),
            detail=(
                f"termId={term_id};taskCount={result.get('taskCount', 0)};"
                f"readyCount={result.get('readyCount', 0)};reason={reason_text}"
            )[:990],
        ))
        db.commit()
    result["reason"] = reason_text
    result["audited"] = True
    return result

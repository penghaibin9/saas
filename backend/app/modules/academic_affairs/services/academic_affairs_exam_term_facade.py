"""考务服务学期写保护叠加层。

现有exam facade已统一名单、异常、结束和归档；本层只补“新建考务批次”必须绑定正式未封存学期，
防止归档后从新批次入口绕回写状态。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_exam_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def create_batch(user, body):
    import json

    from app.models import AaExamBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    term_id = getattr(body, "termId", None)
    if not term_id:
        raise AppException("VALIDATION_ERROR", "考务批次必须绑定正式学期termId")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        guard_term_writable(db, int(term_id))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        batch = AaExamBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=int(term_id),
            exam_type=getattr(body, "examType", None) or "FINAL",
            exam_week_start=getattr(body, "examWeekStart", None),
            exam_week_end=getattr(body, "examWeekEnd", None),
            college_scope_json=(
                json.dumps(body.collegeScope, ensure_ascii=False)
                if getattr(body, "collegeScope", None) else None
            ),
            status=_legacy._B_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_CREATE", f"建考试批次 {name}")
        db.commit()
        return _legacy._batch_dto(batch)


_legacy.create_batch = create_batch

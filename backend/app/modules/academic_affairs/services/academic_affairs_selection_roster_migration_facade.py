"""选课 LOCKED 名单人工调整与教学班名单版本原子同步（过渡入口）。

该文件不再覆盖其它模块函数；选课域收口时将 ``adjust_record`` 合并回公开 Selection Service 后删除。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_facade as _base
from . import academic_affairs_selection_roster_projection_service as roster_projection


def __getattr__(name):
    return getattr(_base, name)


def adjust_record(user, record_id, reason) -> dict:
    """LOCKED后人工退课：选课记录、容量、预计人数与新名单版本在同一事务完成。"""
    from app.models import AaSelectionCourse, AaSelectionRecord
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _base._legacy.session() as db:
        _base._legacy._require_manage_scope(_base._legacy._ctx(user, db))
        reason_text = str(reason or "").strip()
        if len(reason_text) < 5:
            raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == int(record_id),
            AaSelectionRecord.tenant_id == _base._legacy._tid(),
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update().first()
        if not record:
            raise not_found("选课记录不存在")
        if record.status != _base._legacy._REC_LOCKED:
            raise _base._legacy._invalid("仅 LOCKED 记录可人工调整")
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(record.selection_course_id),
            AaSelectionCourse.tenant_id == _base._legacy._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update().first()
        if not course:
            raise not_found("选课课程不存在")
        batch = _base._legacy._get_batch(db, int(record.batch_id))
        guard_term_writable(db, batch.term_id)
        if batch.status == _base._legacy._BATCH_ARCHIVED:
            raise AppException("DATA_CONFLICT", "选课批次已归档，只读不可调整", http_status=409)
        if batch.status != _base._legacy._BATCH_LOCKED:
            raise _base._legacy._invalid(f"仅LOCKED批次可人工调整，当前 {batch.status}")
        consumers = _base._roster_consumers(db, course)
        if consumers:
            raise AppException(
                "DATA_CONFLICT",
                "正式名单已被下游业务使用，不可直接退课：" + "、".join(consumers) + "。请走名单变更迁移流程。",
                details={"consumers": consumers}, http_status=409,
            )

        updated = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == record.id,
            AaSelectionRecord.tenant_id == _base._legacy._tid(),
            AaSelectionRecord.status == _base._legacy._REC_LOCKED,
        ).update({
            AaSelectionRecord.status: _base._legacy._REC_DROPPED,
            AaSelectionRecord.dropped_at: datetime.utcnow(),
            AaSelectionRecord.adjust_reason: reason_text,
        }, synchronize_session=False)
        if not updated:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "名单已被他人调整，请刷新", http_status=409)
        db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == course.id,
            AaSelectionCourse.tenant_id == _base._legacy._tid(),
            AaSelectionCourse.selected_count > 0,
        ).update({
            AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1,
        }, synchronize_session=False)
        db.flush()

        projection = roster_projection.project_selection_course_locked(
            db, int(course.id), reason=f"锁定名单人工退课：{reason_text}",
        )
        _base._legacy._audit(
            db, record.id, "SELECTION_RECORD_ADJUST",
            (
                f"人工调整退课：{reason_text};teachingClassId={projection['teachingClassId']};"
                f"rosterVersionId={projection['rosterVersionId']};members={projection['memberCount']}"
            ),
        )
        db.commit()
        return {
            "recordId": str(record.id),
            "status": _base._legacy._REC_DROPPED,
            "teachingClassId": projection["teachingClassId"],
            "rosterVersionId": projection["rosterVersionId"],
            "rosterVersionNo": projection["versionNo"],
            "memberCount": projection["memberCount"],
        }

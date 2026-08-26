"""Bridge legacy academic warning close into the unified affairs audit trail.

Teacher Mini still reaches ``app.services.academic_service.close_warning`` for the
compatibility warning projection.  The business state is authoritative in
``t_acad_warning``, but that legacy close path historically wrote only
``AcademicAuditTrail``.  Install this wrapper so the same transaction also writes
the canonical ``AffairsAuditTrail / ACAD_WARNING / CLOSE`` evidence consumed by
production audit gates.
"""
from __future__ import annotations


def install(module):
    current = getattr(module, "close_warning", None)
    if current is None or getattr(current, "_aa010_warning_close_audit_guard", False):
        return module

    original = current

    def close_warning(wid, result) -> dict:
        text = str(result or "").strip()
        if len(text) < 5:
            raise module.AppException("VALIDATION_ERROR", "关闭说明必填且不少于 5 字")

        with module.session() as db:
            warning = module._get_warn(db, wid)
            if warning.status == "CLOSED":
                raise module.AppException("DATA_CONFLICT", "该预警已关闭")

            before = warning.status
            warning.status = "CLOSED"
            warning.close_result = text
            warning.version += 1

            student = module._stu_of(db, warning.acad_student_id)
            if student:
                module._sync_student_warning(db, student)

            # Preserve the historical academic-domain trail for compatibility.
            module._audit(db, "WARNING", warning.id, "关闭预警", text, before, "CLOSED")

            # Use the canonical academic-affairs helpers in the *same transaction*:
            # close the unified counselor todo and append the cross-surface audit seal.
            from app.modules.academic_affairs.services import academic_affairs_warning_service as warning_service

            warning_service.mark_todos_done(db, warning.id)
            warning_service._audit(
                db,
                "ACAD_WARNING",
                warning.id,
                "CLOSE",
                text,
                before,
                "CLOSED",
            )
            db.commit()
            return {"id": str(warning.id)}

    close_warning._aa010_warning_close_audit_guard = True
    close_warning._aa010_original_close_warning = original
    module.close_warning = close_warning
    return module

"""Bridge legacy academic warning close into the unified affairs audit trail.

``app.services.academic_service.close_warning`` remains the single owner of the warning close
business command: validation, state transition, student aggregate refresh, todo completion and commit.
The compatibility domain already emits its historical ``AcademicAuditTrail`` through ``module._audit``
inside that transaction.  This guard wraps only that audit sink: when the legacy CLOSE event is written,
it appends the canonical ``AffairsAuditTrail / ACAD_WARNING / CLOSE`` evidence in the very same Session.

Keeping the bridge at the audit boundary avoids a second copy of the warning-close state machine while
preserving the production requirement that both audit trails commit atomically with the business row.
"""
from __future__ import annotations


_MARKER = "_aa010_warning_close_audit_guard"


def install(module):
    current = getattr(module, "_audit", None)
    if current is None or getattr(current, _MARKER, False):
        return module

    original = current

    def audit_with_warning_close(db, biz_type, biz_id, action, detail="", before="", after=""):
        # Preserve the historical academic-domain evidence exactly as before.
        result = original(db, biz_type, biz_id, action, detail, before, after)

        if str(biz_type or "").upper() == "WARNING" and str(action or "") == "关闭预警":
            # Import lazily to keep app.services.academic_service import order acyclic.
            from app.modules.academic_affairs.services import (
                academic_affairs_warning_service as warning_service,
            )

            # academic_service.close_warning already completes the unified todo in this same Session.
            # The canonical audit seal belongs here as an additional side effect of the existing audit
            # command; no warning state, version, student aggregate or transaction boundary is owned here.
            warning_service._audit(
                db,
                "ACAD_WARNING",
                biz_id,
                "CLOSE",
                detail,
                before,
                after,
            )
        return result

    setattr(audit_with_warning_close, _MARKER, True)
    audit_with_warning_close._aa010_original_academic_audit = original
    module._audit = audit_with_warning_close
    return module

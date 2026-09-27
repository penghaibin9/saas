"""A03 student-selection registration shim.

Student-facing HTTP facades intentionally live in their canonical surface packages:
``app.student_portal`` for PC and ``app.api.v1`` for mobile.  Keeping decorators out of the
staff-oriented ``app.modules.internship.routers`` inventory prevents student routes from silently
bypassing or polluting the staff permission-code gate.
"""
from app.api.v1.mobile_internship_selection import router as mobile_router
from app.student_portal.internship_selection_router import router as portal_router

__all__ = ["mobile_router", "portal_router"]

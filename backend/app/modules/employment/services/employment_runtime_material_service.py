"""Employment material approval authority for the production PC runtime.

The production PC has a long-standing closed-loop contract: approving the student's employment
supporting material also verifies the destination record. Teacher Miniapp V3 owns a separate
single-object verification workflow, but that new workflow must not silently change the existing
PC endpoint semantics. Keep the compatibility transition explicit in this authority instead of
letting the mobile service redefine the PC contract.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.modules.employment.services import employment_service as base
from app.modules.employment.services.employment_runtime_service import _assert_material
from app.services.db_service import session


def approve_material(mid, comment="", *, user: dict) -> dict:
    """Approve one PC material and preserve the canonical PC VERIFIED transition."""
    with session() as db:
        material, emp = _assert_material(db, mid, user)
        if material.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = material.status
        operator, _ = base._op()
        material.status = "APPROVED"
        material.reviewer = operator
        material.review_time = datetime.utcnow()
        material.version = int(material.version or 0) + 1
        emp.material_status = "APPROVED"
        # Compatibility contract: the existing production PC endpoint treats material approval
        # as the closed-loop verification decision. Teacher V3's dedicated verification endpoint
        # remains independent and must not weaken this established PC behavior.
        emp.verify_status = "VERIFIED"
        base._audit(db, "MATERIAL", material.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(material.id), "status": "APPROVED"}

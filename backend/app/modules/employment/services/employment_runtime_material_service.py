"""Employment material approval authority for the production PC runtime.

Material review and destination verification are intentionally separate facts. Approving a
supporting material may advance only the material status; destination verification is owned by
the dedicated employment verification flow.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.modules.employment.services import employment_service as base
from app.modules.employment.services.employment_runtime_service import _assert_material
from app.services.db_service import session


def approve_material(mid, comment="", *, user: dict) -> dict:
    """Approve one material without implicitly verifying the student's destination."""
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
        base._audit(db, "MATERIAL", material.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(material.id), "status": "APPROVED"}

"""Employment material-review authority separated from destination verification.

Material approval proves one material passed content review.  It must never mutate
EmpStudent.verify_status; destination verification is a separate T7 command that requires formal
FileBinding evidence and an exact EmpStudent version.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.modules.employment.services import employment_runtime_service as runtime
from app.modules.employment.services import employment_service as base
from app.services.db_service import session


def approve_material(mid, comment="", *, user: dict) -> dict:
    with session() as db:
        material, emp = runtime._assert_material(db, mid, user)
        if material.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = material.status
        operator, _ = base._op()
        material.status = "APPROVED"
        material.reviewer = operator
        material.review_time = datetime.utcnow()
        material.version = int(material.version or 0) + 1
        emp.material_status = "APPROVED"
        # Deliberately do not touch emp.verify_status.  Destination verification has its own
        # FileBinding + optimistic-lock command in Teacher V3 T7.
        base._audit(db, "MATERIAL", material.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(material.id), "status": "APPROVED"}

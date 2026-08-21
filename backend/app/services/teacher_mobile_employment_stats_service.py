"""Exact SQL aggregates for Teacher V3 T7 employment overview.

The operation list is deliberately bounded before T9 capacity work. KPI counts therefore come
from SQL aggregates under the same formal employment dataScope instead of pretending the first
100 rows are the whole school.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import EmpStudent
from app.modules.employment.services import employment_runtime_service as runtime
from app.services.db_service import _tid, session


def exact_stats(*, user: dict) -> dict:
    with session() as db:
        cond = [
            EmpStudent.tenant_id == _tid(),
            EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
        ]
        scope = runtime._scope_condition(db, user)
        if scope is not None:
            cond.append(scope)

        def count(*extra) -> int:
            return int(db.scalar(
                select(func.count()).select_from(EmpStudent).where(*cond, *extra)
            ) or 0)

        non_unemployed = EmpStudent.destination_type != "UNEMPLOYED"
        return {
            "total": count(),
            "unemployed": count(EmpStudent.destination_type == "UNEMPLOYED"),
            "pendingVerification": count(
                EmpStudent.verify_status.in_(["PENDING_VERIFY", "RETURNED"]),
                non_unemployed,
            ),
            "verified": count(EmpStudent.verify_status == "VERIFIED", non_unemployed),
        }

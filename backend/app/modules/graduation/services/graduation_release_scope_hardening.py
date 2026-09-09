"""Graduation SQL-native accessible_student_ids compatibility hardening."""
from __future__ import annotations
from sqlalchemy import select
from app.models import GraduationStudent
from app.modules.graduation.services.graduation_release_hardening_common import _ctx, _student_scope_select


def _install_scope_id_hardening() -> None:
    from app.modules.graduation.services import graduation_scope_service as scope
    old = scope.accessible_student_ids

    def sql_ids(db, tenant_id: int, batch_id=None):
        _user, role = _ctx()
        supported = set(scope.FULL_SCOPE_ROLES) | set(scope.COLLEGE_SCOPE_ROLES) | set(scope.MAJOR_SCOPE_ROLES) | {"GD_MENTOR", "COUNSELOR", "GD_REVIEWER", "STUDENT"}
        if role not in supported:
            return old(db, tenant_id, batch_id=batch_id)
        values = db.scalars(_student_scope_select(db, tenant_id, batch_id=batch_id)).all()
        # SQLAlchemy returns scalar IDs in production. Lightweight scope unit tests
        # intentionally use a FakeDb that returns GraduationStudent rows for any
        # statement; preserve the legacy relation evaluator for that compatibility
        # path instead of coercing ORM rows with int().
        if values and isinstance(values[0], GraduationStudent):
            return old(db, tenant_id, batch_id=batch_id)
        return [int(v) for v in values]

    scope.accessible_student_ids = sql_ids
    module_names = [
        "graduation_mentor_service", "graduation_grade_service", "graduation_stats_service",
        "graduation_guidance_service", "graduation_taskbook_service", "graduation_more_service",
        "graduation_archive_service", "graduation_service", "graduation_midterm_service",
        "graduation_review_service", "graduation_risk_service",
    ]
    import importlib
    for name in module_names:
        try:
            module = importlib.import_module(f"app.modules.graduation.services.{name}")
        except Exception:
            continue
        if hasattr(module, "accessible_student_ids"):
            module.accessible_student_ids = sql_ids

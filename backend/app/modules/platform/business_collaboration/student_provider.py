from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.permissions import has_permission
from app.models import SchoolClass, StudentProfile

from .navigation import NavigationTargetResolver
from .runtime_context import explicit_search_context, search_context_is_authoritative
from .schemas import SearchContext, SearchHit


StudentScopeResolver = Callable[[Session, SearchContext], ColumnElement[bool]]

_STUDENT_SEARCH_PERMISSIONS = (
    "student.profile.view",
    "studentAffairs.student.view",
    "campusService.student.view",
    "internship.student.view",
    "graduationDesign.view",
    "graduationDesign.student.view",
    "graduationDesign.student.manage",
    "academicAffairs.roster.view",
)


def _can_search_students(actor: dict[str, Any]) -> bool:
    if str(actor.get("userType") or "").upper() == "STUDENT":
        return True
    return has_permission(actor, "*") or any(
        has_permission(actor, code) for code in _STUDENT_SEARCH_PERMISSIONS
    )


def _default_scope(db: Session, context: SearchContext) -> ColumnElement[bool]:
    """Resolve the existing StudentAffairs scope in the provider's own session."""
    from app.core.affairs_security import build_affairs_context

    scope = build_affairs_context(context.actor, db)
    if int(scope.tenant_id) != int(context.tenant_id):
        return false()
    if scope.scope_type == "TENANT_ALL":
        return true()
    if scope.scope_type == "SELF":
        return StudentProfile.id == int(scope.self_student_id) if scope.self_student_id else false()
    if scope.scope_type == "STUDENT":
        ids = {int(value) for value in (scope.psychology_student_ids | scope.student_ids)}
        return StudentProfile.id.in_(ids) if ids else false()
    if scope.scope_type in {"NONE", "DORM_BUILDING"}:
        return false()
    class_ids = scope.allowed_class_ids(db)
    return StudentProfile.class_id.in_(class_ids) if class_ids else false()


def _like_value(keyword: str) -> str:
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class StudentSearchProvider:
    provider_code = "STUDENT"

    def __init__(
        self,
        session_factory,
        *,
        target_resolver: NavigationTargetResolver | None = None,
        scope_resolver: StudentScopeResolver | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._targets = target_resolver or NavigationTargetResolver()
        self._scope_resolver = scope_resolver or _default_scope

    def search(self, context: SearchContext) -> list[SearchHit]:
        keyword = str(context.keyword or "").strip()
        if (
            len(keyword) < 2
            or not search_context_is_authoritative(context)
            or not _can_search_students(context.actor)
        ):
            return []
        keyword = keyword[:100]
        limit = min(max(int(context.limit), 1), 50)

        # The provider owns this session.  A request session is never shared
        # across federation worker threads.
        with self._session_factory() as db, explicit_search_context(context):
            scope_predicate = self._scope_resolver(db, context)
            base_predicates = (
                StudentProfile.tenant_id == int(context.tenant_id),
                StudentProfile.is_deleted.is_(False),
                StudentProfile.status == "ACTIVE",
                scope_predicate,
            )
            match_predicate = or_(
                StudentProfile.real_name.like(_like_value(keyword), escape="\\"),
                StudentProfile.student_no == keyword,
            )
            stmt = (
                select(
                    StudentProfile.id,
                    StudentProfile.real_name,
                    StudentProfile.student_no,
                    StudentProfile.grade,
                    StudentProfile.student_status,
                    SchoolClass.class_name,
                )
                .outerjoin(
                    SchoolClass,
                    (SchoolClass.id == StudentProfile.class_id)
                    & (SchoolClass.tenant_id == StudentProfile.tenant_id)
                    & SchoolClass.is_deleted.is_(False),
                )
                # Scope is part of SQL before keyword matching and hydration.
                .where(*base_predicates)
                .where(match_predicate)
                .order_by(StudentProfile.student_no, StudentProfile.id)
                .limit(limit)
            )
            rows = db.execute(stmt).all()

        hits: list[SearchHit] = []
        for row in rows:
            target = self._targets.student(
                int(row.id), client=context.client, actor=context.actor
            )
            secondary = " · ".join(
                value for value in (row.student_no, row.class_name, f"{row.grade}级" if row.grade else None)
                if value
            )
            hits.append(SearchHit(
                provider=self.provider_code,
                type="STUDENT",
                object_id=str(row.id),
                dedupe_key=f"student:{row.id}",
                title=row.real_name,
                secondary=secondary or None,
                module_code="STUDENT",
                status=row.student_status,
                badges=[],
                target=target,
                allowed_actions=["OPEN"] if target else [],
            ))
        return hits

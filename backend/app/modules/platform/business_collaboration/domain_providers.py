from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.core.permissions import has_permission
from app.models import AffairsRiskRecord, GraduationStudent, InternshipRecord, StudentProfile

from .navigation import NavigationTargetResolver
from .runtime_context import explicit_search_context, search_context_is_authoritative
from .schemas import SearchContext, SearchHit


GraduationScopeResolver = Callable[[Session, SearchContext], Select]
InternshipScopeApplier = Callable[[Select, SearchContext], Select]
AffairsScopeResolver = Callable[[Session, SearchContext], ColumnElement[bool]]


def _has_any(actor: dict, codes: tuple[str, ...]) -> bool:
    return has_permission(actor, "*") or any(has_permission(actor, code) for code in codes)


def _like(keyword: str) -> str:
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _graduation_scope(db: Session, context: SearchContext) -> Select:
    from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select

    return student_scope_select(db, int(context.tenant_id))


class GraduationSearchProvider:
    provider_code = "GRADUATION"
    _PERMISSIONS = (
        "graduationDesign.student.view",
        "graduationDesign.student.manage",
        "graduationDesign.proposal.view",
        "graduationDesign.final.view",
        "graduationDesign.guidance.view",
    )

    def __init__(self, session_factory, *, scope_resolver: GraduationScopeResolver | None = None,
                 target_resolver: NavigationTargetResolver | None = None) -> None:
        self._session_factory = session_factory
        self._scope = scope_resolver or _graduation_scope
        self._targets = target_resolver or NavigationTargetResolver()

    def search(self, context: SearchContext) -> list[SearchHit]:
        keyword = str(context.keyword or "").strip()
        student_actor = str(context.actor.get("userType") or "").upper() == "STUDENT"
        if (
            len(keyword) < 2
            or not search_context_is_authoritative(context)
            or (not student_actor and not _has_any(context.actor, self._PERMISSIONS))
        ):
            return []
        keyword = keyword[:100]
        limit = min(max(int(context.limit), 1), 50)
        with self._session_factory() as db, explicit_search_context(context):
            scope = self._scope(db, context)
            rows = db.scalars(
                select(GraduationStudent)
                .where(
                    GraduationStudent.tenant_id == int(context.tenant_id),
                    GraduationStudent.is_deleted.is_(False),
                    GraduationStudent.record_status == "ACTIVE",
                    GraduationStudent.id.in_(scope),
                )
                .where(or_(
                    GraduationStudent.name.like(_like(keyword), escape="\\"),
                    GraduationStudent.student_no == keyword,
                    GraduationStudent.topic_title.like(_like(keyword), escape="\\"),
                ))
                .order_by(GraduationStudent.id.desc())
                .limit(limit)
            ).all()
        return [self._hit(row, context) for row in rows]

    def _hit(self, row: GraduationStudent, context: SearchContext) -> SearchHit:
        target = self._targets.domain(self.provider_code, int(row.id), client=context.client)
        secondary = " · ".join(value for value in (row.student_no, row.topic_title, row.class_name) if value)
        return SearchHit(
            provider=self.provider_code, type="GRADUATION_STUDENT", object_id=str(row.id),
            dedupe_key=f"graduation-student:{row.id}", title=row.name,
            secondary=secondary or None, module_code="GRADUATION", status=row.stage,
            badges=[row.risk_level] if row.risk_level and row.risk_level != "NONE" else [],
            target=target, allowed_actions=["OPEN"] if target else [],
        )


def _internship_scope(stmt: Select, context: SearchContext) -> Select:
    if str(context.actor.get("userType") or "").upper() == "STUDENT":
        raw = context.actor.get("studentId") or context.actor.get("studentProfileId")
        try:
            return stmt.where(InternshipRecord.student_id == int(raw))
        except (TypeError, ValueError):
            return stmt.where(false())
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    return apply_internship_record_scope(stmt, context.actor)


class InternshipSearchProvider:
    provider_code = "INTERNSHIP"
    _PERMISSIONS = (
        "internship.student.view", "internship.dashboard.view", "internship.process.view",
        "internship.report.view", "internship.exception.view",
    )

    def __init__(self, session_factory, *, scope_applier: InternshipScopeApplier | None = None,
                 target_resolver: NavigationTargetResolver | None = None) -> None:
        self._session_factory = session_factory
        self._scope = scope_applier or _internship_scope
        self._targets = target_resolver or NavigationTargetResolver()

    def search(self, context: SearchContext) -> list[SearchHit]:
        keyword = str(context.keyword or "").strip()
        student_actor = str(context.actor.get("userType") or "").upper() == "STUDENT"
        if (
            len(keyword) < 2
            or not search_context_is_authoritative(context)
            or (not student_actor and not _has_any(context.actor, self._PERMISSIONS))
        ):
            return []
        keyword = keyword[:100]
        limit = min(max(int(context.limit), 1), 50)
        with self._session_factory() as db, explicit_search_context(context):
            stmt = select(InternshipRecord, StudentProfile).join(
                StudentProfile,
                (StudentProfile.id == InternshipRecord.student_id)
                & (StudentProfile.tenant_id == InternshipRecord.tenant_id)
                & StudentProfile.is_deleted.is_(False),
            ).where(
                InternshipRecord.tenant_id == int(context.tenant_id),
                InternshipRecord.is_deleted.is_(False),
            )
            stmt = self._scope(stmt, context)
            stmt = stmt.where(or_(
                StudentProfile.real_name.like(_like(keyword), escape="\\"),
                StudentProfile.student_no == keyword,
                InternshipRecord.enterprise_name.like(_like(keyword), escape="\\"),
                InternshipRecord.position_name.like(_like(keyword), escape="\\"),
            )).order_by(InternshipRecord.id.desc()).limit(limit)
            rows = db.execute(stmt).all()
        hits: list[SearchHit] = []
        for record, student in rows:
            target = self._targets.domain(self.provider_code, int(record.id), client=context.client)
            secondary = " · ".join(value for value in (
                student.student_no, record.enterprise_name, record.position_name,
            ) if value)
            hits.append(SearchHit(
                provider=self.provider_code, type="INTERNSHIP_RECORD", object_id=str(record.id),
                dedupe_key=f"internship-record:{record.id}", title=student.real_name,
                secondary=secondary or None, module_code="INTERNSHIP", status=record.status,
                badges=[record.risk_level] if record.risk_level and record.risk_level != "NONE" else [],
                target=target, allowed_actions=["OPEN"] if target else [],
            ))
        return hits


def _affairs_scope(db: Session, context: SearchContext) -> ColumnElement[bool]:
    from app.core.affairs_security import build_affairs_context

    scope = build_affairs_context(context.actor, db)
    if int(scope.tenant_id) != int(context.tenant_id):
        return false()
    if scope.scope_type == "TENANT_ALL":
        return true()
    if scope.scope_type == "SELF" and scope.self_student_id:
        return StudentProfile.id == int(scope.self_student_id)
    if scope.scope_type == "STUDENT":
        ids = {int(value) for value in (scope.psychology_student_ids | scope.student_ids)}
        return StudentProfile.id.in_(ids) if ids else false()
    allowed = scope.allowed_class_ids(db)
    return StudentProfile.class_id.in_(allowed) if allowed else false()


class AffairsSearchProvider:
    provider_code = "AFFAIRS"
    _PERMISSIONS = ("studentAffairs.risk.view",)

    def __init__(self, session_factory, *, scope_resolver: AffairsScopeResolver | None = None,
                 target_resolver: NavigationTargetResolver | None = None) -> None:
        self._session_factory = session_factory
        self._scope = scope_resolver or _affairs_scope
        self._targets = target_resolver or NavigationTargetResolver()

    def search(self, context: SearchContext) -> list[SearchHit]:
        keyword = str(context.keyword or "").strip()
        if (
            len(keyword) < 2
            or not search_context_is_authoritative(context)
            or not _has_any(context.actor, self._PERMISSIONS)
        ):
            return []
        keyword = keyword[:100]
        limit = min(max(int(context.limit), 1), 50)
        with self._session_factory() as db, explicit_search_context(context):
            scope = self._scope(db, context)
            rows = db.execute(
                select(AffairsRiskRecord, StudentProfile)
                .join(
                    StudentProfile,
                    (StudentProfile.id == AffairsRiskRecord.student_id)
                    & (StudentProfile.tenant_id == AffairsRiskRecord.tenant_id)
                    & StudentProfile.is_deleted.is_(False),
                )
                .where(
                    AffairsRiskRecord.tenant_id == int(context.tenant_id),
                    AffairsRiskRecord.is_deleted.is_(False),
                    AffairsRiskRecord.source != "MENTAL",
                    scope,
                )
                .where(or_(
                    AffairsRiskRecord.title.like(_like(keyword), escape="\\"),
                    StudentProfile.real_name.like(_like(keyword), escape="\\"),
                    StudentProfile.student_no == keyword,
                ))
                .order_by(AffairsRiskRecord.id.desc())
                .limit(limit)
            ).all()
        hits: list[SearchHit] = []
        for risk, student in rows:
            target = self._targets.domain(self.provider_code, int(risk.id), client=context.client)
            hits.append(SearchHit(
                provider=self.provider_code, type="AFFAIRS_RISK", object_id=str(risk.id),
                dedupe_key=f"affairs-risk:{risk.id}", title=risk.title or "学工风险",
                secondary=f"{student.real_name} · {student.student_no}", module_code="AFFAIRS",
                status=risk.status, badges=[risk.risk_level] if risk.risk_level else [],
                target=target, allowed_actions=["OPEN"] if target else [],
            ))
        return hits

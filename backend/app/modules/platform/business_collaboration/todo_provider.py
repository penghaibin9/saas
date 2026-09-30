from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import UnifiedTodo
from app.services.todo_route_registry import resolve_todo_route

from .runtime_context import explicit_search_context, search_context_is_authoritative
from .schemas import NavigationTarget, SearchContext, SearchHit


TodoVisibilityResolver = Callable[[Session, SearchContext], ColumnElement[bool] | None]


def _default_visibility(db: Session, context: SearchContext):
    from app.services.workbench_todo_service import _visibility_cond

    return _visibility_cond(db, context.actor)


def _target(todo: UnifiedTodo, context: SearchContext) -> NavigationTarget | None:
    route = resolve_todo_route(todo.todo_type, todo.source_biz_id, client=context.client)
    if not route:
        return None
    return NavigationTarget(
        route_name=route.get("routeName"),
        route_params=dict(route.get("routeParams") or {}),
        query=dict(route.get("query") or {}),
        path=route.get("path"),
        focus_mode=route.get("focusMode") or "NONE",
        exact=bool(route.get("exact")),
    )


class TodoSearchProvider:
    provider_code = "TODO"

    def __init__(self, session_factory, *, visibility_resolver: TodoVisibilityResolver | None = None) -> None:
        self._session_factory = session_factory
        self._visibility = visibility_resolver or _default_visibility

    def search(self, context: SearchContext) -> list[SearchHit]:
        keyword = str(context.keyword or "").strip()
        if len(keyword) < 2 or not search_context_is_authoritative(context):
            return []
        keyword = keyword[:100]
        limit = min(max(int(context.limit), 1), 50)
        with self._session_factory() as db, explicit_search_context(context):
            visibility = self._visibility(db, context)
            if visibility is None:
                return []
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            predicates = (
                UnifiedTodo.tenant_id == int(context.tenant_id),
                UnifiedTodo.is_deleted.is_(False),
                visibility,
            )
            rows = db.scalars(
                select(UnifiedTodo)
                .where(*predicates)
                .where(or_(
                    UnifiedTodo.title.like(like, escape="\\"),
                    UnifiedTodo.todo_type.like(like, escape="\\"),
                    UnifiedTodo.source_biz_type.like(like, escape="\\"),
                ))
                .order_by(UnifiedTodo.status, UnifiedTodo.due_at.is_(None), UnifiedTodo.due_at, UnifiedTodo.id.desc())
                .limit(limit)
            ).all()

        from app.services.workbench_todo_service import _todo_dict

        hits: list[SearchHit] = []
        for row in rows:
            target = _target(row, context)
            dto = _todo_dict(row, client=context.client)
            actions = list(dto.get("allowedActions") or [])
            if target is None:
                actions = [action for action in actions if action != "OPEN"]
            hits.append(SearchHit(
                provider=self.provider_code,
                type="TODO",
                object_id=str(row.id),
                dedupe_key=f"todo:{row.id}",
                title=row.title,
                secondary=row.source_biz_type or row.source_module,
                module_code=str(row.source_module or "TODO").upper(),
                status=row.status,
                badges=[],
                target=target,
                allowed_actions=actions,
            ))
        return hits

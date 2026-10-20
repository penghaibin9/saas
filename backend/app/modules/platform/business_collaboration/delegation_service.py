from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import UnifiedTodo, User
from app.services.message_identity import resolve_message_user_id

from .assignment_service import TodoCollaborationError
from .models import TodoActingDelegation, TodoWorkAssignment
from .time_utils import naive_utc


_SCOPE_TYPES = {"ALL_TODOS", "TODO_TYPE", "SOURCE_MODULE", "TODO_IDS"}


class DelegationIdentityValidator(Protocol):
    def validate_pair(
        self, db: Session, *, tenant_id: int, delegator_user_id: int, delegate_user_id: int,
    ) -> None: ...

    def validate_delegate(
        self, db: Session, *, tenant_id: int, delegate_user_id: int,
    ) -> None: ...


class _DatabaseIdentityValidator:
    @staticmethod
    def _active_staff(db: Session, tenant_id: int, user_id: int, *, lock: bool = False) -> User | None:
        stmt = select(User).where(
            User.id == int(user_id), User.tenant_id == int(tenant_id),
            User.is_deleted.is_(False), User.status == "ACTIVE",
        )
        if lock:
            stmt = stmt.with_for_update()
        row = db.scalars(stmt).first()
        return row if row and str(row.user_type or "").upper() != "STUDENT" else None

    def validate_pair(
        self, db: Session, *, tenant_id: int, delegator_user_id: int, delegate_user_id: int,
    ) -> None:
        if int(delegator_user_id) == int(delegate_user_id):
            raise TodoCollaborationError("VALIDATION_ERROR", "不能代理本人", http_status=422)
        # Locking the delegator serializes overlap checks for this owner.
        if self._active_staff(db, tenant_id, delegator_user_id, lock=True) is None:
            raise TodoCollaborationError("NO_PERMISSION", "委托人不是有效教职工", http_status=403)
        if self._active_staff(db, tenant_id, delegate_user_id) is None:
            raise TodoCollaborationError("VALIDATION_ERROR", "代理人不存在、已停用或不是教职工", http_status=422)

    def validate_delegate(self, db: Session, *, tenant_id: int, delegate_user_id: int) -> None:
        if self._active_staff(db, tenant_id, delegate_user_id) is None:
            raise TodoCollaborationError("NO_PERMISSION", "代理人已停用或不是教职工", http_status=403)


class DelegationCapabilityResolver(Protocol):
    def __call__(self, action: str, todo: UnifiedTodo | None, actor: dict, db: Session) -> bool: ...


class DelegatorCapabilityResolver(Protocol):
    def __call__(self, action: str, todo: UnifiedTodo, delegator_user_id: int, db: Session) -> bool: ...


class DelegateScopeResolver(Protocol):
    def __call__(self, todo: UnifiedTodo, actor: dict, db: Session) -> bool: ...


class DelegationAuditSink(Protocol):
    def __call__(self, event: dict, db: Session) -> None: ...


def _deny_configuration(_action: str, _todo, _actor: dict, _db: Session) -> bool:
    return False


def _deny_delegator(_action: str, _todo: UnifiedTodo, _owner: int, _db: Session) -> bool:
    return False


def _deny_scope(_todo: UnifiedTodo, _actor: dict, _db: Session) -> bool:
    return False


def _default_audit(event: dict, db: Session) -> None:
    from app.services import mock_audit_service as audit

    audit.record_critical(
        event["label"], method="POST", path=event["path"], status_code=200,
        target_type="todo_acting_delegation", target_id=event["delegationId"],
        detail=event["detail"], db=db,
    )


def _actor_id(actor: dict) -> int:
    return int(resolve_message_user_id(actor or {}) or 0)


def _actor_tenant_matches(actor: dict, tenant_id: int) -> bool:
    raw_tenant = (actor or {}).get("tenantId") or (actor or {}).get("tenant_id")
    try:
        return int(tenant_id) > 0 and int(raw_tenant) == int(tenant_id)
    except (TypeError, ValueError):
        return False


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_scope(scope_type: str, scope: dict | None) -> tuple[str, dict, str]:
    normalized_type = str(scope_type or "").strip().upper()
    if normalized_type not in _SCOPE_TYPES:
        raise TodoCollaborationError("VALIDATION_ERROR", "不支持的待办代理范围", http_status=422)
    if scope is not None and not isinstance(scope, dict):
        raise TodoCollaborationError("VALIDATION_ERROR", "待办代理范围必须是对象", http_status=422)
    raw = dict(scope or {})
    if normalized_type == "ALL_TODOS":
        normalized = {}
    elif normalized_type == "TODO_TYPE":
        raw_values = raw.get("todoTypes")
        if not isinstance(raw_values, list) or not raw_values or any(
            not isinstance(value, str) or not value.strip() for value in raw_values
        ):
            raise TodoCollaborationError(
                "VALIDATION_ERROR", "代理范围 todoTypes 必须为非空字符串数组", http_status=422,
            )
        values = sorted({value.strip().upper() for value in raw_values})
        normalized = {"todoTypes": values}
    elif normalized_type == "SOURCE_MODULE":
        raw_values = raw.get("sourceModules")
        if not isinstance(raw_values, list) or not raw_values or any(
            not isinstance(value, str) or not value.strip() for value in raw_values
        ):
            raise TodoCollaborationError(
                "VALIDATION_ERROR", "代理范围 sourceModules 必须为非空字符串数组", http_status=422,
            )
        values = sorted({value.strip().lower() for value in raw_values})
        normalized = {"sourceModules": values}
    else:
        raw_values = raw.get("todoIds")
        normalized_ids: set[str] = set()
        if not isinstance(raw_values, list) or not raw_values:
            raise TodoCollaborationError(
                "VALIDATION_ERROR", "代理范围 todoIds 必须为非空正整数数组", http_status=422,
            )
        for value in raw_values:
            if isinstance(value, bool):
                normalized_id = 0
            elif isinstance(value, int):
                normalized_id = value
            elif isinstance(value, str) and value.strip().isdigit():
                normalized_id = int(value.strip())
            else:
                normalized_id = 0
            if normalized_id <= 0:
                raise TodoCollaborationError(
                    "VALIDATION_ERROR", "代理范围 todoIds 必须为非空正整数数组", http_status=422,
                )
            normalized_ids.add(str(normalized_id))
        values = sorted(normalized_ids, key=int)
        normalized = {"todoIds": values}
    canonical = json.dumps(
        {"scopeType": normalized_type, "scope": normalized},
        ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    )
    return normalized_type, normalized, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scope_matches(row: TodoActingDelegation, todo: UnifiedTodo) -> bool:
    if not isinstance(row.scope_json, dict):
        return False
    scope = row.scope_json
    if row.scope_type == "ALL_TODOS":
        return True
    if row.scope_type == "TODO_TYPE":
        values = scope.get("todoTypes")
        return isinstance(values, list) and str(todo.todo_type or "").upper() in set(values)
    if row.scope_type == "SOURCE_MODULE":
        values = scope.get("sourceModules")
        return isinstance(values, list) and str(todo.source_module or "").lower() in set(values)
    if row.scope_type == "TODO_IDS":
        values = scope.get("todoIds")
        return isinstance(values, list) and str(todo.id) in set(values)
    return False


@dataclass(frozen=True, slots=True)
class ActingAuthorization:
    delegation_id: int
    actor_user_id: int
    on_behalf_of_user_id: int
    action: str


class TodoActingDelegationService:
    def __init__(
        self,
        session_factory,
        *,
        identity_validator: DelegationIdentityValidator | None = None,
        configuration_capability: DelegationCapabilityResolver | None = None,
        delegator_capability: DelegatorCapabilityResolver | None = None,
        delegate_capability: DelegationCapabilityResolver | None = None,
        delegate_scope: DelegateScopeResolver | None = None,
        domain_capability: DelegationCapabilityResolver | None = None,
        audit_sink: DelegationAuditSink | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._identity = identity_validator or _DatabaseIdentityValidator()
        self._configuration_capability = configuration_capability or _deny_configuration
        self._delegator_capability = delegator_capability or _deny_delegator
        self._delegate_capability = delegate_capability or _deny_configuration
        self._delegate_scope = delegate_scope or _deny_scope
        self._domain_capability = domain_capability or _deny_configuration
        self._audit = audit_sink or _default_audit

    def create(
        self, *, tenant_id: int, delegate_user_id: int, scope_type: str,
        scope: dict | None, effective_from: datetime, effective_until: datetime,
        reason: str, actor: dict,
    ) -> TodoActingDelegation:
        delegator_id = _actor_id(actor)
        if (
            delegator_id <= 0
            or not _actor_tenant_matches(actor, tenant_id)
            or str(actor.get("userType") or "").upper() == "STUDENT"
        ):
            raise TodoCollaborationError("NO_PERMISSION", "仅有效教职工可配置待办代理", http_status=403)
        start = naive_utc(effective_from)
        end = naive_utc(effective_until)
        now = _utcnow()
        if start is None or end is None:
            raise TodoCollaborationError("VALIDATION_ERROR", "代理时间窗无效", http_status=422)
        if end <= start or end <= now or end - start > timedelta(days=366):
            raise TodoCollaborationError("VALIDATION_ERROR", "代理时间窗无效或超过 366 天", http_status=422)
        normalized_reason = str(reason or "").strip()
        if len(normalized_reason) < 2 or len(normalized_reason) > 500:
            raise TodoCollaborationError("VALIDATION_ERROR", "代理原因长度必须为 2-500 字", http_status=422)
        normalized_type, normalized_scope, scope_hash = _normalize_scope(scope_type, scope)

        db = self._session_factory()
        try:
            self._identity.validate_pair(
                db, tenant_id=int(tenant_id), delegator_user_id=delegator_id,
                delegate_user_id=int(delegate_user_id),
            )
            if not self._configuration_capability("DELEGATE", None, actor, db):
                raise TodoCollaborationError("NO_PERMISSION", "无权配置待办代理", http_status=403)
            overlap = db.scalars(select(TodoActingDelegation).where(
                TodoActingDelegation.tenant_id == int(tenant_id),
                TodoActingDelegation.delegator_user_id == delegator_id,
                TodoActingDelegation.status.in_(("SCHEDULED", "ACTIVE")),
                TodoActingDelegation.revoked_at.is_(None),
                TodoActingDelegation.effective_from < end,
                TodoActingDelegation.effective_until > start,
                TodoActingDelegation.is_deleted.is_(False),
            ).with_for_update()).first()
            if overlap is not None:
                # Different delegates and scope encodings can still authorize
                # the same Todo.  One delegator therefore has one unambiguous
                # acting-authority window at a time.
                raise TodoCollaborationError("DELEGATION_OVERLAP", "委托人的代理时间窗重叠", http_status=409)
            row = TodoActingDelegation(
                tenant_id=int(tenant_id), delegator_user_id=delegator_id,
                delegate_user_id=int(delegate_user_id), scope_type=normalized_type,
                scope_json=normalized_scope, scope_hash=scope_hash,
                effective_from=start, effective_until=end,
                status="ACTIVE" if start <= now < end else "SCHEDULED",
                reason=normalized_reason, created_by=delegator_id, updated_by=delegator_id,
            )
            db.add(row)
            db.flush()
            self._audit({
                "label": "待办代理创建", "path": "/api/v1/todo-acting-delegations",
                "delegationId": str(row.id),
                "detail": {
                    "actorUserId": str(delegator_id), "delegateUserId": str(delegate_user_id),
                    "scopeType": normalized_type, "scopeHash": scope_hash,
                },
            }, db)
            db.commit()
            db.refresh(row)
            return row
        except TodoCollaborationError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def authorize_action(
        self, *, tenant_id: int, todo_id: int, action: str,
        actor: dict, now: datetime | None = None,
    ) -> ActingAuthorization:
        actor_id = _actor_id(actor)
        if (
            actor_id <= 0
            or not _actor_tenant_matches(actor, tenant_id)
            or str(actor.get("userType") or "").upper() == "STUDENT"
        ):
            raise TodoCollaborationError("NO_PERMISSION", "学生或无效身份不能代理教职工待办", http_status=403)
        normalized_action = str(action or "").strip().upper()
        if not normalized_action:
            raise TodoCollaborationError("VALIDATION_ERROR", "缺少待办动作", http_status=422)
        instant = naive_utc(now) or _utcnow()
        with self._session_factory() as db:
            self._identity.validate_delegate(db, tenant_id=int(tenant_id), delegate_user_id=actor_id)
            todo = db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == int(tenant_id),
                UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING",
            )).first()
            if todo is None:
                raise TodoCollaborationError("TODO_NOT_FOUND", "待办不存在或已办结", http_status=404)
            owner_id = self._effective_owner_id(db, int(tenant_id), todo)
            if owner_id is None or owner_id == actor_id:
                raise TodoCollaborationError("NO_DELEGATION", "待办没有可用代理关系", http_status=403)
            rows = db.scalars(select(TodoActingDelegation).where(
                TodoActingDelegation.tenant_id == int(tenant_id),
                TodoActingDelegation.delegator_user_id == owner_id,
                TodoActingDelegation.delegate_user_id == actor_id,
                TodoActingDelegation.status.in_(("SCHEDULED", "ACTIVE")),
                TodoActingDelegation.revoked_at.is_(None),
                TodoActingDelegation.effective_from <= instant,
                TodoActingDelegation.effective_until > instant,
                TodoActingDelegation.is_deleted.is_(False),
            ).order_by(TodoActingDelegation.id.desc()).limit(2)).all()
            if len(rows) > 1:
                raise TodoCollaborationError(
                    "DELEGATION_AMBIGUOUS",
                    "检测到重叠代理授权，已默认拒绝",
                    http_status=409,
                )
            delegation = next((row for row in rows if _scope_matches(row, todo)), None)
            if delegation is None:
                raise TodoCollaborationError("NO_DELEGATION", "待办不在有效代理范围或时间窗内", http_status=403)

            # Runtime intersection: no role, permission or data-scope snapshot is
            # copied from the delegator.  Every term is evaluated in real time.
            checks = (
                self._delegator_capability(normalized_action, todo, owner_id, db),
                self._delegate_capability(normalized_action, todo, actor, db),
                self._delegate_scope(todo, actor, db),
                self._domain_capability(normalized_action, todo, actor, db),
            )
            if not all(checks):
                raise TodoCollaborationError("NO_PERMISSION", "代理动作未通过实时权限与数据范围交集", http_status=403)
            authorization = ActingAuthorization(
                delegation_id=int(delegation.id), actor_user_id=actor_id,
                on_behalf_of_user_id=owner_id, action=normalized_action,
            )
            self._audit({
                "label": "待办代理动作授权", "path": f"/api/v1/todos/{todo_id}/acting/{normalized_action.lower()}",
                "delegationId": str(delegation.id),
                "detail": {
                    "todoId": str(todo_id), "action": normalized_action,
                    "actorUserId": str(actor_id), "onBehalfOfUserId": str(owner_id),
                },
            }, db)
            db.commit()
            return authorization

    def revoke(
        self, *, tenant_id: int, delegation_id: int, reason: str, actor: dict,
    ) -> TodoActingDelegation:
        actor_id = _actor_id(actor)
        if (
            actor_id <= 0
            or not _actor_tenant_matches(actor, tenant_id)
            or str(actor.get("userType") or "").upper() == "STUDENT"
        ):
            raise TodoCollaborationError("NO_PERMISSION", "仅有效教职工可撤销待办代理", http_status=403)
        normalized_reason = str(reason or "").strip()
        if len(normalized_reason) < 2 or len(normalized_reason) > 500:
            raise TodoCollaborationError("VALIDATION_ERROR", "撤销原因长度必须为 2-500 字", http_status=422)
        db = self._session_factory()
        try:
            self._identity.validate_delegate(db, tenant_id=int(tenant_id), delegate_user_id=actor_id)
            row = db.scalars(select(TodoActingDelegation).where(
                TodoActingDelegation.id == int(delegation_id),
                TodoActingDelegation.tenant_id == int(tenant_id),
                TodoActingDelegation.is_deleted.is_(False),
            ).with_for_update()).first()
            if row is None:
                raise TodoCollaborationError("DELEGATION_NOT_FOUND", "待办代理不存在", http_status=404)
            if row.revoked_at is not None or row.status == "REVOKED":
                raise TodoCollaborationError("DELEGATION_REVOKED", "待办代理已撤销", http_status=409)
            if int(row.delegator_user_id) != actor_id and not self._configuration_capability(
                "REVOKE_OTHER", None, actor, db
            ):
                raise TodoCollaborationError("NO_PERMISSION", "仅委托人或授权管理员可撤销", http_status=403)
            row.status = "REVOKED"
            row.revoked_at = _utcnow()
            row.revoked_by = actor_id
            row.updated_by = actor_id
            self._audit({
                "label": "待办代理撤销", "path": f"/api/v1/todo-acting-delegations/{delegation_id}/revoke",
                "delegationId": str(row.id),
                "detail": {
                    "actorUserId": str(actor_id), "delegatorUserId": str(row.delegator_user_id),
                    "delegateUserId": str(row.delegate_user_id), "reason": normalized_reason,
                },
            }, db)
            db.commit()
            db.refresh(row)
            return row
        except TodoCollaborationError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _effective_owner_id(db: Session, tenant_id: int, todo: UnifiedTodo) -> int | None:
        assignment = db.scalars(select(TodoWorkAssignment).where(
            TodoWorkAssignment.tenant_id == tenant_id,
            TodoWorkAssignment.todo_id == int(todo.id),
            TodoWorkAssignment.status == "ACTIVE",
            TodoWorkAssignment.released_at.is_(None),
            TodoWorkAssignment.is_deleted.is_(False),
        ).order_by(TodoWorkAssignment.id.desc()).limit(1)).first()
        if assignment is not None:
            return int(assignment.owner_user_id)
        return int(todo.assignee_id) if int(todo.assignee_id) > 0 else None

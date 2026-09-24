from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import UnifiedTodo
from app.services.message_identity import resolve_message_user_id

from .models import TodoWorkAssignment


class TodoCollaborationError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class ITodoPoolVisibilityProvider(Protocol):
    def can_view(self, todo: UnifiedTodo, user: dict, db: Session) -> bool: ...


class DenyTodoPoolVisibilityProvider:
    def can_view(self, todo: UnifiedTodo, user: dict, db: Session) -> bool:
        return False


class CanonicalStudentTodoPoolVisibilityProvider:
    """Current workbench visibility, with non-student-centric pools denied."""

    def can_view(self, todo: UnifiedTodo, user: dict, db: Session) -> bool:
        if todo.student_id is None:
            return False
        from app.services.workbench_todo_service import _visibility_cond

        predicate = _visibility_cond(db, user)
        if predicate is None:
            return False
        return db.scalar(select(UnifiedTodo.id).where(
            UnifiedTodo.id == todo.id,
            UnifiedTodo.tenant_id == todo.tenant_id,
            UnifiedTodo.is_deleted.is_(False),
            predicate,
        ).limit(1)) is not None


class CollaborationCapabilityResolver(Protocol):
    def __call__(self, action: str, todo: UnifiedTodo, user: dict, db: Session) -> bool: ...


class AssignmentAuditSink(Protocol):
    def __call__(self, event: dict, db: Session) -> None: ...


def _deny_capability(_action: str, _todo: UnifiedTodo, _user: dict, _db: Session) -> bool:
    return False


def _default_audit(event: dict, db: Session) -> None:
    from app.services import mock_audit_service as audit

    audit.record_critical(
        event["action"], method="POST", path=event["path"], status_code=200,
        target_type="todo_work_assignment", target_id=event["assignmentId"],
        detail=event["detail"], db=db,
    )


def _actor_id(user: dict) -> int:
    return int(resolve_message_user_id(user or {}) or 0)


def _is_student(user: dict) -> bool:
    return str((user or {}).get("userType") or "").upper() == "STUDENT"


def _now() -> datetime:
    return datetime.utcnow()


@dataclass(frozen=True, slots=True)
class EffectiveOwner:
    ownership_mode: str
    owner_user_id: int | None
    assignment_id: int | None


class TodoAssignmentService:
    def __init__(
        self,
        session_factory,
        *,
        visibility_provider: ITodoPoolVisibilityProvider | None = None,
        capability_resolver: CollaborationCapabilityResolver | None = None,
        audit_sink: AssignmentAuditSink | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._visibility = visibility_provider or DenyTodoPoolVisibilityProvider()
        self._capability = capability_resolver or _deny_capability
        self._audit = audit_sink or _default_audit

    def claim(self, *, tenant_id: int, todo_id: int, expected_version: int, user: dict) -> TodoWorkAssignment:
        actor_id = self._require_staff_actor(user, tenant_id)
        db = self._session_factory()
        try:
            todo = self._load_todo_for_update(db, tenant_id, todo_id)
            self._assert_expected_version(todo, expected_version)
            if todo.status != "PENDING" or int(todo.assignee_id) != 0:
                raise TodoCollaborationError("TODO_NOT_CLAIMABLE", "待办不是可认领的池待办", http_status=409)
            if not self._visibility.can_view(todo, user, db):
                raise TodoCollaborationError("TODO_NOT_FOUND", "待办不存在或不可见", http_status=404)
            if not self._capability("CLAIM", todo, user, db):
                raise TodoCollaborationError("NO_PERMISSION", "无权认领该待办", http_status=403)
            if self._active_assignment(db, tenant_id, todo_id, lock=True) is not None:
                raise TodoCollaborationError("TODO_ALREADY_CLAIMED", "待办已被认领", http_status=409)

            assignment = TodoWorkAssignment(
                tenant_id=int(tenant_id), todo_id=int(todo_id), assignment_type="CLAIM",
                owner_user_id=actor_id, status="ACTIVE", claimed_at=_now(), effective_from=_now(),
                source_ref_type=todo.source_biz_type, source_ref_id=str(todo.source_biz_id),
                created_by=actor_id, updated_by=actor_id,
            )
            db.add(assignment)
            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                raise TodoCollaborationError(
                    "TODO_ALREADY_CLAIMED", "待办已被其他办理人认领", http_status=409
                ) from exc
            self._audit({
                "action": "待办认领",
                "path": f"/api/v1/todos/{todo_id}/claim",
                "assignmentId": str(assignment.id),
                "detail": {
                    "todoId": str(todo_id), "actorUserId": str(actor_id),
                    "originalAssigneeId": str(todo.assignee_id), "expectedVersion": int(expected_version),
                },
            }, db)
            db.commit()
            db.refresh(assignment)
            return assignment
        except TodoCollaborationError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def release(
        self, *, tenant_id: int, todo_id: int, expected_version: int,
        reason: str, user: dict,
    ) -> TodoWorkAssignment:
        actor_id = self._require_staff_actor(user, tenant_id)
        normalized_reason = str(reason or "").strip()
        if len(normalized_reason) < 2 or len(normalized_reason) > 500:
            raise TodoCollaborationError("VALIDATION_ERROR", "释放原因长度必须为 2-500 字", http_status=422)
        db = self._session_factory()
        try:
            todo = self._load_todo_for_update(db, tenant_id, todo_id)
            self._assert_expected_version(todo, expected_version)
            if todo.status != "PENDING":
                raise TodoCollaborationError("TODO_NOT_RELEASABLE", "待办不是可释放状态", http_status=409)
            if not self._visibility.can_view(todo, user, db):
                raise TodoCollaborationError("TODO_NOT_FOUND", "待办不存在或不可见", http_status=404)
            if not self._capability("RELEASE", todo, user, db):
                raise TodoCollaborationError("NO_PERMISSION", "无权释放该待办", http_status=403)
            assignment = self._active_assignment(db, tenant_id, todo_id, lock=True)
            if assignment is None:
                raise TodoCollaborationError("TODO_NOT_CLAIMED", "待办当前未被认领", http_status=409)
            is_owner = int(assignment.owner_user_id) == actor_id
            if not is_owner and not self._capability("RELEASE_OTHER", todo, user, db):
                raise TodoCollaborationError("NO_PERMISSION", "仅当前办理人可释放待办", http_status=403)
            assignment.status = "RELEASED"
            assignment.released_at = _now()
            assignment.release_reason = normalized_reason
            assignment.updated_by = actor_id
            self._audit({
                "action": "待办释放",
                "path": f"/api/v1/todos/{todo_id}/release",
                "assignmentId": str(assignment.id),
                "detail": {
                    "todoId": str(todo_id), "actorUserId": str(actor_id),
                    "ownerUserId": str(assignment.owner_user_id), "reason": normalized_reason,
                },
            }, db)
            db.commit()
            db.refresh(assignment)
            return assignment
        except TodoCollaborationError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def effective_owner(self, *, tenant_id: int, todo_id: int) -> EffectiveOwner:
        with self._session_factory() as db:
            todo = self._load_todo(db, tenant_id, todo_id)
            active = self._active_assignment(db, tenant_id, todo_id)
            if active is not None:
                return EffectiveOwner("CLAIMED", int(active.owner_user_id), int(active.id))
            if int(todo.assignee_id) > 0:
                return EffectiveOwner("DIRECT", int(todo.assignee_id), None)
            return EffectiveOwner("POOL", None, None)

    @staticmethod
    def _require_staff_actor(user: dict, tenant_id: int) -> int:
        actor_id = _actor_id(user)
        raw_tenant = (user or {}).get("tenantId") or (user or {}).get("tenant_id")
        try:
            tenant_matches = int(raw_tenant) == int(tenant_id) and int(tenant_id) > 0
        except (TypeError, ValueError):
            tenant_matches = False
        if actor_id <= 0 or _is_student(user) or not tenant_matches:
            raise TodoCollaborationError("NO_PERMISSION", "仅有效教职工身份可执行待办协作", http_status=403)
        return actor_id

    @staticmethod
    def _assert_expected_version(todo: UnifiedTodo, expected_version: int) -> None:
        if int(todo.version or 0) != int(expected_version):
            raise TodoCollaborationError("VERSION_CONFLICT", "待办版本已变化，请刷新后重试", http_status=409)

    @staticmethod
    def _load_todo(db: Session, tenant_id: int, todo_id: int) -> UnifiedTodo:
        todo = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == int(tenant_id),
            UnifiedTodo.is_deleted.is_(False),
        )).first()
        if todo is None:
            raise TodoCollaborationError("TODO_NOT_FOUND", "待办不存在", http_status=404)
        return todo

    def _load_todo_for_update(self, db: Session, tenant_id: int, todo_id: int) -> UnifiedTodo:
        todo = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == int(tenant_id),
            UnifiedTodo.is_deleted.is_(False),
        ).with_for_update()).first()
        if todo is None:
            raise TodoCollaborationError("TODO_NOT_FOUND", "待办不存在", http_status=404)
        return todo

    @staticmethod
    def _active_assignment(
        db: Session, tenant_id: int, todo_id: int, *, lock: bool = False,
    ) -> TodoWorkAssignment | None:
        stmt = select(TodoWorkAssignment).where(
            TodoWorkAssignment.tenant_id == int(tenant_id),
            TodoWorkAssignment.todo_id == int(todo_id),
            TodoWorkAssignment.status == "ACTIVE",
            TodoWorkAssignment.released_at.is_(None),
            TodoWorkAssignment.is_deleted.is_(False),
        ).order_by(TodoWorkAssignment.id.desc()).limit(1)
        if lock:
            stmt = stmt.with_for_update()
        return db.scalars(stmt).first()

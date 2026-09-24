"""Same-session writer for append-only lifecycle projection facts.

This service never opens or commits a session. Canonical domain commands must pass their
own transaction, so a business rollback also rolls back the fact.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact

_VISIBILITY_CODES = {
    "STUDENT_SELF_ONLY",
    "STUDENT_SELF_AND_SCOPED_STAFF",
    "SCOPED_STAFF_ONLY",
    "RESTRICTED_STAFF_ONLY",
}
_SENSITIVITY_LEVELS = {"PUBLIC", "INTERNAL", "PERSONAL", "SENSITIVE", "HIGHLY_SENSITIVE"}


@dataclass(frozen=True, slots=True)
class LifecycleFactInput:
    student_id: int
    college_id: int | None
    source_module: str
    fact_type: str
    source_biz_type: str
    source_biz_id: str
    source_version: str
    event_time: datetime
    title: str
    summary: str | None
    importance: str
    visibility_code: str
    sensitivity_level: str
    target_ref: dict[str, Any] | None
    metadata: dict[str, Any] | None = None
    created_by: int | None = None


def fact_dedupe_key(fact: LifecycleFactInput) -> str:
    identity = {
        "sourceModule": fact.source_module,
        "factType": fact.fact_type,
        "sourceBizType": fact.source_biz_type,
        "sourceBizId": fact.source_biz_id,
        "sourceVersion": fact.source_version,
    }
    raw = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _tenant_id() -> int:
    raw = str(current_tenant_id() or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return int(raw)


def _validate_target_ref(value: Any, path: str = "targetRef") -> None:
    if value is None:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"url", "path", "href", "route"}:
                raise AppException("VALIDATION_ERROR", f"{path} 只能保存 typed target")
            _validate_target_ref(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_target_ref(child, f"{path}[{index}]")
    elif isinstance(value, str) and (value.startswith("/") or "://" in value):
        raise AppException("VALIDATION_ERROR", f"{path} 不能保存原始 URL")


def record_in_session(db, fact: LifecycleFactInput) -> StudentLifecycleFact:
    """Idempotently append a fact inside the caller's existing transaction."""
    tenant_id = _tenant_id()
    if fact.student_id <= 0 or not fact.source_biz_id or not fact.source_version:
        raise AppException("VALIDATION_ERROR", "生命周期 Fact 源身份不完整")
    if len(fact.title) > 200 or (fact.summary is not None and len(fact.summary) > 500):
        raise AppException("VALIDATION_ERROR", "生命周期 Fact 展示文本超过上限")
    if str(fact.visibility_code).upper() not in _VISIBILITY_CODES:
        raise AppException("VALIDATION_ERROR", "生命周期 Fact visibilityCode 不受支持")
    if str(fact.sensitivity_level).upper() not in _SENSITIVITY_LEVELS:
        raise AppException("VALIDATION_ERROR", "生命周期 Fact sensitivityLevel 不受支持")
    if not isinstance(fact.target_ref, dict) or not str(fact.target_ref.get("type") or "").strip() \
            or not str(fact.target_ref.get("id") or "").strip():
        raise AppException("VALIDATION_ERROR", "生命周期 Fact 必须保存 typed target")
    _validate_target_ref(fact.target_ref)
    dedupe = fact_dedupe_key(fact)
    existing = db.scalars(select(StudentLifecycleFact).where(
        StudentLifecycleFact.tenant_id == tenant_id,
        StudentLifecycleFact.dedupe_key == dedupe,
    ).limit(1)).first()
    if existing is not None:
        return existing

    values = {
        "tenant_id": tenant_id,
        "student_id": fact.student_id,
        "college_id": fact.college_id,
        "source_module": fact.source_module,
        "fact_type": fact.fact_type,
        "source_biz_type": fact.source_biz_type,
        "source_biz_id": fact.source_biz_id,
        "source_version": fact.source_version,
        "event_time": fact.event_time,
        "recorded_at": datetime.utcnow(),
        "title": fact.title,
        "summary": fact.summary,
        "importance": fact.importance,
        "visibility_code": str(fact.visibility_code).upper(),
        "sensitivity_level": str(fact.sensitivity_level).upper(),
        "target_ref_json": fact.target_ref,
        "metadata_json": fact.metadata,
        "dedupe_key": dedupe,
        "created_by": fact.created_by,
    }
    dialect_name = str(getattr(getattr(db, "bind", None), "dialect", None).name or "") \
        if getattr(getattr(db, "bind", None), "dialect", None) is not None else ""
    if dialect_name == "mysql":
        # ON DUPLICATE KEY is a statement inside the caller's transaction. It neither commits
        # nor rolls back the canonical mutation, while the unique key closes the concurrency race.
        statement = mysql_insert(StudentLifecycleFact).values(**values)
        db.execute(statement.on_duplicate_key_update(id=StudentLifecycleFact.id))
        row = db.scalars(select(StudentLifecycleFact).where(
            StudentLifecycleFact.tenant_id == tenant_id,
            StudentLifecycleFact.dedupe_key == dedupe,
        ).limit(1)).one()
        return row

    # Non-MySQL is a unit-test/development path only. The pre-read above preserves idempotency;
    # production acceptance remains MySQL and uses the atomic statement above.
    row = StudentLifecycleFact(**values)
    db.add(row)
    db.flush()
    return row

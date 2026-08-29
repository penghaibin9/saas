from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.modules.platform.document_lifecycle import lifecycle_projection_service as service


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def scalars(self, statement):
        self.statements.append(statement)
        return _Scalars(self.rows)


def _fact(row_id: int, *, visibility: str, sensitivity: str = "PERSONAL"):
    return SimpleNamespace(
        id=row_id,
        source_module="graduation",
        fact_type="GRADUATION_ARCHIVED",
        event_time=datetime(2026, 8, 29, 10, 0, 0) - timedelta(minutes=row_id),
        title=f"milestone-{row_id}",
        summary=f"summary-{row_id}",
        importance="HIGH",
        visibility_code=visibility,
        sensitivity_level=sensitivity,
        target_ref_json={"type": "GRADUATION_STUDENT", "id": str(row_id)},
    )


def _visibility_values(statement) -> set[str]:
    values: set[str] = set()
    for value in statement.compile().params.values():
        if isinstance(value, (list, tuple)):
            values.update(str(item) for item in value)
    return values


def _prepare(monkeypatch, rows):
    monkeypatch.setattr(service, "_tid", lambda: 101)
    monkeypatch.setattr(
        service,
        "_assert_student_scope",
        lambda _db, student_id, _user: SimpleNamespace(id=student_id, real_name="同学"),
    )
    return _Db(rows)


def test_student_projection_hides_restricted_and_masks_sensitive_summary(monkeypatch) -> None:
    rows = [
        _fact(3, visibility="STUDENT_SELF_AND_SCOPED_STAFF", sensitivity="SENSITIVE"),
        _fact(2, visibility="STUDENT_SELF_ONLY"),
    ]
    db = _prepare(monkeypatch, rows)

    result = service.lifecycle_timeline(
        db, student_id=7, user={"userType": "STUDENT"}, page_size=1,
    )

    assert _visibility_values(db.statements[0]) == {
        "STUDENT_SELF_ONLY", "STUDENT_SELF_AND_SCOPED_STAFF",
    }
    assert result["items"][0]["summary"] is None
    assert result["nextCursor"]
    event_time, row_id = service._decode_cursor(result["nextCursor"])
    assert (event_time, row_id) == (rows[0].event_time, rows[0].id)


def test_staff_restricted_visibility_requires_explicit_sensitive_permission(monkeypatch) -> None:
    rows = [_fact(1, visibility="SCOPED_STAFF_ONLY")]
    db = _prepare(monkeypatch, rows)
    monkeypatch.setattr(service, "has_permission", lambda _user, _permission: False)

    service.lifecycle_timeline(db, student_id=7, user={"userType": "TEACHER"})

    assert _visibility_values(db.statements[0]) == {
        "STUDENT_SELF_AND_SCOPED_STAFF", "SCOPED_STAFF_ONLY",
    }

    privileged = _prepare(monkeypatch, rows)
    monkeypatch.setattr(
        service,
        "has_permission",
        lambda _user, permission: permission == "studentLifecycle.sensitive.view",
    )
    service.lifecycle_timeline(privileged, student_id=7, user={"userType": "TEACHER"})
    assert "RESTRICTED_STAFF_ONLY" in _visibility_values(privileged.statements[0])

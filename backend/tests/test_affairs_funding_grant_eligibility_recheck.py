"""SA-005：助学金真正授予前必须重读 SA-002 困难库资格。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import affairs_funding_scan_guard as guard
from app.services import affairs_funding_service as legacy


class _FakeDb:
    def __init__(self, batch, project):
        self.batch = batch
        self.project = project

    def get(self, model, row_id):
        if model.__name__ == "FundingBatch":
            return self.batch if int(row_id) == int(self.batch.id) else None
        if model.__name__ == "FundingProject":
            return self.project if int(row_id) == int(self.project.id) else None
        raise AssertionError(f"unexpected model lookup: {model}")


def _fixture():
    tenant_id = 1001
    batch = SimpleNamespace(
        id=2001,
        tenant_id=tenant_id,
        project_id=3001,
        is_deleted=False,
    )
    project = SimpleNamespace(
        id=3001,
        tenant_id=tenant_id,
        is_deleted=False,
    )
    application = SimpleNamespace(
        id=4001,
        tenant_id=tenant_id,
        batch_id=batch.id,
        student_id=5001,
        project_type="GRANT",
        status="PUBLICITY",
        check_snapshot_json=json.dumps({"type": "GRANT", "ok": True}),
    )
    return tenant_id, _FakeDb(batch, project), application, project


def test_grant_recheck_blocks_when_difficult_library_qualification_drifted(monkeypatch):
    tenant_id, db, application, _project = _fixture()
    called = []

    monkeypatch.setattr(guard, "_tid", lambda: tenant_id)
    monkeypatch.setattr(
        legacy,
        "_check_grant",
        lambda *_args, **_kwargs: {
            "type": "GRANT",
            "aidLevel": None,
            "inDifficultLibrary": False,
            "aidLevelAllowed": True,
            "ruleVersion": "2026.1",
            "ok": False,
        },
    )
    monkeypatch.setattr(legacy, "_reject_reason", lambda _snapshot: "未进入困难学生库")
    monkeypatch.setattr(guard, "_ORIGINAL_GRANT_ONE", lambda *_args: called.append("GRANTED"))

    before = application.check_snapshot_json
    with pytest.raises(AppException) as exc_info:
        guard._grant_one(db, application)

    assert exc_info.value.code == "DATA_CONFLICT"
    assert exc_info.value.http_status == 409
    assert "助学资格已变化" in exc_info.value.message
    assert called == []
    assert application.status == "PUBLICITY"
    assert application.check_snapshot_json == before


def test_grant_recheck_freezes_current_qualification_before_award(monkeypatch):
    tenant_id, db, application, project = _fixture()
    audits = []
    calls = []
    current = {
        "type": "GRANT",
        "aidLevel": "SPECIAL_DIFFICULT",
        "inDifficultLibrary": True,
        "aidLevelAllowed": True,
        "ruleVersion": "2026.1",
        "ruleSource": "PACKAGE_DEFAULT",
        "evaluatedAt": "2026-08-25T04:30:00",
        "ok": True,
    }

    monkeypatch.setattr(guard, "_tid", lambda: tenant_id)

    def _check(_db, student_id, selected_project):
        assert int(student_id) == int(application.student_id)
        assert selected_project is project
        return current

    monkeypatch.setattr(legacy, "_check_grant", _check)
    monkeypatch.setattr(
        legacy,
        "_audit",
        lambda _db, biz_id, action, detail="": audits.append((biz_id, action, detail)),
    )

    def _original(_db, row):
        calls.append(row.id)
        row.status = "GRANTED"
        return "granted"

    monkeypatch.setattr(guard, "_ORIGINAL_GRANT_ONE", _original)

    assert guard._grant_one(db, application) == "granted"
    assert calls == [application.id]
    assert application.status == "GRANTED"
    frozen = json.loads(application.check_snapshot_json)
    assert frozen["grantEligibilityRecheck"] == current
    assert any(action == "GRANT_ELIGIBILITY_RECHECK" for _, action, _ in audits)


def test_scholarship_grant_primitive_keeps_sa004_semantics(monkeypatch):
    tenant_id, db, application, _project = _fixture()
    application.project_type = "SCHOLARSHIP"
    calls = []

    monkeypatch.setattr(guard, "_tid", lambda: tenant_id)
    monkeypatch.setattr(
        legacy,
        "_check_grant",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("GRANT recheck must not run")),
    )
    monkeypatch.setattr(guard, "_ORIGINAL_GRANT_ONE", lambda _db, row: calls.append(row.id))

    guard._grant_one(db, application)
    assert calls == [application.id]


def test_runtime_install_order_keeps_one_final_grant_gate():
    scan_guard = Path("app/services/affairs_funding_scan_guard.py").read_text("utf-8")
    authority = Path("app/services/affairs_funding_authority_service.py").read_text("utf-8")
    api = Path("app/api/v1/affairs_funding_authority_api.py").read_text("utf-8")

    assert "legacy._grant_one = _grant_one" in scan_guard
    assert "_ORIGINAL_GRANT_ONE = legacy._grant_one" in scan_guard
    assert "eligibilityConflict" in scan_guard
    assert 'for name in ("create_project", "apply", "_grant_one"' in authority
    assert "legacy._grant_one = _grant_one" in authority
    assert "install_funding_scan_guard()" in api

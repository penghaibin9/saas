"""Academic D-W1 archive four-state contract.

Archive eligibility is not boolean. UNKNOWN must never become PASS, while a proven
NOT_APPLICABLE domain is non-blocking and must remain distinguishable from PASS.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _tenant_context():
    from app.core.context import set_tenant

    set_tenant({"tenantId": "1"})
    try:
        yield
    finally:
        set_tenant(None)


class _FakeQuery:
    def __init__(self, *, rows=None, first=None):
        self._rows = list(rows or [])
        self._first = first

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._first


class _ArchiveDb:
    def __init__(self, *, term=None, graduation_batches=None):
        self.term = term
        self.graduation_batches = list(graduation_batches or [])

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "AaTerm":
            return _FakeQuery(first=self.term)
        if name == "AaGraduationAuditBatch":
            return _FakeQuery(rows=self.graduation_batches)
        raise AssertionError(f"unexpected model: {name}")


def _term(*, start=True, end=True):
    return SimpleNamespace(
        id=9,
        tenant_id=1,
        start_date=datetime(2026, 2, 20) if start else None,
        end_date=datetime(2026, 7, 10) if end else None,
        is_deleted=False,
    )


def _batch(status: str, at=datetime(2026, 5, 1)):
    return SimpleNamespace(status=status, generate_at=at, created_at=at)


def _assert_state(result, state: str, *, blocking: bool):
    assert result["result"] == state
    assert result["present"] is (state == "PASS")
    if blocking:
        assert int(result["blockingCount"]) >= 1
    else:
        assert int(result["blockingCount"]) == 0


def test_d_w1_graduation_missing_term_id_is_unknown_not_pass():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    result = policy.evaluate_graduation(_ArchiveDb(), None)
    _assert_state(result, "UNKNOWN", blocking=True)
    assert "学期" in result["remark"]


def test_d_w1_graduation_missing_term_dates_is_unknown_not_pass():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    result = policy.evaluate_graduation(
        _ArchiveDb(term=_term(start=False), graduation_batches=[_batch("ARCHIVED")]),
        9,
    )
    _assert_state(result, "UNKNOWN", blocking=True)
    assert "日期" in result["remark"]


def test_d_w1_graduation_no_batch_in_valid_term_is_not_applicable():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    result = policy.evaluate_graduation(_ArchiveDb(term=_term(), graduation_batches=[]), 9)
    _assert_state(result, "NOT_APPLICABLE", blocking=False)
    assert "未发现" in result["remark"]


def test_d_w1_graduation_unfinished_batch_is_blocked():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    result = policy.evaluate_graduation(
        _ArchiveDb(term=_term(), graduation_batches=[_batch("PRECHECKED")]),
        9,
    )
    _assert_state(result, "BLOCKED", blocking=True)


def test_d_w1_graduation_archived_batches_pass():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    result = policy.evaluate_graduation(
        _ArchiveDb(term=_term(), graduation_batches=[_batch("ARCHIVED")]),
        9,
    )
    _assert_state(result, "PASS", blocking=False)


def test_d_w1_public_result_preserves_unknown_and_not_applicable_semantics():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    unknown = service._public_result("GRADUATION", {
        "recordCount": 0,
        "present": False,
        "result": "UNKNOWN",
        "blockingCount": 1,
        "summary": "学期证据不完整",
    })
    not_applicable = service._public_result("GRADUATION", {
        "recordCount": 0,
        "present": False,
        "result": "NOT_APPLICABLE",
        "blockingCount": 0,
        "summary": "本学期不适用毕业审核",
    })

    assert unknown["result"] == "UNKNOWN" and unknown["blockingCount"] == 1
    assert not_applicable["result"] == "NOT_APPLICABLE" and not_applicable["blockingCount"] == 0



def _manifest_domains(*, graduation_state: str):
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    states = {}
    for code, _label in service._DOMAINS:
        state = graduation_state if code == "GRADUATION" else "PASS"
        states[code] = {
            "recordCount": 0,
            "present": state == "PASS",
            "result": state,
            "blockingCount": 1 if state in {"BLOCKED", "UNKNOWN"} else 0,
            "ruleCode": f"{code}_D_W1_TEST",
            "summary": f"{code}:{state}",
            "evidence": [],
        }
    return states


def test_d_w1_manifest_allows_not_applicable_as_nonblocking(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest

    monkeypatch.setattr(
        manifest.archive_service,
        "_evaluate_domains",
        lambda _db, _term_id, _term_code: _manifest_domains(graduation_state="NOT_APPLICABLE"),
    )
    batch = SimpleNamespace(term_id=9, term_code="2025-2026-2")
    counts, hashes, max_ids = manifest._live_manifest_parts(SimpleNamespace(), batch)
    assert counts["GRADUATION"] == 0
    assert hashes["GRADUATION"]
    assert max_ids["GRADUATION"] is None


def test_d_w1_manifest_blocks_unknown_before_formal_archive(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest

    monkeypatch.setattr(
        manifest.archive_service,
        "_evaluate_domains",
        lambda _db, _term_id, _term_code: _manifest_domains(graduation_state="UNKNOWN"),
    )
    batch = SimpleNamespace(term_id=9, term_code="2025-2026-2")
    with pytest.raises(AppException) as exc:
        manifest._live_manifest_parts(SimpleNamespace(), batch)
    assert exc.value.http_status == 409
    assert "GRADUATION:GRADUATION_D_W1_TEST" in exc.value.details["blockingRules"]

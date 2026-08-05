from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models import EmpStudent
from app.modules.academic_affairs.services import academic_affairs_graduation_service as service
from app.modules.academic_affairs.services import academic_affairs_graduation_truth_guard as guard


class _ScalarResult:
    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeDb:
    def __init__(self, *responses):
        self.responses = list(responses)

    def scalars(self, _statement):
        if not self.responses:
            raise AssertionError("unexpected scalar query")
        return _ScalarResult(self.responses.pop(0))


@pytest.fixture(autouse=True)
def _tenant(monkeypatch):
    monkeypatch.setattr(guard, "_tid", lambda: 1)


def _row(**kwargs):
    defaults = {
        "id": 1,
        "status": None,
        "is_deleted": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_guard_is_installed_on_public_graduation_service():
    assert service._run_items is guard.strict_run_items
    assert service._check_domain_exists is guard.strict_domain_check


def test_generic_domain_without_authoritative_rule_never_passes():
    db = _FakeDb([_row(id=41)])
    result = guard.strict_domain_check(
        db,
        "EMPLOYMENT",
        EmpStudent,
        "student_id",
        _row(id=9),
        "AA_STAFF",
    )
    assert result["result"] == "UNKNOWN"
    assert "禁止仅按记录存在判定通过" in result["evidence"]


def test_preparing_internship_record_is_not_graduation_complete():
    db = _FakeDb([_row(id=11, status="PREPARING")])
    result = guard._check_internship_completion(db, _row(id=9))
    assert result["result"] == "FAIL"
    assert result["refId"] == "11"


def test_archived_internship_requires_published_passing_score_and_valid_archive():
    record = _row(id=11, status="ARCHIVED")
    score = _row(id=21, status="PENDING_REVIEW", is_pass=True, incomplete=False)
    archive = _row(
        id=31,
        status="ARCHIVED",
        completeness=100,
        force_reason=None,
        force_evidence_file_ids=None,
        force_approved_by=None,
        force_approved_role=None,
    )
    db = _FakeDb([record], [score], [archive])
    result = guard._check_internship_completion(db, _row(id=9))
    assert result["result"] == "FAIL"


def test_archived_internship_with_authoritative_chain_passes():
    record = _row(id=11, status="ARCHIVED")
    score = _row(id=21, status="PUBLISHED", is_pass=True, incomplete=False)
    archive = _row(
        id=31,
        status="ARCHIVED",
        completeness=100,
        force_reason=None,
        force_evidence_file_ids=None,
        force_approved_by=None,
        force_approved_role=None,
    )
    db = _FakeDb([record], [score], [archive])
    result = guard._check_internship_completion(db, _row(id=9))
    assert result["result"] == "PASS"
    assert result["sourceObjectIds"] == {
        "internshipRecordId": "11",
        "finalScoreId": "21",
        "archiveId": "31",
    }


def test_archived_graduation_student_with_draft_grade_does_not_pass():
    student = _row(id=51, stage="ARCHIVED", record_status="ACTIVE")
    grade = _row(id=61, status="DRAFT", total_score=90, grade_level="优秀")
    archive = _row(id=71, status="FILED", manifest_hash="abc")
    db = _FakeDb([student], [grade], [archive])
    result = guard._check_graduation_design_completion(db, _row(id=9))
    assert result["result"] == "FAIL"


def test_graduation_design_requires_published_pass_and_filed_manifest():
    student = _row(id=51, stage="ARCHIVED", record_status="ACTIVE")
    grade = _row(
        id=61,
        status="PUBLISHED",
        total_score=80,
        grade_level="良好",
        source_snapshot_hash="grade-hash",
    )
    archive = _row(id=71, status="FILED", manifest_hash="manifest-hash")
    db = _FakeDb([student], [grade], [archive])
    result = guard._check_graduation_design_completion(db, _row(id=9))
    assert result["result"] == "PASS"
    assert result["sourceManifestHash"] == "manifest-hash"
    assert result["sourceGradeHash"] == "grade-hash"


@pytest.mark.parametrize(
    "grade",
    [
        _row(status="PUBLISHED", total_score=59, grade_level="及格"),
        _row(status="PUBLISHED", total_score=90, grade_level="不及格"),
        _row(status="WITHDRAWN", total_score=90, grade_level="优秀"),
    ],
)
def test_invalid_graduation_grade_never_counts_as_passed(grade):
    assert guard._is_passing_graduation_grade(grade) is False


def test_employment_record_is_nonblocking_unknown_not_fake_pass():
    employment = _row(
        id=81,
        destination_type="EMPLOYED",
        verify_status="VERIFIED",
        material_status="APPROVED",
    )
    db = _FakeDb([employment])
    result = guard._check_employment_evidence(db, _row(id=9))
    assert result["result"] == "UNKNOWN"
    assert "禁止仅因存在记录判定通过" in result["evidence"]

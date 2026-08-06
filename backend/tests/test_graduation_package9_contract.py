"""包 9 反向合同：稳定导师、答辩权威门禁、严格清单与版本化归档。"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import GraduationArchiveRecord, GraduationBatch, GraduationStudent
from app.modules.graduation.policies import defense_policy
from app.modules.graduation.schemas.graduation_mentor import MentorAssignRequest, MentorChangeRequest
from app.modules.graduation.services import graduation_mentor_subject_guard as subject_guard
from app.modules.graduation.services import graduation_package9_guard as package9


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"gdStudentId": "1", "mentorId": "11"}, "INTERNAL:11"),
        ({"gdStudentId": "1", "externalAdvisorId": "21"}, "EXTERNAL:21"),
    ],
)
def test_assign_request_accepts_exactly_one_typed_stable_subject(payload, expected):
    body = MentorAssignRequest(**payload)
    assert body.mentorId == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"gdStudentId": "1"},
        {"gdStudentId": "1", "mentorId": "11", "externalAdvisorId": "21"},
        {"gdStudentId": "1", "advisorName": "同名导师"},
        {"gdStudentId": "1", "mentorId": "同名导师"},
        {"gdStudentId": "1", "externalAdvisorId": "-1"},
    ],
)
def test_assign_request_rejects_missing_ambiguous_name_or_invalid_subject(payload):
    with pytest.raises(ValidationError):
        MentorAssignRequest(**payload)


def test_change_request_preserves_internal_or_external_subject_type():
    legacy = MentorChangeRequest(gdStudentId="1", newMentorId="11", reason="调整原因不少于五字")
    internal = MentorChangeRequest(gdStudentId="1", mentorId="12", reason="调整原因不少于五字")
    external = MentorChangeRequest(gdStudentId="1", externalAdvisorId="21", reason="调整原因不少于五字")
    assert legacy.newMentorId == "INTERNAL:11"
    assert internal.newMentorId == "INTERNAL:12"
    assert external.newMentorId == "EXTERNAL:21"


def test_batch_assignment_rejects_name_and_preserves_external_subject_type():
    assert subject_guard.normalize_assignment_item({
        "gdStudentId": "1", "externalAdvisorId": "21",
    })["mentorId"] == "EXTERNAL:21"
    assert subject_guard.normalize_assignment_item({
        "gdStudentId": "1", "mentorId": "11",
    })["mentorId"] == "INTERNAL:11"
    with pytest.raises(AppException) as exc:
        subject_guard.normalize_assignment_item({"gdStudentId": "1", "advisorName": "同名导师"})
    assert exc.value.code == "VALIDATION_ERROR"


def test_typed_subject_guard_rejects_wrong_mentor_type(monkeypatch):
    mentors = {
        "11": SimpleNamespace(id=11, mentor_type="INTERNAL"),
        "21": SimpleNamespace(id=21, mentor_type="ENTERPRISE"),
        "31": SimpleNamespace(id=31, mentor_type="DUAL"),
    }
    monkeypatch.setattr(subject_guard, "_PREVIOUS_GET_MENTOR", lambda db, mid: mentors[str(mid)])

    assert subject_guard._get_typed_mentor(None, "INTERNAL:11").id == 11
    assert subject_guard._get_typed_mentor(None, "EXTERNAL:21").id == 21
    assert subject_guard._get_typed_mentor(None, "INTERNAL:31").id == 31
    assert subject_guard._get_typed_mentor(None, "EXTERNAL:31").id == 31

    with pytest.raises(AppException) as external_mismatch:
        subject_guard._get_typed_mentor(None, "EXTERNAL:11")
    assert external_mismatch.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as internal_mismatch:
        subject_guard._get_typed_mentor(None, "INTERNAL:21")
    assert internal_mismatch.value.code == "VALIDATION_ERROR"


def _batch(stage_config, status="RUNNING"):
    return GraduationBatch(
        tenant_id=1,
        batch_name="2026 届毕业设计",
        batch_no="GD-2026",
        status=status,
        stage_config=stage_config,
    )


def test_defense_phase_is_fail_closed_when_explicitly_closed_or_outside_window():
    assert defense_policy._defense_phase_open(_batch(None)) is True
    assert defense_policy._defense_phase_open(_batch([
        {"code": "DEFENSE", "status": "CLOSED"},
    ])) is False
    assert defense_policy._defense_phase_open(_batch([
        {"code": "DEFENSE", "startDate": "2026-09-01", "endDate": "2026-09-30"},
    ]), today=date(2026, 8, 6)) is False
    assert defense_policy._defense_phase_open(_batch([], status="CLOSED")) is False


class _ScalarQueue:
    def __init__(self, values):
        self.values = list(values)

    def scalars(self, statement):
        return self

    def first(self):
        return self.values.pop(0)


def test_defense_write_requires_stage_open_batch_published_bound_group(monkeypatch):
    monkeypatch.setattr(defense_policy, "authorize_student_action", lambda *args, **kwargs: True)
    student = SimpleNamespace(
        id=9, tenant_id=1, stage="DEFENSE", batch_id=3, defense_group_id=7,
    )
    batch = SimpleNamespace(status="RUNNING", stage_config=None)
    group = SimpleNamespace(published=True)
    assert defense_policy.authorize(_ScalarQueue([batch, group]), student, "score") is True

    student.stage = "FINAL_CHECK"
    with pytest.raises(AppException) as exc:
        defense_policy.authorize(_ScalarQueue([batch, group]), student, "score")
    assert exc.value.code == "DATA_CONFLICT"


def test_requested_group_id_is_never_authoritative(monkeypatch):
    previous = package9._PREVIOUS_ENTER_SCORE
    monkeypatch.setattr(package9, "_PREVIOUS_ENTER_SCORE", lambda *args, **kwargs: kwargs)
    with pytest.raises(AppException) as exc:
        package9._enter_score("1", "评委", defense_group_id="999")
    assert exc.value.code == "VALIDATION_ERROR"
    result = package9._enter_score("1", "评委")
    assert result["defense_group_id"] is None
    monkeypatch.setattr(package9, "_PREVIOUS_ENTER_SCORE", previous)


def test_archive_version_model_and_migration_freeze_required_fields():
    columns = set(package9.GraduationArchiveVersion.__table__.columns.keys())
    assert {
        "archive_version", "current_flag", "previous_archive_id", "invalidated_reason",
        "source_manifest_json", "source_manifest_hash",
    }.issubset(columns)

    migration = Path("alembic/versions/20260806_gd_package9_archive_versions.py").read_text("utf-8")
    assert 'revision = "20260806_gd_pkg9_archive_ver"' in migration
    assert 'down_revision = "20260804_aa_enrollment_program"' in migration
    assert "uk_gd_archive_version_no" in migration


def test_package9_guard_installs_subject_archive_and_current_fact_guards():
    router_init = Path("app/modules/graduation/routers/__init__.py").read_text("utf-8")
    guard_source = Path("app/modules/graduation/services/graduation_package9_guard.py").read_text("utf-8")
    subject_source = Path("app/modules/graduation/services/graduation_mentor_subject_guard.py").read_text("utf-8")
    terminal_source = Path("app/modules/graduation/services/graduation_archive_terminal_guard.py").read_text("utf-8")
    assert "install_graduation_package9_guard()" in router_init
    assert "install_graduation_mentor_subject_guard()" in router_init
    assert "register_graduation_archive_guard()" in guard_source
    assert "model.is_deleted.is_(False)" in guard_source
    assert "order_by(model.id.desc())" in guard_source
    assert 'status == "FILED"' in terminal_source
    assert "source_manifest_json" in guard_source
    assert "source_manifest_hash" in guard_source
    assert "_strict_manifest_payload" in guard_source
    assert '{"INTERNAL", "DUAL"}' in subject_source
    assert '{"ENTERPRISE", "DUAL"}' in subject_source


def test_archive_filed_appends_mysql_version_chain(db_mode, monkeypatch):
    """真实 MySQL：两次 FILED 形成连续版本，且同一时刻仅一个 current。"""
    from app.db.session import get_sessionmaker

    tenant_id = 1000000000000000001
    monkeypatch.setattr(package9, "_strict_check_completeness", lambda db, student: ([], []))
    monkeypatch.setattr(
        package9,
        "_strict_manifest_payload",
        lambda db, student, archive_no: {
            "tenantId": str(tenant_id),
            "gdStudentId": str(student.id),
            "archiveBatchNo": archive_no,
            "grade": {"id": "1", "status": "PUBLISHED", "version": 1},
            "fileErrors": [],
            "manifestHash": "a" * 64 if archive_no.endswith("01") else "b" * 64,
        },
    )

    db = get_sessionmaker()()
    try:
        student = GraduationStudent(
            tenant_id=tenant_id,
            student_no="PKG9-MYSQL-001",
            name="包9归档测试学生",
            stage="FINAL_CHECK",
            record_status="ACTIVE",
        )
        db.add(student)
        db.flush()
        archive = GraduationArchiveRecord(
            tenant_id=tenant_id,
            gd_student_id=student.id,
            status="PENDING_SUBMIT",
        )
        db.add(archive)
        db.flush()

        archive.status = "FILED"
        archive.archive_batch_no = "PKG9-ARCH-01"
        archive.filed_at = datetime.utcnow()
        archive.verified_by = "mysql-test"
        db.flush()

        first = db.scalars(select(package9.GraduationArchiveVersion).where(
            package9.GraduationArchiveVersion.archive_record_id == archive.id,
        )).one()
        assert first.archive_version == 1
        assert first.current_flag is True
        assert first.previous_archive_id is None
        assert first.source_manifest_hash == "a" * 64

        archive.status = "SUBMITTED"
        db.flush()
        archive.status = "FILED"
        archive.archive_batch_no = "PKG9-ARCH-02"
        archive.filed_at = datetime.utcnow()
        db.flush()
        db.commit()

        rows = list(db.scalars(select(package9.GraduationArchiveVersion).where(
            package9.GraduationArchiveVersion.archive_record_id == archive.id,
        ).order_by(package9.GraduationArchiveVersion.archive_version)).all())
        assert [row.archive_version for row in rows] == [1, 2]
        assert rows[0].current_flag is False
        assert rows[0].invalidated_reason == "SUPERSEDED_BY_REFILING"
        assert rows[1].current_flag is True
        assert rows[1].previous_archive_id == rows[0].id
        assert rows[1].source_manifest_hash == "b" * 64
    finally:
        db.rollback()
        db.close()

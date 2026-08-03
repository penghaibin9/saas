"""归档、谈话和第二课堂核心修复静态合同。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_archive_is_real_scoped_and_not_placeholder_success():
    archive = read("backend/app/services/affairs_archive_service.py")
    resolvers = read("backend/app/services/file_access_resolvers.py")
    assert 'context.require_student(db, student_id)' in archive
    assert 'str(action or "").upper() != "APPROVE"' in archive
    assert 'package.status = "SUBMITTED"' in archive
    assert 'status="SUCCESS"' in archive
    assert 'file_hash=digest' in archive
    assert 'file_obj.biz_type = "AFFAIRS_ARCHIVE"' in archive
    assert '@register_file_resolver("AFFAIRS_ARCHIVE")' in resolvers
    assert 'studentAffairs.archive.view' in resolvers
    assert 'require_student(db, int(student_id))' in resolvers


def test_talk_actions_are_backend_guarded_and_auditable():
    text = read("backend/app/services/affairs_talk_guard.py")
    assert 'StudentProfile.tenant_id == _tid()' in text
    assert 'studentAffairs.risk.psyDetail.view' in text
    assert '该谈话已转风险，不可重复创建' in text
    assert '该谈话已转家校，不可重复创建' in text
    assert '[办结 {stamp}]' in text
    assert '家长回执' in text


def test_second_class_uses_append_only_difference_adjustments():
    text = read("backend/app/services/affairs_activity_accounting_guard.py")
    assert 'AffairsActivityCredit.is_deleted' not in text
    assert 'adjustment = claim if appeal.appeal_type == "MISSING" else claim - current' in text
    assert 'activity_id=None' in text
    assert 'source="MANUAL_ADJUST"' in text
    assert '撤销确认冲正' in text
    assert 'db.delete(' not in text


def test_activity_and_volunteer_dtos_return_actions_and_scope():
    text = read("backend/app/services/affairs_activity_accounting_guard.py")
    assert '"PENDING": ["CONFIRM", "REJECT"]' not in text
    assert '"allowedActions": ["CONFIRM", "REJECT"] if row.status == "PENDING" else []' in text
    assert '"version": int(row.version or 0)' in text
    assert 'build_affairs_context(user, db).require_student(db, sid)' in text
    assert 'require_activity_scope(db, row, user)' in text

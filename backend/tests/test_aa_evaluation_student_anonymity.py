"""学生评教匿名、名单归属与单人单次提交合同。"""
from types import SimpleNamespace

import pytest


def test_anonymous_token_is_deterministic_but_not_plain_identity(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service, "_tid", lambda: 88)
    first = service._submission_token(12, 345)
    second = service._submission_token(12, 345)
    other = service._submission_token(12, 346)

    assert first == second
    assert first != other
    assert "345" not in first
    assert len(first) == 64


def test_anonymous_token_does_not_change_when_jwt_secret_rotates(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service, "_tid", lambda: 88)
    monkeypatch.setattr(service.settings, "FIELD_ENCRYPTION_KEY", "stable-anonymous-data-key")
    monkeypatch.setattr(service.settings, "JWT_SECRET", "jwt-secret-before")
    before = service._submission_token(12, 345)
    monkeypatch.setattr(service.settings, "JWT_SECRET", "jwt-secret-after")
    after = service._submission_token(12, 345)

    assert before == after


def test_missing_anonymous_token_key_fails_closed(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service.settings, "FIELD_ENCRYPTION_KEY", "")
    with pytest.raises(AppException) as exc:
        service._anonymous_token_key()

    assert exc.value.http_status == 500
    assert "凭证密钥未配置" in exc.value.message


def test_reserved_anonymous_token_cannot_be_overridden_by_client():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    encoded = service._encode_student_answers(
        {"q1": 95, service._RESERVED_TOKEN_KEY: "client-forged"},
        "server-signed",
    )

    assert '"q1":95' in encoded
    assert f'"{service._RESERVED_TOKEN_KEY}":"server-signed"' in encoded
    assert "client-forged" not in encoded


def test_non_student_cannot_submit_student_evaluation():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    task = SimpleNamespace(id=1, teaching_task_id=2)
    with pytest.raises(AppException) as exc:
        service._student_submission_context(
            object(),
            {"userType": "STAFF", "currentRoleCode": "ACADEMIC_TEACHER"},
            task,
        )

    assert exc.value.http_status == 403


class _LockQuery:
    def __init__(self, result):
        self.result = result

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args):
        return self

    def group_by(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def populate_existing(self):
        return self

    def with_for_update(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class _LockDb:
    def __init__(self, results):
        self.results = list(results)

    def query(self, *_args):
        return _LockQuery(self.results.pop(0))


def _class_and_version(*, source_type="SELECTION_LOCK", source_id=55):
    teaching_class = SimpleNamespace(id=20, teaching_task_id=4, term_id=7)
    version = SimpleNamespace(
        id=10,
        version_no=3,
        source_type=source_type,
        source_id=source_id,
        roster_hash="hash-10",
        member_count=2,
    )
    return teaching_class, version


def test_student_must_belong_to_current_official_roster(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_evaluation_submit_roster_guard as roster_guard
    from app.services import mobile_student_identity_facade

    profile = SimpleNamespace(id=7)
    roster = {
        "teachingClassId": "20",
        "rosterVersionId": "10",
        "memberCount": 2,
    }
    task = SimpleNamespace(id=3, teaching_task_id=4)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(mobile_student_identity_facade, "resolve_student", lambda _db, _user: profile)
    monkeypatch.setattr(roster_guard, "resolve_submit_roster", lambda _db, _task_id: roster)

    resolved_profile, resolved_roster, _token = service._student_submission_context(
        object(),
        {"userType": "STUDENT", "currentRoleCode": "STUDENT"},
        task,
    )
    assert resolved_profile is profile
    assert resolved_roster is roster

    db = _LockDb([SimpleNamespace(id=20), None])
    with pytest.raises(AppException) as exc:
        service._lock_student_roster_member(db, task, profile, roster)

    assert exc.value.http_status == 403
    assert "不在该课程当前正式教学班名单" in exc.value.message


def test_valid_student_gets_only_pseudonymous_submission_context(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_evaluation_submit_roster_guard as roster_guard
    from app.services import mobile_student_identity_facade

    profile = SimpleNamespace(id=7, student_no="S0007", real_name="张三")
    roster = {"teachingClassId": "20", "memberCount": 2, "rosterVersionId": "10"}
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(mobile_student_identity_facade, "resolve_student", lambda _db, _user: profile)
    monkeypatch.setattr(roster_guard, "resolve_submit_roster", lambda _db, _task_id: roster)

    resolved_profile, resolved_roster, token = service._student_submission_context(
        object(),
        {"userType": "STUDENT", "currentRoleCode": "STUDENT"},
        SimpleNamespace(id=3, teaching_task_id=4),
    )

    assert resolved_profile is profile
    assert resolved_roster is roster
    assert len(token) == 64
    assert profile.student_no not in token
    assert profile.real_name not in token


def test_submit_roster_guard_rejects_latest_selection_before_lock(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_evaluation_submit_roster_guard as roster_guard

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _LockDb([_class_and_version(), (56, "OPEN", 1)])

    with pytest.raises(AppException) as exc:
        roster_guard.resolve_submit_roster(db, 4)

    assert exc.value.code == "DATA_CONFLICT"
    assert "尚未锁定正式名单" in exc.value.message


def test_submit_roster_guard_rejects_stale_selection_projection(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_evaluation_submit_roster_guard as roster_guard

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _LockDb([_class_and_version(source_id=55), (56, "LOCKED", 1)])

    with pytest.raises(AppException) as exc:
        roster_guard.resolve_submit_roster(db, 4)

    assert exc.value.code == "DATA_CONFLICT"
    assert "名单版本与最新已锁定选课批次不一致" in exc.value.message


def test_submit_roster_guard_accepts_matching_locked_selection_projection(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service
    from app.modules.academic_affairs.services import academic_affairs_evaluation_submit_roster_guard as roster_guard

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _LockDb([_class_and_version(source_id=55), (55, "LOCKED", 1)])

    roster = roster_guard.resolve_submit_roster(db, 4)

    assert roster["teachingClassId"] == "20"
    assert roster["rosterVersionId"] == "10"
    assert roster["memberCount"] == 2
    assert roster["batchIds"] == ["55"]


def test_share_batch_hotpath_still_rejects_archived_term(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    batch = SimpleNamespace(id=91, term_id=7)
    db = _LockDb([(batch, "ARCHIVED")])

    with pytest.raises(AppException) as exc:
        service._base._writable_batch(db, 91, lock="share")

    assert exc.value.code == "TERM_ARCHIVED"
    assert "已归档封存" in exc.value.message


def test_student_submit_roster_guard_does_not_materialize_whole_roster():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_evaluation_submit_roster_guard.py"
    ).read_text(encoding="utf-8")

    assert "resolve_versioned_roster" not in source
    assert "ensure_teaching_class_for_task" not in source
    assert "studentIds" not in source
    assert "AaTeachingClassRosterVersion" in source
    assert "AaSelectionBatch.id.desc()" in source
    assert "SELECTION_LOCK" in source
    assert "db.query(AaTeachingClass.id)" in source
    assert "db.query(AaTeachingClassMember.id)" in source
    assert 'term_status.label("_term_status")' in source


def test_student_audit_and_lock_contract_remain_fail_closed():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_evaluation_public_service.py"
    ).read_text(encoding="utf-8")

    assert 'operator="ANONYMOUS_STUDENT"' in source
    assert 'detail="学生匿名评教提交"' in source
    assert "answers_json.like(_token_pattern(" in source
    assert "_lock_student_roster_member" in source
    assert "AaTeachingClassMember" in source
    assert ".with_for_update(read=True)" in source
    assert '"isolation_level": "READ COMMITTED"' in source
    assert "_active_student_submission_count" not in source
    assert '"submittedCount": None' in source
    assert "_increment_student_submission_count" not in source
    # 非学生 SELF/PEER/SUPERVISOR 仍保留独占 Task 行锁守本人+幂等。
    assert ".populate_existing().with_for_update().first()" in source
    assert "settings.JWT_SECRET.encode" not in source
    assert "settings.FIELD_ENCRYPTION_KEY" in source

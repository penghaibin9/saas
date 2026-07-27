"""R9 选课、考勤、考务、成绩统一名单版本回归。

本文件只验证稳定模型和业务契约，不再把 Facade 文件名、函数 __module__ 或源码出现顺序
当成“真实可运行”的证据。数据库事务行为在最终 MySQL 集成阶段执行。
"""
from datetime import datetime
from inspect import signature
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException


def _snapshot(**overrides):
    data = {
        "id": 11,
        "snapshot_version": 2,
        "consumer_type": "GRADE_TASK",
        "consumer_id": 7,
        "teaching_task_id": 31,
        "teaching_class_id": 41,
        "roster_version_id": 51,
        "roster_version_no": 3,
        "roster_source": "SELECTION_LOCK",
        "roster_hash": "hash-1",
        "member_count": 3,
        "student_ids_json": "[1,2,3]",
        "captured_at": datetime(2026, 7, 27, 10, 0, 0),
        "captured_by": "1001",
        "status": "ACTIVE",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _resolved(**overrides):
    data = {
        "teachingClassId": "41",
        "rosterVersionId": "51",
        "rosterVersionNo": 3,
        "rosterHash": "hash-1",
        "memberCount": 3,
        "studentIds": [3, 1, 2, 2],
        "source": "SELECTION_LOCK",
    }
    data.update(overrides)
    return data


def test_roster_consumer_model_has_history_identity_fields():
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    fields = set(AaRosterConsumerSnapshot.__mapper__.attrs.keys())
    assert {
        "consumer_type", "consumer_id", "snapshot_version", "teaching_task_id",
        "teaching_class_id", "roster_version_id", "roster_version_no",
        "roster_source", "roster_hash", "member_count", "student_ids_json",
        "captured_at", "captured_by", "status",
    } <= fields
    unique_names = {
        constraint.name for constraint in AaRosterConsumerSnapshot.__table__.constraints
        if constraint.name
    }
    assert "uk_aa_roster_consumer_version" in unique_names
    assert "uk_aa_roster_consumer" not in unique_names


def test_roster_hash_is_order_independent_and_zero_safe():
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash

    assert roster_hash([3, 1, 2, 2]) == roster_hash([1, 2, 3])
    assert roster_hash([]) == roster_hash(set())
    assert roster_hash([]) != roster_hash([1])


def test_snapshot_dto_uses_real_model_fields_and_sorted_student_ids():
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import _snapshot_dto

    result = _snapshot_dto(_snapshot(), created=True)
    assert result["snapshotId"] == "11"
    assert result["snapshotVersion"] == 2
    assert result["source"] == "SELECTION_LOCK"
    assert result["studentIds"] == [1, 2, 3]
    assert result["status"] == "ACTIVE"
    assert result["created"] is True


def test_snapshot_match_requires_full_roster_identity():
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import _matches

    row = _snapshot()
    assert _matches(row, 31, _resolved()) is True
    assert _matches(row, 31, _resolved(rosterVersionId="52")) is False
    assert _matches(row, 31, _resolved(studentIds=[1, 2, 4])) is False
    assert _matches(row, 32, _resolved()) is False


def test_multiple_active_snapshots_fail_closed():
    from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import _active_row

    rows = [_snapshot(id=1), _snapshot(id=2, snapshot_version=3)]
    with pytest.raises(AppException):
        _active_row(rows)


def test_consumer_snapshot_api_exposes_explicit_replace_and_current_check():
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as service

    params = signature(service.freeze_consumer_snapshot).parameters
    assert "allow_replace" in params
    assert "replace_reason" in params
    assert callable(service.require_consumer_snapshot_current)
    assert callable(service.consumer_snapshot_history)
    assert callable(service.consumer_counts)


def test_r9_migrations_preserve_initial_snapshot_then_enable_history():
    root = Path(__file__).resolve().parents[1]
    initial = (root / "alembic/versions/0129_aa_roster_consumer_snapshot.py").read_text(encoding="utf-8")
    history = (root / "alembic/versions/0133_aa_roster_consumer_history.py").read_text(encoding="utf-8")

    assert 'revision = "0129_aa_roster_consumer_snapshot"' in initial
    assert 'down_revision = "0128_aa_grade_course_identity"' in initial
    assert "禁止迁移时按课程名或行政班猜测" in initial

    assert 'revision = "0133_aa_roster_history"' in history
    assert 'down_revision = "0132_aa_effective_grade_policy"' in history
    assert "snapshot_version" in history
    assert "uk_aa_roster_consumer_version" in history
    assert "SUPERSEDED" in history or "历史证据" in history


def test_grade_resubmit_explicitly_allows_snapshot_replacement_only_after_return():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_grade_service.py"
    ).read_text(encoding="utf-8")

    assert 'was_returned = task.status == "RETURNED"' in source
    assert "allow_replace=was_returned" in source
    assert "成绩任务退回后按当前正式名单重新提交" in source

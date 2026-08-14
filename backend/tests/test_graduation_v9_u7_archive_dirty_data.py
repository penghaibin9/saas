"""U7 archive dirty-data read-only and fail-closed contracts."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.graduation.services.graduation_archive_data_quality import (
    assert_archive_identity_writable,
    identity_anomaly_reasons,
    readonly_missing_markers,
)

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_archive_identity_anomaly_rule_is_shared_and_precise():
    clean = SimpleNamespace(name="张三", student_no="20260001")
    missing_name = SimpleNamespace(name=" ", student_no="20260002")
    missing_both = SimpleNamespace(name=None, student_no="")

    assert identity_anomaly_reasons(clean) == []
    assert identity_anomaly_reasons(missing_name) == ["学生姓名缺失"]
    assert identity_anomaly_reasons(missing_both) == ["学生姓名缺失", "学号缺失"]
    assert readonly_missing_markers(missing_both) == [
        "历史主档异常：学生姓名缺失",
        "历史主档异常：学号缺失",
    ]


def test_archive_identity_anomaly_is_server_side_read_only():
    dirty = SimpleNamespace(name="", student_no="20260003")
    with pytest.raises(AppException) as exc:
        assert_archive_identity_writable(dirty)
    assert exc.value.code == "DATA_CONFLICT"
    assert "仅允许只读查看" in exc.value.message


def test_single_archive_writes_use_batch_bound_dirty_data_guard():
    router = text("backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py")
    assert "assert_archive_identity_writable" in router
    assert "student = load_student_in_batch(db, student_id, batch_id)" in router
    assert router.count("writable=True") == 4
    assert "with_for_update()" not in router


def test_batch_archive_snapshot_keeps_dirty_rows_visible_but_non_executable():
    consistency = text("backend/app/modules/graduation/services/graduation_archive_consistency.py")
    assert '"dataAnomaly": bool(anomaly_reasons)' in consistency
    assert '"anomalyReasons": anomaly_reasons' in consistency
    assert "readonly_missing_markers(student)" in consistency
    assert 'if snap.get("dataAnomaly")' in consistency
    assert '"dirtySkipped": dirty_skipped' in consistency
    assert 'reasons.append("dirty_data")' in consistency


def test_archive_read_model_exposes_explicit_read_only_state_without_mutating_db_status():
    read_model = text("backend/app/modules/graduation/services/graduation_archive_read_service.py")
    assert 'item["status"] = "DATA_ANOMALY"' in read_model
    assert 'item["statusLabel"] = "历史数据异常 · 只读"' in read_model
    assert 'item["statusTone"] = "danger"' in read_model
    assert 'item["allowedActions"] = []' in read_model

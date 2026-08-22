from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w73_summary_exposes_manual_required_metrics():
    service = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    for field in ("pending", "inReview", "returned", "doneToday", "overdue", "avgHours", "byType"):
        assert f'"{field}"' in service
    assert "datetime.now(timezone.utc)" in service
    assert "_processing_hours" in service


def test_w73_queue_defaults_to_business_priority_not_latest_only():
    router = _read("app/modules/graduation/routers/graduation_review_center.py")
    service = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    assert 'sort: Optional[str] = Query(default="PRIORITY")' in router
    assert 'PRIORITY_SORT = "PRIORITY"' in service
    assert '"RETURNED": 0' in service
    assert '"FINAL": 2' in service
    assert '"FORMAL_REVIEW": 3' in service
    assert '"PROPOSAL": 4' in service


def test_w73_deadline_projection_is_conservative_and_read_only():
    service = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    assert "GraduationBatch.stage_config" not in service  # accessed through the loaded batch only
    assert "batch.stage_config" in service
    assert "batch.end_date" in service
    assert 'row["deadlineAt"]' in service
    assert 'row["overdue"]' in service
    for forbidden in ("db.add(", "db.commit(", "update(", "insert(", "delete("):
        assert forbidden not in service


def test_w73_router_uses_contract_completion_service():
    router = _read("app/modules/graduation/routers/graduation_review_center.py")
    assert "graduation_review_center_contract_service as center" in router
    assert "@router.post" not in router
    assert "/review-center/submit" not in router

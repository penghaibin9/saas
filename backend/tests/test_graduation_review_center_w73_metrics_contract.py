from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w73_summary_exposes_manual_required_metrics_and_aggregates_in_mysql():
    facade = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    service = _read("app/modules/graduation/services/graduation_review_center_summary_service.py")
    for field in ("pending", "inReview", "returned", "doneToday", "overdue", "avgHours", "byType"):
        assert f'"{field}"' in facade or f'"{field}"' in service
    assert "graduation_review_center_summary_service as summary_query" in facade
    assert "summary_query.summary(batch_id, reviewer_mentor_id=reviewer_id)" in facade
    assert "q._CTE" in service
    assert "accessible_student_ids" in service
    assert "COUNT(*) AS total" in service
    assert "SUM(CASE" in service
    assert "AVG(CASE" in service
    assert "TIMESTAMPDIFF" in service
    assert "GROUP BY case_type" in service
    assert "[dict(r) for r in db.execute" not in service


def test_w73_queue_defaults_to_business_priority_not_latest_only():
    router = _read("app/modules/graduation/routers/graduation_review_center.py")
    service = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    assert 'sort: Optional[str] = Query(default="PRIORITY")' in router
    assert 'PRIORITY_SORT = "PRIORITY"' in service
    assert '"RETURNED": 0' in service
    assert '"FINAL": 2' in service
    assert '"FORMAL_REVIEW": 3' in service
    assert '"PROPOSAL": 4' in service


def test_w73_deadline_summary_projection_is_conservative_scoped_local_day_and_read_only():
    service = _read("app/modules/graduation/services/graduation_review_center_summary_service.py")
    assert "q._batch_deadlines" in service
    assert "deadlines[case] < now" in service
    assert "status_group IN ('WAITING','IN_REVIEW','RETURNED','BLOCKED')" in service
    assert "q._base_params" in service
    assert "local_today_bounds_utc" in service
    assert "today_start, tomorrow_start = local_today_bounds_utc(now)" in service
    assert "utc_now()" in service
    assert "datetime(now.year, now.month, now.day)" not in service
    for forbidden in ("db.add(", "db.commit(", "update(", "insert(", "delete("):
        assert forbidden not in service


def test_w73_router_uses_contract_completion_service():
    router = _read("app/modules/graduation/routers/graduation_review_center.py")
    assert "graduation_review_center_contract_service as center" in router
    assert "@router.post" not in router
    assert "/review-center/submit" not in router

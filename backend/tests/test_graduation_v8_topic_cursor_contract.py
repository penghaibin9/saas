from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v8_mobile_topics_use_bounded_cursor_contract_without_the_legacy_500_cap():
    service = _text("backend/app/services/mobile_student_service.py")
    router = _text("backend/app/api/v1/mobile.py")

    assert "list_topics(1, 500" not in service
    assert "func.coalesce(GraduationTopic.selected, 0) < func.coalesce(GraduationTopic.capacity, 0)" in service
    for key in ('"items"', '"nextCursor"', '"total"', '"hasMore"'):
        assert key in service
    assert "pageSize: int = Query(default=20, ge=1, le=30)" in router
    for key in ("keyword", "category", "advisor", "cursor"):
        assert f"{key}: str | None" in router

"""选课轮次归档写保护与正式公开入口回归。"""
from pathlib import Path


SERVICES = Path(__file__).resolve().parents[1] / "app/modules/academic_affairs/services"


def test_canonical_round_service_uses_selection_term_archive_guard():
    source = (SERVICES / "academic_affairs_selection_round_service.py").read_text(encoding="utf-8")
    selection_source = (SERVICES / "academic_affairs_selection_service.py").read_text(encoding="utf-8")

    assert "selection_service._guard_batch_writable(db, batch)" in source
    assert "archive_service.guard_term_writable(db, parsed_term_id)" in selection_source
    assert "stmt = stmt.with_for_update()" in selection_source


def test_public_round_compat_path_delegates_all_writes_to_canonical_service():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import (
        academic_affairs_selection_round_facade as compatibility,
        academic_affairs_selection_round_service as canonical,
    )

    public = services.academic_affairs_selection_round_service
    # 保留历史包级模块身份，避免旧 import 路径失效；真正写函数必须来自 canonical owner。
    assert public is compatibility
    assert compatibility._canonical is canonical
    assert compatibility._legacy is canonical
    for name in ("create_round", "open_round", "close_round", "draw_round"):
        assert getattr(public, name) is getattr(canonical, name)
        assert getattr(public, name).__module__.endswith("academic_affairs_selection_round_service")
    assert not hasattr(public, "draw_lottery")


def test_round_compatibility_layer_contains_no_second_write_transaction():
    source = (SERVICES / "academic_affairs_selection_round_facade.py").read_text(encoding="utf-8")

    for forbidden in (
        "AaSelectionRound",
        "AaSelectionCourse",
        "AaSelectionRecord",
        "db.query(",
        "db.add(",
        "db.flush(",
        "db.commit(",
        "hash((",
    ):
        assert forbidden not in source, f"duplicate selection-round business logic returned: {forbidden}"

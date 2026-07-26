"""教材学期写保护、库存容量、异常关闭和第13归档域回归。"""
from types import SimpleNamespace


def _order(status):
    return SimpleNamespace(status=status)


def test_textbook_domain_is_optional_when_term_has_no_order_batch():
    from app.modules.academic_affairs.services.academic_affairs_archive_textbook_facade import (
        _textbook_gate_result,
    )

    result = _textbook_gate_result([])

    assert result["present"] is True
    assert "未启用教材征订" in result["remark"]


def test_textbook_archive_blocks_unfinished_order_distribution_and_fee():
    from app.modules.academic_affairs.services.academic_affairs_archive_textbook_facade import (
        _textbook_gate_result,
    )

    result = _textbook_gate_result(
        [_order("DRAFT"), _order("PARTIALLY_ARRIVED"), _order("ARRIVED")],
        missing_distribution_orders=1,
        unfinished_distributions=2,
        pending_records=3,
        missing_fee_records=4,
        unsettled_fees=5,
    )

    assert result["present"] is False
    assert "未到货/未取消征订批次 2 个" in result["remark"]
    assert "未形成发放批次的征订 1 个" in result["remark"]
    assert "未完成教材发放批次 2 个" in result["remark"]
    assert "待处理教材发放记录 3 条" in result["remark"]
    assert "缺少费用台账 4 条" in result["remark"]
    assert "未结清教材费用 5 条" in result["remark"]


def test_textbook_archive_accepts_arrived_archived_cancelled_and_settled_fees():
    from app.modules.academic_affairs.services.academic_affairs_archive_textbook_facade import (
        _textbook_gate_result,
    )

    result = _textbook_gate_result([
        _order("ARRIVED"),
        _order("ARCHIVED"),
        _order("CANCELLED"),
    ])

    assert result["present"] is True


def test_textbook_input_helpers_dedupe_ids_and_reject_zero_quantity():
    from app.modules.academic_affairs.services.academic_affairs_textbook_final_facade import (
        _invalid_order_quantity_ids,
        _unique_positive_ids,
    )

    assert _unique_positive_ids(["1", 1, "2", "0", "x", None, 3]) == [1, 2, 3]
    rows = [
        SimpleNamespace(id=1, expected_qty=10),
        SimpleNamespace(id=2, expected_qty=0),
        SimpleNamespace(id=3, expected_qty=None),
        SimpleNamespace(id=4, expected_qty="5"),
    ]
    assert _invalid_order_quantity_ids(rows) == [2, 3, 4]


def test_distribution_capacity_counts_only_active_allocations():
    from app.modules.academic_affairs.services.academic_affairs_textbook_roster_facade import (
        _ACTIVE_ALLOCATION_STATUSES,
        _distribution_shortage,
    )

    assert set(_ACTIVE_ALLOCATION_STATUSES) == {"PENDING", "RECEIVED", "EXCHANGED"}
    # 到货30，已有20条有效占用，再发10人刚好；退领/排除不进入allocated。
    assert _distribution_shortage(arrived=30, allocated=20, requested=10) == 0
    assert _distribution_shortage(arrived=30, allocated=20, requested=11) == 1
    # 历史脏数据已超占时，可用量按0处理，禁止继续发放。
    assert _distribution_shortage(arrived=5, allocated=8, requested=2) == 2


def test_textbook_model_term_chain_matches_current_schema():
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        SchoolClass,
    )

    order_fields = set(AaTextbookOrderBatch.__mapper__.attrs.keys())
    fee_fields = set(AaTextbookFeeLedger.__mapper__.attrs.keys())
    distribution_fields = set(AaTextbookDistributionBatch.__mapper__.attrs.keys())
    record_fields = set(AaTextbookDistributionRecord.__mapper__.attrs.keys())
    class_fields = set(SchoolClass.__mapper__.attrs.keys())

    assert "term_id" in order_fields
    assert "term_code" not in order_fields
    assert {"term_id", "term_code"}.isdisjoint(fee_fields)
    assert "order_batch_id" in distribution_fields
    assert "batch_id" in record_fields
    assert "distribution_record_id" in fee_fields
    assert {"class_name", "class_status"} <= class_fields


def test_public_textbook_and_archive_services_point_to_final_layers():
    from app.modules.academic_affairs import services

    archive = services.academic_affairs_archive_service
    textbook = services.academic_affairs_textbook_service

    assert archive.__name__.endswith("academic_affairs_archive_textbook_facade")
    domain_codes = [code for code, _label in archive._legacy._DOMAINS]
    assert {"SELECTION", "MAKEUP", "EVALUATION", "TEXTBOOK"} <= set(domain_codes)
    assert archive._archive_executor._evaluate_domains is archive._evaluate_domains

    assert textbook.__name__.endswith("academic_affairs_textbook_lock_facade")
    assert textbook.generate_distribution.__module__.endswith("academic_affairs_textbook_roster_facade")
    assert textbook.mark_fee.__module__.endswith("academic_affairs_textbook_roster_facade")
    assert textbook.create_order_batch.__module__.endswith("academic_affairs_textbook_final_facade")
    assert textbook.record_arrival.__module__.endswith("academic_affairs_textbook_final_facade")
    assert textbook.cancel_order_batch.__module__.endswith("academic_affairs_textbook_term_facade")
    assert textbook.return_distribution.__module__.endswith("academic_affairs_textbook_final_facade")
    assert textbook._legacy._apply_receipt.__module__.endswith("academic_affairs_textbook_final_facade")
    assert textbook._term_layer._distribution_chain.__module__.endswith("academic_affairs_textbook_lock_facade")
    assert textbook._term_layer._fee_chain.__module__.endswith("academic_affairs_textbook_lock_facade")
    # 教材目录是跨学期主数据，仍由原服务维护，不应被学期写保护包装。
    assert textbook.create_textbook.__module__.endswith("academic_affairs_textbook_service")
    assert textbook.update_textbook.__module__.endswith("academic_affairs_textbook_service")

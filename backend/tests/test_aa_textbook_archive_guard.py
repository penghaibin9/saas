"""教材学期写保护、库存容量、异常关闭和第13归档域回归。"""
from pathlib import Path
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


def test_textbook_archive_checks_each_source_roster_member_across_school_and_colleges(db_mode, monkeypatch):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (AaTeachingTask, AaTerm, AaTextbook, AaTextbookSelection,
        AaTextbookOrderBatch, AaTextbookOrderItem, AaTextbookDistributionBatch,
        AaTextbookDistributionRecord, AaTextbookFeeLedger, AffairsAuditTrail,
        College, Major, SchoolClass, StudentProfile)
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy
    from app.modules.academic_affairs.services import academic_affairs_textbook_final_facade as textbook
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as teaching_classes
    from test_aa_textbook import TID, _seed

    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        first = db.get(StudentProfile, ids["student"])
        first_task = db.get(AaTeachingTask, ids["task"])
        other_college = College(tenant_id=TID, college_name="商贸学院", status="ACTIVE")
        db.add(other_college); db.flush()
        other_major = Major(tenant_id=TID, college_id=other_college.id,
                            major_name="电子商务", status="ACTIVE")
        db.add(other_major); db.flush()
        other_class = SchoolClass(tenant_id=TID, major_id=other_major.id,
                                  class_name="商贸2401", grade="2024", status="ACTIVE")
        db.add(other_class); db.flush()
        second = StudentProfile(tenant_id=TID, student_no="TB2402", real_name="书乙",
                                college_id=other_college.id, major_id=other_major.id,
                                class_id=other_class.id, grade="2024",
                                student_status="NORMAL", status="ACTIVE")
        # 开课任务仍在甲学院批次，领用学生归属按其真实学院判定。
        second_task = AaTeachingTask(tenant_id=TID, batch_id=first_task.batch_id,
                                     course_id=2, course_name="商贸选修", class_id=other_class.id)
        book = AaTextbook(tenant_id=TID, name="共同教材", unit_price=20)
        other_book = AaTextbook(tenant_id=TID, name="乙专用教材", unit_price=15)
        order = AaTextbookOrderBatch(tenant_id=TID, term_id=ids["term"],
                                     batch_name="两院共同教材", status="ARRIVED")
        other_term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1,
                            status="PUBLISHED")
        db.add_all([second, second_task, book, other_book, order, other_term]); db.flush()
        selections = [AaTextbookSelection(tenant_id=TID, task_id=task_id,
            textbook_id=book.id, textbook_name=book.name, expected_qty=1, status="ORDERED")
            for task_id in (first_task.id, second_task.id)]
        selections.append(AaTextbookSelection(tenant_id=TID, task_id=second_task.id,
            textbook_id=other_book.id, textbook_name=other_book.name,
            expected_qty=1, status="ORDERED"))
        item = AaTextbookOrderItem(tenant_id=TID, order_batch_id=order.id,
            textbook_id=book.id, textbook_name=book.name, order_qty=2,
            arrived_qty=2, unit_price_snapshot=20)
        other_item = AaTextbookOrderItem(tenant_id=TID, order_batch_id=order.id,
            textbook_id=other_book.id, textbook_name=other_book.name, order_qty=1,
            arrived_qty=1, unit_price_snapshot=15)
        db.add_all([*selections, item, other_item]); db.flush()
        db.add_all([AffairsAuditTrail(tenant_id=TID, biz_type="AA_TEXTBOOK_ORDER",
            biz_id=order.id, action="TEXTBOOK_ORDER_SOURCE", detail=f"selectionId={selection.id}")
            for selection in selections])
        first_distribution = AaTextbookDistributionBatch(tenant_id=TID,
            order_batch_id=order.id, class_id=ids["class"], status="COMPLETED")
        second_distribution = AaTextbookDistributionBatch(tenant_id=TID,
            order_batch_id=order.id, class_id=other_class.id, status="COMPLETED")
        unrelated_order = AaTextbookOrderBatch(tenant_id=TID, term_id=other_term.id,
            batch_name="别学期教材", status="ARRIVED")
        foreign_order = AaTextbookOrderBatch(tenant_id=TID + 1, term_id=ids["term"],
            batch_name="外校教材", status="ARRIVED")
        db.add_all([first_distribution, second_distribution, unrelated_order, foreign_order]); db.flush()
        unrelated_distribution = AaTextbookDistributionBatch(tenant_id=TID,
            order_batch_id=unrelated_order.id, class_id=other_class.id, status="COMPLETED")
        foreign_distribution = AaTextbookDistributionBatch(tenant_id=TID + 1,
            order_batch_id=foreign_order.id, class_id=other_class.id, status="COMPLETED")
        db.add_all([unrelated_distribution, foreign_distribution]); db.flush()
        received = AaTextbookDistributionRecord(tenant_id=TID,
            batch_id=first_distribution.id, student_id=first.id,
            textbook_id=book.id, status="RECEIVED")
        db.add_all([received,
            AaTextbookDistributionRecord(tenant_id=TID, batch_id=second_distribution.id,
                student_id=second.id, textbook_id=other_book.id, status="EXCLUDED"),
            AaTextbookDistributionRecord(tenant_id=TID, batch_id=unrelated_distribution.id,
                student_id=second.id, textbook_id=book.id, status="EXCLUDED"),
            AaTextbookDistributionRecord(tenant_id=TID + 1, batch_id=foreign_distribution.id,
                student_id=second.id, textbook_id=book.id, status="EXCLUDED")])
        db.flush()
        db.add(AaTextbookFeeLedger(tenant_id=TID, distribution_record_id=received.id,
            student_id=first.id, amount=20, paid_amount=20, status="PAID"))
        order_id, book_id, second_id = order.id, book.id, second.id
        second_task_id = second_task.id
        first_college_id, second_college_id = first.college_id, other_college.id
        second_distribution_id = second_distribution.id
        db.commit()

    set_tenant({"tenantId": str(TID)})
    try:
        with get_sessionmaker()() as db:
            roster = teaching_classes.resolve_teaching_task_roster(db, second_task_id)
            assert roster["ready"] and second_id in roster["studentIds"]
            school = policy.evaluate_textbook(db, ids["term"])
            assert school["present"] is False
            assert "未建教材发放记录 1 条" in school["remark"]
            assert school["evidence"][0]["missingCount"] == 1
            assert school["evidence"][0]["sampleMissing"] == [{
                "orderBatchId": str(order_id), "textbookId": str(book_id),
                "studentId": str(second_id)}]
            own = policy.evaluate_college_textbook(db, ids["term"], {first_college_id})
            other = policy.evaluate_college_textbook(db, ids["term"], {second_college_id})
            assert own["result"] == "UNKNOWN" and own["evidence"][-1]["localMissingCount"] == 0
            assert other["result"] == "BLOCKED"
            assert other["evidence"][-1]["sampleLocalMissing"] == school["evidence"][0]["sampleMissing"]

            db.add(AaTextbookDistributionRecord(tenant_id=TID,
                batch_id=second_distribution_id, student_id=second_id,
                textbook_id=book_id, status="EXCLUDED", exclude_reason="正式排除"))
            db.flush()
            assert policy.evaluate_textbook(db, ids["term"])["present"] is True
            assert policy.evaluate_college_textbook(db, ids["term"],
                {second_college_id})["evidence"][-1]["localMissingCount"] == 0

            original = teaching_classes.resolve_teaching_task_roster
            with monkeypatch.context() as patch:
                patch.setattr(teaching_classes, "resolve_teaching_task_roster",
                    lambda session, task_id: {"ready": False, "note": "正式名单未就绪"}
                    if task_id == second_task_id else original(session, task_id))
                not_ready = policy.evaluate_textbook(db, ids["term"])
            assert not_ready["result"] == "UNKNOWN"
            assert "正式名单未就绪" in not_ready["evidence"][0]["sampleUnknown"][0]["reason"]

            db.add(AffairsAuditTrail(tenant_id=TID, biz_type="AA_TEXTBOOK_ORDER",
                biz_id=order_id, action="TEXTBOOK_ORDER_SOURCE", detail="selectionId=bad"))
            db.flush()
            unknown = policy.evaluate_textbook(db, ids["term"])
            assert unknown["result"] == "UNKNOWN"
            assert "来源" in unknown["evidence"][0]["sampleUnknown"][0]["reason"]
            college = policy.evaluate_college_textbook(db, ids["term"], {first_college_id})
            assert college["result"] == "UNKNOWN"
            assert "sampleUnknown" not in college["evidence"][-1]
    finally:
        set_tenant(None)


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
    from app.modules.academic_affairs.services.academic_affairs_textbook_final_facade import (
        _ACTIVE_ALLOCATION_STATUSES,
        _distribution_shortage,
    )

    assert set(_ACTIVE_ALLOCATION_STATUSES) == {"PENDING", "RECEIVED", "EXCHANGED"}
    assert _distribution_shortage(arrived=30, allocated=20, requested=10) == 0
    assert _distribution_shortage(arrived=30, allocated=20, requested=11) == 1
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


def test_public_textbook_service_exposes_one_lifecycle_contract_without_patch_layers():
    from app.modules.academic_affairs import services

    textbook = services.academic_affairs_textbook_service
    assert textbook.__name__.endswith("academic_affairs_textbook_final_facade")
    for name in (
        "create_selection", "submit_selection", "withdraw_selection",
        "create_review_batch", "review_batch_advance",
        "create_order_batch", "submit_order", "record_arrival", "archive_order_batch",
        "cancel_order_batch", "generate_distribution", "sign_receipt", "sign_receipt_my",
        "return_distribution", "mark_fee", "textbook_stock",
    ):
        assert callable(getattr(textbook, name))

    root = Path(__file__).resolve().parents[1]
    for filename in (
        "academic_affairs_textbook_final_facade.py",
        "academic_affairs_textbook_term_facade.py",
        "academic_affairs_textbook_roster_facade.py",
        "academic_affairs_textbook_lock_facade.py",
        "academic_affairs_textbook_order_guard_facade.py",
    ):
        source = (root / "app/modules/academic_affairs/services" / filename).read_text(encoding="utf-8")
        assert "setattr(" not in source
        assert "sys.modules" not in source
        assert "_legacy.create_" not in source
        assert "_legacy.generate_distribution =" not in source
        assert "_legacy.mark_fee =" not in source

    assert textbook.create_textbook is textbook._legacy.create_textbook
    assert textbook.update_textbook is textbook._legacy.update_textbook

"""教材静态施工的隔离行为/查询构造检查；不连接数据库，不替代 MySQL 验收。"""
import unittest
from contextlib import contextmanager, ExitStack
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import patch

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Query, Session

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_textbook_final_facade as service
from app.modules.academic_affairs.services import academic_affairs_textbook_read_service as reads


class TextbookFlowTests(unittest.TestCase):
    @contextmanager
    def isolated(self, scope="TENANT_ALL", **results):
        statements = []
        db = Session()
        ctx = NS(scope_type=scope, college_ids={7}, permission_codes={"academicAffairs.textbook.review.manage"})

        @contextmanager
        def session():
            yield db

        def answer(kind):
            def call(query, *args, **kwargs):
                statements.append(str(query.statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True})))
                return results.get(kind, [] if kind == "all" else 0)
            return call

        with ExitStack() as stack:
            for module in {reads.legacy, service._legacy}:
                stack.enter_context(patch.object(module, "session", session))
                stack.enter_context(patch.object(module, "_ctx", return_value=ctx))
                stack.enter_context(patch.object(module, "_tid", return_value=42))
            for kind in ["all", "scalar", "one", "count", "first"]:
                stack.enter_context(patch.object(Query, kind, answer(kind)))
            stack.enter_context(patch.object(db, "commit"))
            yield statements, ctx, db
        db.close()

    def test_review_one_college_action_then_one_school_action_and_old_nodes(self):
        source = NS(item_count=1, owner_count=1, college_count=1, college_id=7,
                    min_term_id=5, max_term_id=5, reviewing_count=1, writable_count=1)
        for start, scope, expected in [("DRAFT", "COLLEGE", "COLLEGE_APPROVED"),
                                       ("COLLEGE_REVIEWING", "COLLEGE", "COLLEGE_APPROVED"),
                                       ("COLLEGE_APPROVED", "TENANT_ALL", "PUBLISHED"),
                                       ("ACADEMIC_APPROVED", "TENANT_ALL", "PUBLISHED")]:
            with self.subTest(start=start), self.isolated(scope, all=[NS(status="REVIEWING")], first=source):
                batch = NS(id=9, batch_name="教材审核", term_id=5, college_id=7, status=start, reject_reason=None)
                with patch.object(service, "_get_review_batch", return_value=batch), patch.object(service, "_term"), patch.object(service._legacy, "_audit") as audit:
                    result = service.review_batch_advance({}, 9, "APPROVE")
                self.assertEqual(result["status"], expected)
                audit.assert_called_once()

    def test_review_wrong_role_and_published_batch_cannot_advance(self):
        source = NS(item_count=1, owner_count=1, college_count=1, college_id=7,
                    min_term_id=5, max_term_id=5, reviewing_count=1, writable_count=1)
        for status, scope in [("DRAFT", "TENANT_ALL"), ("COLLEGE_APPROVED", "COLLEGE"), ("PUBLISHED", "TENANT_ALL")]:
            with self.subTest(status=status), self.isolated(scope, all=[], first=source):
                batch = NS(id=9, term_id=5, college_id=7, status=status)
                with patch.object(service, "_get_review_batch", return_value=batch), patch.object(service, "_term"), patch.object(service._legacy, "_audit") as audit:
                    with self.assertRaises(AppException):
                        service.review_batch_advance({}, 9, "APPROVE")
                    audit.assert_not_called()

    def test_school_only_reads_reject_college_before_loading_rows(self):
        with self.isolated("COLLEGE") as (statements, _, _):
            for fn, args in [(reads.list_order_batches, ()), (reads.list_distribution_records, (1,)),
                             (reads.list_fees, ()), (reads.textbook_stock, ()), (reads.stats, ())]:
                with self.subTest(fn=fn.__name__), self.assertRaises(AppException):
                    fn({}, *args)
            self.assertEqual(statements, [])

    def test_fee_projection_includes_same_tenant_student_and_distribution_source(self):
        fee = NS(id=1, student_id=3, textbook_name="教材", amount=Decimal("12.50"), paid_amount=0, status="UNPAID", waive_reason=None)
        student = NS(real_name="测试学生", student_no="TEST001")
        with self.isolated(scalar=1) as (statements, _, _):
            def read_all(query):
                statements.append(str(query.statement.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True})))
                return [(fee, student, 8)] if len(statements) == 2 else []
            with patch.object(Query, 'all', read_all):
                rows, total = reads.list_fees({}, page=2, page_size=20)
        self.assertEqual(total, 1)
        self.assertEqual((rows[0]["studentName"], rows[0]["studentNo"], rows[0]["distributionBatchId"]), ("测试学生", "TEST001", "8"))
        self.assertIn("LIMIT 20, 20", statements[-2])
        self.assertGreaterEqual(statements[-2].count("tenant_id = 42"), 3)

    def test_fee_history_remains_visible_when_student_profile_is_missing(self):
        fee = NS(id=1, student_id=3, textbook_name="历史教材", amount=10, paid_amount=0, status="UNPAID", waive_reason=None)
        with self.isolated(scalar=1):
            with patch.object(Query, 'all', side_effect=[[(fee, None, None)], []]):
                rows, _ = reads.list_fees({})
        self.assertEqual(rows[0]["studentId"], "3")
        self.assertIsNone(rows[0]["studentName"])

    def test_student_fee_totals_subtract_refund_and_keep_original_payment(self):
        fee = NS(id=1, textbook_name='教材', amount=Decimal('20'), paid_amount=Decimal('7'), status='REFUNDED')
        refund = NS(fee_id=1, amount=Decimal('7'))
        with self.isolated() as (statements, _, _):
            def one(query):
                statements.append(str(query.statement.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True})))
                return (20, 20, 0, 7)
            with patch.object(Query, 'one', one), patch.object(Query, 'scalar', side_effect=[1, Decimal('7')]), patch.object(Query, 'all', side_effect=[[fee], [refund]]):
                data = reads.my_student_fees({}, 3)
        self.assertEqual(data['totalDue'], 0)
        self.assertEqual(data['totalPaid'], 0)
        self.assertEqual(data['totalRefunded'], 7)
        self.assertEqual(data['waivedAmount'], 0)
        self.assertEqual(data['unpaid'], 0)
        self.assertEqual(data['items'][0]['paidAmount'], 7)
        self.assertEqual(data['items'][0]['refundAmount'], 7)
        self.assertIn('NOT (EXISTS', statements[0])
        self.assertIn('student_id = 3', statements[0])

    def test_stats_exclude_cancelled_orders_in_count_and_quantity(self):
        with self.isolated(scalar=0, one=(40, 20)) as (statements, ctx, _):
            ctx.permission_codes.add('academicAffairs.textbook.fee.manage')
            result = reads.stats({})
        self.assertEqual(result["arrivalRate"], 0.5)
        order_count, quantity = statements[2:4]
        for sql in [order_count, quantity]:
            self.assertIn("status != 'CANCELLED'", sql)
            self.assertIn("tenant_id = 42", sql)
        self.assertIn("JOIN", quantity)
        self.assertIn('refundedAmount', result)
        self.assertIn('refundPendingReturnCount', result)
        self.assertTrue(any("t_aa_textbook_refund" in sql and "tenant_id = 42" in sql for sql in statements))
        self.assertTrue(any("status = 'REFUNDED'" in sql for sql in statements))

    def test_stats_without_fee_permission_do_not_query_or_expose_fee_amounts(self):
        with self.isolated(scalar=0, one=(40, 20)) as (statements, _, _):
            result = reads.stats({})
        self.assertFalse(result['feeVisible'])
        self.assertIsNone(result['unpaidAmount'])
        self.assertIsNone(result['refundedAmount'])
        self.assertIsNone(result['refundPendingReturnCount'])
        self.assertFalse(any('t_aa_textbook_fee_ledger' in sql or 't_aa_textbook_refund' in sql for sql in statements))

    def test_distribution_details_include_refund_and_detect_wrong_student(self):
        from app.modules.academic_affairs.services import academic_affairs_textbook_workbench_service as workbench
        record = NS(id=3, student_id=8, textbook_name='教材', qty=1, status='RECEIVED')
        student = NS(student_no='T1', real_name='测试学生')
        fee = NS(id=11, distribution_record_id=3, student_id=9, status='REFUNDED', amount=20, paid_amount=7)
        refund = NS(fee_id=11, amount=7)
        batch = NS(id=4, order_batch_id=5, class_id=6, class_name='测试班', status='DISTRIBUTING')
        order = NS(id=5, batch_name='教材征订')
        with self.isolated() as (_, _, db):
            with patch.object(workbench, 'session', service._legacy.session), patch.object(workbench, '_require_school', return_value=NS(permission_codes={'academicAffairs.textbook.fee.manage'})), patch.object(workbench, '_tid', return_value=42), patch.object(Query, 'first', side_effect=[batch, order]), patch.object(Query, 'count', return_value=1), patch.object(Query, 'all', side_effect=[[(record, student)], [fee], [refund]]):
                rows, total, _ = workbench.list_distribution_records({}, 4)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]['refundAmount'], 7)
        self.assertTrue(rows[0]['feeMismatch'])

    def test_distribution_without_fee_permission_hides_amounts(self):
        from app.modules.academic_affairs.services import academic_affairs_textbook_workbench_service as workbench
        record = NS(id=3, student_id=8, textbook_name='教材', qty=1, status='RECEIVED')
        fee = NS(id=11, distribution_record_id=3, student_id=8, status='REFUNDED', amount=20, paid_amount=7)
        batch = NS(id=4, order_batch_id=5, class_id=6, class_name='测试班', status='DISTRIBUTING')
        with self.isolated():
            with patch.object(workbench, 'session', service._legacy.session), patch.object(workbench, '_require_school', return_value=NS(permission_codes={'academicAffairs.textbook.distribution.manage'})), patch.object(workbench, '_tid', return_value=42), patch.object(Query, 'first', side_effect=[batch, NS(id=5, batch_name='教材征订')]), patch.object(Query, 'count', return_value=1), patch.object(Query, 'all', side_effect=[[(record, NS(student_no='T1', real_name='测试学生'))], [fee]]):
                rows, _, _ = workbench.list_distribution_records({}, 4)
        self.assertEqual(rows[0]['feeStatus'], 'REFUNDED')
        self.assertFalse(rows[0]['feeVisible'])
        self.assertIsNone(rows[0]['amount']); self.assertIsNone(rows[0]['paidAmount']); self.assertIsNone(rows[0]['refundAmount'])

    def test_review_detail_checks_college_before_querying_selections(self):
        source = NS(item_count=1, owner_count=1, college_count=1, college_id=8, min_term_id=5, max_term_id=5)
        with self.isolated("COLLEGE", first=source) as (statements, _, _):
            with patch.object(service, "_get_review_batch", return_value=NS(id=9, term_id=5, college_id=8)):
                with self.assertRaises(AppException):
                    reads.review_items({}, 9)
            self.assertEqual(len(statements), 1)

    def test_catalog_price_rejects_negative_subcent_and_nonfinite(self):
        from pydantic import ValidationError
        from app.modules.academic_affairs.routers.textbook_core_router import TextbookBody
        for price in [-1, "0.001", "NaN", "Infinity", "1000000.00"]:
            with self.subTest(price=price), self.assertRaises(ValidationError):
                TextbookBody(name="教材", unitPrice=price)
        self.assertEqual(TextbookBody(name="教材", unitPrice="0").unitPrice, 0)
        self.assertIsNone(TextbookBody(name="教材").unitPrice)

    def test_review_detail_queries_are_paged_and_retain_selection_reason(self):
        source = NS(item_count=1, owner_count=1, college_count=1, college_id=7, min_term_id=5,
                    max_term_id=5, reviewing_count=1, writable_count=1)
        selection = NS(id=11, task_id=12, textbook_id=13, textbook_name="教材", course_name="课程",
                       expected_qty=30, officer_key=None, remark="实训课程需要", reject_reason=None, status="REVIEWING")
        book = NS(isbn="TEST", edition="新版", publisher="测试出版社")
        batch = NS(id=9, batch_name="审核批次", term_id=5, college_id=7, status="DRAFT", reject_reason=None)
        with self.isolated("COLLEGE", first=source, count=1, all=[(selection, book)]) as (statements, _, _):
            with patch.object(service, "_get_review_batch", return_value=batch):
                rows, total, dto = reads.review_items({}, 9, page=2, page_size=20)
        self.assertEqual(rows[0]["remark"], "实训课程需要")
        self.assertEqual(total, 1)
        self.assertTrue(dto["actions"]["advance"])
        self.assertIn("LIMIT 20, 20", statements[-1])
        self.assertGreaterEqual(statements[-1].count("tenant_id = 42"), 3)

    def test_arrival_locks_parent_before_item_and_flushes_before_aggregation(self):
        item = NS(id=8, order_batch_id=9, order_qty=3, arrived_qty=0)
        order = NS(id=9, term_id=5, status="ORDERED")
        events = []
        with self.isolated(all=[item]) as (statements, _, db):
            def first(query):
                events.append("lock-item" if query._for_update_arg is not None else "locate-item")
                return item

            def parent(*args, **kwargs):
                self.assertTrue(kwargs["lock"])
                events.append("lock-order")
                return order

            with patch.object(Query, "first", first), patch.object(service, "_get_order_batch", side_effect=parent), patch.object(service, "_term"), patch.object(service._legacy, "_audit"), patch.object(db, "flush", side_effect=lambda: events.append("flush")):
                result = service.record_arrival({}, 8, 3)
        self.assertEqual(events, ["locate-item", "lock-order", "lock-item", "flush"])
        self.assertIn("FOR UPDATE", statements[-1])
        self.assertEqual(result["batchStatus"], "ARRIVED")

    def test_zero_price_receipt_can_be_returned_without_changing_fee_history(self):
        record = NS(id=3, student_id=8, status="RECEIVED", exchange_reason=None)
        fee = NS(student_id=8, status="PAID", amount=Decimal("0"), paid_amount=Decimal("0"))
        with self.isolated(first=fee):
            with patch.object(service, "_distribution_chain", return_value=(record, NS(), NS())), patch.object(service, "_refresh_distribution_batch"), patch.object(service._legacy, "_audit") as audit:
                result = service.return_distribution({}, 3, "教材领用后无需使用")
        self.assertEqual(result["status"], "RETURNED")
        self.assertEqual(fee.status, "PAID")
        audit.assert_called_once()

    def test_full_refund_keeps_paid_amount_and_prevents_duplicate_writes(self):
        fee = NS(id=11, status="PARTIAL", amount=Decimal('20'), paid_amount=Decimal('7'))
        record = NS(status="RECEIVED")
        with self.isolated(first=None) as (_, _, db):
            with patch.object(service, '_fee_chain', return_value=(fee, record, NS(), NS())), patch.object(db, 'add') as add, patch.object(service._legacy, '_audit') as audit, patch.object(service._legacy, '_op', return_value='test-officer'):
                result = service.register_refund({}, 11, '学生实际已退还教材费', Decimal('7'))
        self.assertEqual(result['refundAmount'], 7)
        self.assertEqual(fee.paid_amount, Decimal('7'))
        self.assertEqual(fee.status, 'REFUNDED')
        add.assert_called_once(); audit.assert_called_once()
        refund = NS(amount=Decimal('7'))
        with self.isolated(first=refund) as (_, _, db):
            with patch.object(service, '_fee_chain', return_value=(fee, record, NS(), NS())), patch.object(db, 'add') as add:
                result = service.register_refund({}, 11, '学生实际已退还教材费', Decimal('7'))
        self.assertTrue(result['idempotent']); add.assert_not_called()

    def test_refund_rejects_stale_amount_and_wrong_scope(self):
        fee = NS(id=11, status='PAID', amount=Decimal('20'), paid_amount=Decimal('20'))
        for scope, expected in [('TENANT_ALL', Decimal('7')), ('COLLEGE', Decimal('20'))]:
            with self.subTest(scope=scope), self.isolated(scope, first=None) as (_, _, db):
                with patch.object(service, '_fee_chain', return_value=(fee, NS(status='RECEIVED'), NS(), NS())), patch.object(db, 'add') as add:
                    with self.assertRaises(AppException):
                        service.register_refund({}, 11, '学生实际已退还教材费', expected)
                    add.assert_not_called()

    def test_return_requires_refund_proof_and_preserves_original_receipt(self):
        fee = NS(id=11, student_id=8, status='REFUNDED', amount=Decimal('20'), paid_amount=Decimal('7'), waive_reason=None)
        record = NS(id=3, student_id=8, status='RECEIVED', exchange_reason=None)
        with self.isolated() as (_, _, db):
            with patch.object(Query, 'first', side_effect=[fee, NS(amount=Decimal('7'))]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(service, '_refresh_distribution_batch'), patch.object(service._legacy, '_audit'):
                result = service.return_distribution({}, 3, '教材领用后无需使用')
        self.assertEqual(result['status'], 'RETURNED')
        self.assertEqual(fee.status, 'WAIVED'); self.assertEqual(fee.paid_amount, Decimal('7'))

    def test_receipt_rechecks_student_after_lock_before_writing(self):
        record = NS(id=3, student_id=9, status='PENDING')
        with self.isolated() as (_, _, db):
            with patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(db, 'add') as add:
                with self.assertRaises(AppException):
                    service._apply_receipt(db, 3, expected_student_id=8)
                add.assert_not_called()

    def test_receipt_rejects_missing_price_or_invalid_quantity(self):
        for price, qty in [(None, 1), (-1, 1), (10, 0), (500000, 2)]:
            record = NS(id=3, student_id=8, textbook_id=4, qty=qty, status='PENDING')
            with self.subTest(price=price, qty=qty), self.isolated(first=NS(unit_price_snapshot=price)) as (_, _, db):
                with patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(db, 'add') as add:
                    with self.assertRaises(AppException):
                        service._apply_receipt(db, 3)
                    add.assert_not_called()
            self.assertEqual(record.status, 'PENDING')

    def test_receipt_never_recreates_missing_fee_for_historical_signed_record(self):
        record = NS(id=3, student_id=8, textbook_id=4, qty=1, status='RECEIVED')
        with self.isolated() as (_, _, db):
            with patch.object(Query, 'first', side_effect=[NS(unit_price_snapshot=20), None]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(db, 'add') as add:
                with self.assertRaises(AppException):
                    service._apply_receipt(db, 3)
                add.assert_not_called()

    def test_receipt_rejects_existing_fee_for_another_student(self):
        record = NS(id=3, student_id=8, textbook_id=4, qty=1, status='RECEIVED')
        with self.isolated() as (_, _, db):
            with patch.object(Query, 'first', side_effect=[NS(unit_price_snapshot=20), NS(student_id=9, amount=20)]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(db, 'add') as add:
                with self.assertRaises(AppException):
                    service._apply_receipt(db, 3)
                add.assert_not_called()

    def test_pending_receipt_with_existing_fee_is_not_silently_signed(self):
        record = NS(id=3, student_id=8, textbook_id=4, qty=1, status='PENDING')
        with self.isolated() as (_, _, db):
            with patch.object(Query, 'first', side_effect=[NS(unit_price_snapshot=20), NS(student_id=8, amount=20)]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(db, 'add') as add:
                with self.assertRaises(AppException):
                    service._apply_receipt(db, 3)
                add.assert_not_called()
        self.assertEqual(record.status, 'PENDING')

    def test_return_rejects_missing_financial_amounts(self):
        for amount, paid in [(None, 0), (20, None)]:
            fee = NS(student_id=8, status='UNPAID', amount=amount, paid_amount=paid)
            record = NS(id=3, student_id=8, status='RECEIVED')
            with self.subTest(amount=amount, paid=paid), self.isolated(first=fee):
                with patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(service._legacy, '_audit') as audit:
                    with self.assertRaises(AppException):
                        service.return_distribution({}, 3, '教材领用后无需使用')
                    audit.assert_not_called()
            self.assertEqual(record.status, 'RECEIVED')

    def test_receipt_normal_and_idempotent_paths(self):
        for status in ['PENDING', 'RECEIVED']:
            record = NS(id=3, student_id=8, textbook_id=4, textbook_name='教材', qty=1, status=status)
            fee = NS(student_id=8, amount=Decimal('20'), paid_amount=0, status='UNPAID') if status == 'RECEIVED' else None
            with self.subTest(status=status), self.isolated() as (_, _, db):
                with patch.object(Query, 'first', side_effect=[NS(unit_price_snapshot=20), fee]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(service, '_refresh_distribution_batch'), patch.object(service._legacy, '_audit') as audit, patch.object(db, 'add') as add:
                    result = service._apply_receipt(db, 3, expected_student_id=8)
                self.assertEqual(result['amount'], 20)
                self.assertEqual(result['status'], 'RECEIVED')
                self.assertEqual(add.call_count, 1 if status == 'PENDING' else 0)
                self.assertEqual(audit.call_count, 1 if status == 'PENDING' else 0)

    def test_signed_receipt_retry_rejects_inconsistent_payment_state(self):
        record = NS(id=3, student_id=8, textbook_id=4, qty=1, status='RECEIVED')
        fee = NS(student_id=8, amount=Decimal('20'), paid_amount=Decimal('0'), status='PAID')
        with self.isolated() as (_, _, db):
            with patch.object(Query, 'first', side_effect=[NS(unit_price_snapshot=20), fee]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS(id=2))), patch.object(service, '_refresh_distribution_batch') as refresh:
                with self.assertRaises(AppException):
                    service._apply_receipt(db, 3)
                refresh.assert_not_called()

    def test_return_retry_requires_consistent_fee_and_refund(self):
        record = NS(id=3, student_id=8, status='RETURNED')
        fee = NS(id=11, student_id=8, status='WAIVED', amount=Decimal('20'), paid_amount=Decimal('7'))
        for refund, success in [(NS(amount=Decimal('7')), True), (None, False), (NS(amount=Decimal('6')), False)]:
            with self.subTest(refund=refund), self.isolated() as (_, _, db):
                with patch.object(Query, 'first', side_effect=[fee, refund]), patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(service._legacy, '_audit') as audit:
                    if success:
                        self.assertTrue(service.return_distribution({}, 3, '教材领用后无需使用')['idempotent'])
                    else:
                        with self.assertRaises(AppException):
                            service.return_distribution({}, 3, '教材领用后无需使用')
                    audit.assert_not_called()

    def test_fee_mark_rejects_invalid_status_amount_and_unreceived_record(self):
        for status, due, paid, record_status in [('UNKNOWN', 20, 0, 'RECEIVED'), ('PARTIAL', 20, 20, 'RECEIVED'), ('UNPAID', 20, 0, 'PENDING')]:
            fee = NS(status=status, amount=Decimal(due), paid_amount=Decimal(paid))
            with self.subTest(status=status, record=record_status), self.isolated() as (_, _, db):
                with patch.object(service, '_fee_chain', return_value=(fee, NS(status=record_status), NS(), NS())), patch.object(service._legacy, '_audit') as audit:
                    with self.assertRaises(AppException):
                        service.mark_fee({}, 11, 'PAID')
                    audit.assert_not_called()
            self.assertEqual(fee.status, status)

    def test_paid_or_partial_receipt_remains_blocked_from_return(self):
        for status, amount, paid in [("PAID", 10, 10), ("PARTIAL", 10, 3), ("PAID", 10, 0)]:
            with self.subTest(status=status, paid=paid), self.isolated(first=NS(student_id=8, status=status, amount=amount, paid_amount=paid)):
                record = NS(id=3, student_id=8, status="RECEIVED")
                with patch.object(service, "_distribution_chain", return_value=(record, NS(), NS())), patch.object(service._legacy, "_audit") as audit:
                    with self.assertRaises(AppException):
                        service.return_distribution({}, 3, "教材领用后无需使用")
                self.assertEqual(record.status, "RECEIVED")
                audit.assert_not_called()

    def test_return_rejects_fee_belonging_to_another_student(self):
        fee = NS(student_id=9, status='UNPAID', amount=20, paid_amount=0)
        record = NS(id=3, student_id=8, status='RECEIVED')
        with self.isolated(first=fee):
            with patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(service._legacy, '_audit') as audit:
                with self.assertRaises(AppException):
                    service.return_distribution({}, 3, '教材领用后无需使用')
                audit.assert_not_called()
        self.assertEqual(record.status, 'RECEIVED')

    def test_refund_rejects_inconsistent_payment_state(self):
        for status, paid in [('PAID', 7), ('PARTIAL', 20)]:
            fee = NS(id=11, status=status, amount=Decimal('20'), paid_amount=Decimal(paid))
            with self.subTest(status=status), self.isolated(first=None) as (_, _, db):
                with patch.object(service, '_fee_chain', return_value=(fee, NS(status='RECEIVED'), NS(), NS())), patch.object(db, 'add') as add:
                    with self.assertRaises(AppException):
                        service.register_refund({}, 11, '已实际全额退还费用', Decimal(paid))
                    add.assert_not_called()

    def test_existing_refund_with_inconsistent_state_is_not_reported_success(self):
        fee = NS(id=11, status='PAID', amount=Decimal('20'), paid_amount=Decimal('20'))
        with self.isolated(first=NS(amount=Decimal('20'))) as (_, _, db):
            with patch.object(service, '_fee_chain', return_value=(fee, NS(status='RECEIVED'), NS(), NS())), patch.object(db, 'add') as add:
                with self.assertRaises(AppException):
                    service.register_refund({}, 11, '已实际全额退还费用', Decimal('20'))
                add.assert_not_called()

    def test_return_rejects_zero_paid_record_falsely_marked_refunded(self):
        fee = NS(student_id=8, status='REFUNDED', amount=20, paid_amount=0)
        record = NS(id=3, student_id=8, status='RECEIVED')
        with self.isolated(first=fee):
            with patch.object(service, '_distribution_chain', return_value=(record, NS(), NS())), patch.object(service._legacy, '_audit') as audit:
                with self.assertRaises(AppException):
                    service.return_distribution({}, 3, '教材领用后无需使用')
                audit.assert_not_called()

    def test_cancel_rejects_invalid_or_incomplete_source_without_mutating_selection(self):
        for sources, selections, items in [
            ([NS(detail="selectionId=1"), NS(detail="broken")], [], []),
            ([NS(detail="selectionId=1"), NS(detail="selectionId=2")], [NS(id=1, status="ORDERED", expected_qty=2, textbook_id=7)], [NS(textbook_id=7, order_qty=2)]),
            ([NS(detail="selectionId=1")], [NS(id=1, status="ORDERED", expected_qty=2, textbook_id=7)], [NS(textbook_id=7, order_qty=3)]),
        ]:
            batch = NS(id=9, term_id=5, status="DRAFT")
            with self.subTest(sources=sources), self.isolated():
                with patch.object(Query, "all", side_effect=[sources, selections, items]), patch.object(service, "_get_order_batch", return_value=batch), patch.object(service, "_term"), patch.object(service._legacy, "_audit") as audit:
                    with self.assertRaises(AppException):
                        service.cancel_order_batch({}, 9, "需要取消本次征订")
                    audit.assert_not_called()
            self.assertEqual(batch.status, "DRAFT")
            self.assertTrue(all(row.status == "ORDERED" for row in selections))

    def test_cancel_valid_complete_sources_restores_all_selections(self):
        batch = NS(id=9, term_id=5, status="DRAFT", batch_name="征订", submit_at=None, archived_at=None)
        selections = [NS(id=1, status="ORDERED", expected_qty=2, textbook_id=7)]
        with self.isolated():
            with patch.object(Query, "all", side_effect=[[NS(detail="selectionId=1")], selections, [NS(textbook_id=7, order_qty=2)]]), patch.object(service, "_get_order_batch", return_value=batch), patch.object(service, "_term"), patch.object(service._legacy, "_audit"), patch.object(service._legacy, "_ob_dto", return_value={}):
                service.cancel_order_batch({}, 9, "需要取消本次征订")
        self.assertEqual(batch.status, "CANCELLED")
        self.assertEqual(selections[0].status, "APPROVED")

    def test_source_reused_by_another_live_order_is_blocked(self):
        with self.isolated(first=NS(id=31)) as (statements, _, db):
            with self.assertRaises(AppException):
                service._require_unique_order_sources(db, 9, [1, 2])
        self.assertIn("status != 'CANCELLED'", statements[-1])
        self.assertIn('tenant_id = 42', statements[-1])
        self.assertIn("selectionId=1", statements[-1])

    def test_source_not_shared_with_other_live_order_can_proceed(self):
        with self.isolated(first=None) as (statements, _, db):
            service._require_unique_order_sources(db, 9, [1])
        self.assertIn('FOR UPDATE', statements[-1])

    def test_duplicate_source_rows_cannot_create_distribution(self):
        with self.isolated(all=[NS(detail='selectionId=1'), NS(detail='selectionId=1')]) as (_, _, db):
            with self.assertRaises(AppException) as error:
                service._distribution_members(db, NS(id=9, term_id=5), [], [8])
        self.assertIn('重复', error.exception.message)

    def test_order_source_requires_canonical_positive_database_identifier(self):
        self.assertEqual(service._parse_order_source('selectionId=17'), 17)
        for value in ['selectionId=0017', 'selectionId=١٧', 'selectionId=0', 'selectionId=9223372036854775808', 'selectionId=' + '9' * 500, 'selectionId=17 ']:
            with self.subTest(value=value):
                self.assertIsNone(service._parse_order_source(value))

    def test_order_price_rejects_corrupt_negative_or_out_of_range_values(self):
        books = {1: NS(unit_price=Decimal('0')), 2: NS(unit_price=Decimal('-1')),
                 3: NS(unit_price=Decimal('1000000')), 4: NS(unit_price=Decimal('1.001'))}
        self.assertEqual(service._invalid_price_textbook_ids(books, [1, 2, 3, 4]), [2, 3, 4])


if __name__ == "__main__":
    unittest.main()

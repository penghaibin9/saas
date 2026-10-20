"""M8 finance route contract on the real platform registrar.

M8 is deliberately isolated from the frozen M1-M5 24-route surface. These tests
prove the ten finance routes are additive, inherit the real platform identity/PAM
boundary, preserve Idempotency-Key and optimistic versions, and only transport
manual control facts to ``module_commerce_finance_service``.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch


class M8FinanceRouterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import APIRouter, FastAPI
        from app.api.v1.route_registration import register_platform_routes
        from app.core.exceptions import register_exception_handlers
        from app.modules.platform.routers import (
            module_commerce_finance_router,
            module_commerce_router,
            platform_router,
        )
        from app.modules.platform.services import platform_access_governance_legacy

        cls.finance = module_commerce_finance_router
        cls.frozen = module_commerce_router
        cls.canonical = platform_router
        cls.pam = platform_access_governance_legacy
        cls.registered = APIRouter()
        register_platform_routes(cls.registered)
        cls.app = FastAPI()
        register_exception_handlers(cls.app)
        cls.app.include_router(cls.registered, prefix="/api/v1")

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user

        self.actor = {
            "userId": "42",
            "currentRoleCode": "PLATFORM_COMMERCIAL",
            "userType": "PLATFORM_COMMERCIAL",
            "permissions": [],
        }
        self.app.dependency_overrides[get_current_user] = lambda: self.actor
        self.addCleanup(self.app.dependency_overrides.clear)
        records = patch.object(self.pam, "_load_user_records", return_value=([], []))
        self.records = records.start()
        self.addCleanup(records.stop)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    @staticmethod
    def _contexts(router):
        from app.core.commercial_surface_module_gate import iter_effective_route_contexts
        return list(iter_effective_route_contexts(router))

    @classmethod
    def _signatures(cls, router):
        return {
            (str(method).upper(), str(context.path))
            for context in cls._contexts(router)
            for method in (getattr(context, "methods", None) or ())
        }

    def test_m1_m5_frozen_surface_stays_twenty_four_and_m8_adds_exactly_ten(self):
        self.assertEqual(len(self.frozen.router.routes), 24)
        self.assertEqual(len(self.finance.router.routes), 10)
        frozen = self._signatures(self.frozen.router)
        finance = self._signatures(self.finance.router)
        self.assertFalse(frozen & finance)
        canonical = self._signatures(self.canonical.router)
        self.assertTrue(frozen.issubset(canonical))
        self.assertTrue(finance.issubset(canonical))

    def test_repeat_finance_install_is_noop_and_never_replaces_existing_routes(self):
        before = tuple(self.canonical.router.routes)
        self.assertEqual(self.finance.install_into_platform_router(self.canonical.router), 0)
        self.assertEqual(tuple(self.canonical.router.routes), before)

    def test_finance_route_collision_is_atomic(self):
        from fastapi import APIRouter

        target = APIRouter()
        first = self.finance.router.routes[0]
        target.add_api_route(first.path, lambda: {}, methods=list(first.methods))
        before = tuple(target.routes)
        with self.assertRaisesRegex(RuntimeError, "finance route collision"):
            self.finance.install_into_platform_router(target)
        self.assertEqual(tuple(target.routes), before)

    def test_school_wildcard_cannot_enter_any_m8_finance_route(self):
        self.actor.update(currentRoleCode="SCHOOL_ADMIN", userType="ADMIN", permissions=["*"])
        for route in self.finance.router.routes:
            url = "/api/v1" + route.path.format(tenant_id=42, case_id=9, invoice_case_id=10)
            for method in route.methods:
                with self.subTest(method=method, path=route.path):
                    response = self.client.request(
                        method,
                        url,
                        json={},
                        headers={"Idempotency-Key": "finance-route-school-deny"},
                    )
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(response.json()["bizCode"], "NO_PERMISSION")
        self.records.assert_not_called()

    def test_read_routes_transport_filters_to_finance_service(self):
        from app.services import module_commerce_finance_service as finance

        scenarios = [
            ("/api/v1/platform/commercial/tenants/42/finance-orders?page=2&pageSize=7",
             "list_finance_orders", (42,), {"page": 2, "page_size": 7}),
            ("/api/v1/platform/commercial/tenants/42/refunds?status=APPROVED&page=2&pageSize=7",
             "list_refunds", (42,), {"status": "APPROVED", "page": 2, "page_size": 7}),
            ("/api/v1/platform/commercial/tenants/42/invoices?status=ISSUED&page=2&pageSize=7",
             "list_invoices", (42,), {"status": "ISSUED", "page": 2, "page_size": 7}),
        ]
        for url, name, args, kwargs in scenarios:
            with self.subTest(url=url), patch.object(finance, name, return_value={"items": []}) as call:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.text)
                call.assert_called_once_with(*args, **kwargs)

    def test_request_commands_preserve_idempotency_key_and_actor(self):
        from app.services import module_commerce_finance_service as finance

        with patch.object(finance, "request_refund", return_value={"caseId": "1"}) as refund:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/refunds",
                json={"orderId": "11", "amount": "10.00", "currency": "CNY", "reason": "manual review only"},
                headers={"Idempotency-Key": "refund-route-command-001"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            refund.assert_called_once_with(
                {"orderId": "11", "amount": "10.00", "currency": "CNY", "reason": "manual review only", "tenantId": "42"},
                idempotency_key="refund-route-command-001",
                actor_id="42",
            )

        with patch.object(finance, "request_invoice", return_value={"invoiceCaseId": "2"}) as invoice:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/invoices",
                json={"orderId": "11", "amount": "20.00", "currency": "CNY", "invoiceTitle": "测试学校"},
                headers={"Idempotency-Key": "invoice-route-command-001"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            invoice.assert_called_once_with(
                {"orderId": "11", "amount": "20.00", "currency": "CNY", "invoiceTitle": "测试学校", "tenantId": "42"},
                idempotency_key="invoice-route-command-001",
                actor_id="42",
            )

    def test_refund_transitions_preserve_expected_version_and_external_evidence(self):
        from app.services import module_commerce_finance_service as finance

        scenarios = [
            ("approve_refund", "/api/v1/platform/commercial/tenants/42/refunds/9/approve",
             {"expectedVersion": 3, "note": "finance approved"},
             (42, 9), {"expected_version": 3, "note": "finance approved", "actor_id": "42"}),
            ("reject_refund", "/api/v1/platform/commercial/tenants/42/refunds/9/reject",
             {"expectedVersion": 4, "reason": "contract rejected after review"},
             (42, 9), {"expected_version": 4, "reason": "contract rejected after review", "actor_id": "42"}),
            ("settle_refund", "/api/v1/platform/commercial/tenants/42/refunds/9/settle",
             {"expectedVersion": 5, "settlementRef": "BANK-REF-00001"},
             (42, 9), {"expected_version": 5, "settlement_ref": "BANK-REF-00001", "actor_id": "42"}),
        ]
        for name, url, payload, args, kwargs in scenarios:
            with self.subTest(name=name), patch.object(finance, name, return_value={"status": "OK"}) as call:
                response = self.client.post(url, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                call.assert_called_once_with(*args, **kwargs)

    def test_invoice_transitions_preserve_external_reference_but_do_not_require_database_file_id(self):
        from app.services import module_commerce_finance_service as finance

        with patch.object(finance, "issue_invoice", return_value={"status": "ISSUED"}) as issue:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/invoices/10/issue",
                json={"expectedVersion": 2, "externalInvoiceRef": "INV-EXT-00001"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            issue.assert_called_once_with(
                42, 10, expected_version=2, external_invoice_ref="INV-EXT-00001",
                invoice_file_id=None, actor_id="42",
            )

        with patch.object(finance, "void_invoice", return_value={"status": "VOIDED"}) as void:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/invoices/10/void",
                json={"expectedVersion": 3, "reason": "external invoice already voided"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            void.assert_called_once_with(
                42, 10, expected_version=3, reason="external invoice already voided", actor_id="42",
            )

    def test_missing_idempotency_header_stops_before_finance_service(self):
        from app.services import module_commerce_finance_service as finance

        with patch.object(finance, "request_refund") as writer:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/refunds",
                json={"orderId": "11", "amount": "10.00", "currency": "CNY", "reason": "missing command key"},
            )
            self.assertEqual(response.status_code, 400, response.text)
            writer.assert_not_called()

    def test_finance_router_copy_never_claims_external_execution(self):
        from pathlib import Path

        source = Path("app/modules/platform/routers/module_commerce_finance_router.py").read_text(encoding="utf-8")
        for explicit in (
            "系统未执行资金退款",
            "外部资金渠道实际退款后登记凭据",
            "系统未调用税控或第三方开票服务",
            "订单支付真值和模块授权未被自动修改",
        ):
            self.assertIn(explicit, source)
        for forbidden in ("refund_payment(", "payment_gateway", "tax_provider", "cancel_subscription_source_now("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

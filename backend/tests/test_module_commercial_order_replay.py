"""Exercise the real order writer with instrumented IO, without a database."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1] / "app"


def module(name, **values):
    result = ModuleType(name)
    result.__dict__.update(values)
    return result


class OrderReplayTests(unittest.TestCase):
    def setUp(self):
        saved = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
        def restore():
            for name in list(sys.modules):
                if name == "app" or name.startswith("app."):
                    del sys.modules[name]
            sys.modules.update(saved)
        self.addCleanup(restore)
        for name in saved:
            del sys.modules[name]
        self.db = Mock()
        self.factory = Mock(return_value=self.db)
        self.enabled = Mock(return_value=True)
        self.catalog = Mock(side_effect=RuntimeError("catalogue offline"))
        self.audit = Mock(side_effect=AssertionError("replay must not emit another audit"))
        replacements = {
            "app": module("app", __path__=[str(APP)]),
            "app.core": module("app.core", __path__=[str(APP / "core")]),
            "app.models": module("app.models", __path__=[str(APP / "models")]),
            "app.services": module("app.services", __path__=[str(APP / "services")]),
            "app.db": module("app.db", __path__=[str(APP / "db")]),
            "app.core.config": module("app.core.config", settings=SimpleNamespace(TIMEZONE_OFFSET_HOURS=8)),
            "app.core.context": module("app.core.context", get_trace_id=lambda: "order-replay-test"),
            "app.db.session": module("app.db.session", db_enabled=self.enabled,
                                      get_sessionmaker=lambda: self.factory),
            "app.services.commercial_catalog_service": module("app.services.commercial_catalog_service",
                                                               get_sku_snapshot=self.catalog),
            "app.services.audit_log": module("app.services.audit_log", record_critical_in_session=self.audit),
        }
        sys.modules.update(replacements)
        models = replacements["app.models"]
        for name, source in [("Tenant", "tenant"), ("IdempotencyRecord", "idempotency"),
                             ("PlatformOrder", "platform"), ("CommercialOrderItem", "commercial")]:
            setattr(models, name, getattr(importlib.import_module(f"app.models.{source}"), name))
        self.service = importlib.import_module("app.services.commercial_order_item_service")
        self.body = {"tenantId": "42", "currency": "CNY", "totalAmount": "100.00", "items": [{
            "lineNo": 1, "skuCode": "REPLAY-SKU", "skuRevision": 1, "skuContentHash": "a" * 64,
            "quantity": 1, "unitPrice": "100.00", "discountAmount": "0.00", "netAmount": "100.00",
            "startAt": "2026-09-01T00:00:00Z", "endAt": "2027-09-01T00:00:00Z", "requestedGeneration": 1,
        }]}
        contract, order_type, remark = self.service._clean_body(self.body)
        self.receipt = {"orderId": "7", "orderNo": "MO-ORIGINAL", "status": "unpaid",
                        "paymentRecorded": False, "rightsMaterialized": False}
        self.idem = SimpleNamespace(fingerprint=self.service._fingerprint(contract, order_type, remark),
                                    state="COMPLETED", result_json=self.receipt)
        self.reads = []
        self.configure_reads()

    def configure_reads(self, *, tenant=True, idem=True):
        results = iter([SimpleNamespace(id=42) if tenant else None, self.idem if idem else None])
        def scalars(statement):
            self.reads.append(statement)
            return Mock(first=Mock(return_value=next(results)))
        self.db.scalars.side_effect = scalars

    def create(self):
        return self.service.create_itemized_order(self.body, idempotency_key="stable-order-key", actor_id="7")

    def assert_no_write(self):
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.audit.assert_not_called()
        self.db.close.assert_called_once()

    def test_completed_receipt_replays_without_catalogue(self):
        result = self.create()
        self.assertEqual(result, {**self.receipt, "replayed": True})
        self.catalog.assert_not_called()
        result["orderNo"] = "caller mutation"
        self.assertEqual(self.receipt["orderNo"], "MO-ORIGINAL")
        self.assert_no_write()

    def test_payload_conflict_precedes_catalogue_state(self):
        self.body["remark"] = "different contract"
        with self.assertRaises(self.service.AppException) as caught:
            self.create()
        self.assertEqual(caught.exception.http_status, 409)
        self.catalog.assert_not_called()
        self.assert_no_write()

    def test_incomplete_command_never_reexecutes(self):
        self.idem.state = "PROCESSING"
        with self.assertRaises(self.service.AppException) as caught:
            self.create()
        self.assertEqual(caught.exception.http_status, 409)
        self.catalog.assert_not_called()
        self.assert_no_write()

    def test_corrupt_receipt_does_not_create_replacement(self):
        self.idem.result_json = None
        with self.assertRaises(self.service.AppException) as caught:
            self.create()
        self.assertEqual(caught.exception.http_status, 409)
        self.catalog.assert_not_called()
        self.assert_no_write()

    def test_receipt_query_keeps_tenant_actor_operation_and_key_scope(self):
        self.create()
        params = self.reads[1].compile().params
        self.assertEqual(set(params.values()), {42, "7", self.service._OPERATION,
                                               self.service._idempotency_hash("stable-order-key")})
        self.assertIn("FOR UPDATE", str(self.reads[0]))
        self.assertIn("FOR UPDATE", str(self.reads[1]))
        self.assert_no_write()

    def test_missing_tenant_cannot_replay_any_receipt(self):
        self.configure_reads(tenant=False)
        with self.assertRaises(self.service.AppException) as caught:
            self.create()
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(len(self.reads), 1)
        self.catalog.assert_not_called()
        self.assert_no_write()

    def test_new_command_still_requires_live_catalogue(self):
        self.configure_reads(idem=False)
        with self.assertRaisesRegex(RuntimeError, "catalogue offline"):
            self.create()
        self.catalog.assert_called_once()
        self.assert_no_write()

    def test_new_command_cannot_buy_retired_sku(self):
        self.configure_reads(idem=False)
        self.catalog.side_effect = self.service.AppException("DATA_NOT_FOUND", "retired", http_status=404)
        with self.assertRaises(self.service.AppException) as caught:
            self.create()
        self.assertEqual(caught.exception.http_status, 404)
        self.assert_no_write()

    def test_invalid_key_stops_before_session(self):
        with self.assertRaises(self.service.AppException) as caught:
            self.service.create_itemized_order(self.body, idempotency_key="")
        self.assertEqual(caught.exception.http_status, 422)
        self.factory.assert_not_called()
        self.catalog.assert_not_called()


if __name__ == "__main__":
    unittest.main()

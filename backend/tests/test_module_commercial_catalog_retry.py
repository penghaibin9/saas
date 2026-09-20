"""Deterministic transaction fault injection; no live database is used here.

The real SKU compiler/model/service execute against instrumented session IO.
Real MySQL concurrency and audit atomicity are covered separately by M1/M2 CI.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.dialects import mysql

APP = Path(__file__).resolve().parents[1] / "app"


def module(name, **values):
    result = ModuleType(name)
    result.__dict__.update(values)
    return result


def deadlock(*, invalidated=False):
    return OperationalError("private SQL", {}, Exception(1213, "private diagnostic"),
                            connection_invalidated=invalidated)


class CatalogRetryTests(unittest.TestCase):
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
        self.events = []
        self.maker = Mock()
        self.audit = Mock(side_effect=lambda db, *a, **k: self.events.append((db.label, "audit")))
        self.enabled = Mock(return_value=True)
        replacements = {
            "app": module("app", __path__=[str(APP)]),
            "app.core": module("app.core", __path__=[str(APP / "core")]),
            "app.services": module("app.services", __path__=[str(APP / "services")]),
            "app.models": module("app.models", __path__=[str(APP / "models")]),
            "app.db": module("app.db", __path__=[str(APP / "db")]),
            "app.core.config": module("app.core.config", settings=SimpleNamespace(TIMEZONE_OFFSET_HOURS=8)),
            "app.core.context": module("app.core.context", get_trace_id=lambda: "catalog-test"),
            "app.db.session": module("app.db.session", db_enabled=self.enabled,
                                      get_sessionmaker=lambda: self.maker),
            "app.services.audit_log": module("app.services.audit_log", record_critical_in_session=self.audit),
        }
        sys.modules.update(replacements)
        self.model = importlib.import_module("app.models.commercial").CommercialSkuVersion
        replacements["app.models"].CommercialSkuVersion = self.model
        self.service = importlib.import_module("app.services.commercial_catalog_service")
        self.service.sleep = Mock(side_effect=lambda duration: self.events.append(("sleep", duration)))
        self.payload = {"skuCode": "RETRY-SKU", "revision": 1, "name": "immutable test",
                        "productType": "MODULE", "moduleKey": "internship",
                        "features": {"internship": True}, "quotas": {},
                        "pricePolicy": {"unitPrice": "100.00", "currency": "CNY",
                                        "taxTreatment": "UNSPECIFIED"},
                        "lifecyclePolicyVersion": "TEST-1"}
        self.snapshot = self.service.compile_sku(self.payload, known_features=self.service.D.FEATURE_KEYS,
                                                approved_features=self.service.APPROVED_FEATURE_SCOPES)

    def session(self, label, *, existing=None, flush_error=None, commit_error=None, winner=None):
        db = Mock()
        db.label = label
        db.queries = []
        rows = iter([existing, winner])

        def scalars(query):
            db.queries.append(str(query.compile(dialect=mysql.dialect())))
            return Mock(first=Mock(return_value=next(rows)))

        def add(row):
            self.events.append((label, "add"))
            row.id = 7

        def flush():
            self.events.append((label, "flush"))
            if flush_error:
                raise flush_error

        def commit():
            self.events.append((label, "commit"))
            if commit_error:
                raise commit_error

        db.scalars.side_effect = scalars
        db.add.side_effect = add
        db.flush.side_effect = flush
        db.commit.side_effect = commit
        db.rollback.side_effect = lambda: self.events.append((label, "rollback"))
        db.close.side_effect = lambda: self.events.append((label, "close"))
        return db

    def winner(self, content_hash=None):
        return SimpleNamespace(sku_code="RETRY-SKU", sku_revision=1,
                               content_hash=content_hash or self.snapshot.content_hash,
                               publish_status="PUBLISHED", version=0)

    def publish(self):
        return self.service.publish_sku(self.payload, reason="deterministic publication test", actor_id=9)

    def test_success_uses_unique_key_not_missing_row_lock(self):
        db = self.session("first"); self.maker.return_value = db
        result = self.publish()
        self.assertFalse(result["replayed"])
        self.assertEqual(result["contentHash"], self.snapshot.content_hash)
        self.assertNotIn("FOR UPDATE", db.queries[0])
        self.assertEqual(self.events, [("first", "add"), ("first", "flush"),
                                      ("first", "audit"), ("first", "commit"), ("first", "close")])
        self.service.sleep.assert_not_called()

    def test_flush_deadlock_closes_and_rolls_back_before_fresh_attempt(self):
        first = self.session("first", flush_error=deadlock()); second = self.session("second")
        self.maker.side_effect = [first, second]
        self.assertFalse(self.publish()["replayed"])
        self.assertEqual(self.events[:5], [("first", "add"), ("first", "flush"),
                                         ("first", "rollback"), ("first", "close"), ("sleep", 0.01)])
        first.commit.assert_not_called()
        self.assertEqual(self.maker.call_count, 2)
        self.audit.assert_called_once()
        self.assertIs(self.audit.call_args.args[0], second)

    def test_commit_deadlock_replays_whole_transaction_not_commit_only(self):
        first = self.session("first", commit_error=deadlock()); second = self.session("second")
        self.maker.side_effect = [first, second]
        self.assertFalse(self.publish()["replayed"])
        self.assertLess(self.events.index(("first", "rollback")), self.events.index(("second", "add")))
        self.assertLess(self.events.index(("first", "close")), self.events.index(("sleep", 0.01)))
        self.assertEqual(self.audit.call_count, 2)  # first audit belongs to rolled-back transaction
        first.commit.assert_called_once(); second.commit.assert_called_once()

    def test_deadlock_then_competitor_win_returns_replay_without_second_write(self):
        first = self.session("first", flush_error=deadlock())
        second = self.session("second", existing=self.winner())
        self.maker.side_effect = [first, second]
        self.assertTrue(self.publish()["replayed"])
        second.add.assert_not_called(); second.commit.assert_not_called(); self.audit.assert_not_called()

    def test_retry_budget_exhaustion_is_bounded_and_sanitized_503(self):
        sessions = [self.session(str(i), flush_error=deadlock()) for i in range(4)]
        self.maker.side_effect = sessions
        with self.assertRaises(self.service.AppException) as caught:
            self.publish()
        self.assertEqual(caught.exception.http_status, 503)
        self.assertEqual(caught.exception.code, "COMMERCIAL_PUBLISH_BUSY")
        self.assertNotIn("private", str(caught.exception))
        self.assertEqual(self.maker.call_count, 4)
        self.assertEqual([c.args[0] for c in self.service.sleep.call_args_list], [0.01, 0.02, 0.04])
        for db in sessions:
            db.rollback.assert_called_once(); db.close.assert_called_once(); db.commit.assert_not_called()

    def test_other_database_errors_and_ambiguous_commit_are_not_retried(self):
        errors = [OperationalError("SQL", {}, Exception(code, "fault")) for code in (1205, 2006, 1045)]
        errors += [deadlock(invalidated=True), OperationalError("SQL", {}, Exception())]
        for index, error in enumerate(errors):
            with self.subTest(error=index):
                self.maker.reset_mock(); self.service.sleep.reset_mock()
                db = self.session(str(index), commit_error=error); self.maker.return_value = db
                with self.assertRaises(OperationalError) as caught:
                    self.publish()
                self.assertIs(caught.exception, error)
                self.assertEqual(self.maker.call_count, 1)
                self.service.sleep.assert_not_called(); db.rollback.assert_called_once(); db.close.assert_called_once()

    def test_duplicate_key_same_content_is_replayed_after_rollback(self):
        db = self.session("first", flush_error=IntegrityError("INSERT", {}, Exception(1062, "duplicate")),
                          winner=self.winner())
        self.maker.return_value = db
        self.assertTrue(self.publish()["replayed"])
        db.rollback.assert_called_once(); db.commit.assert_not_called()
        self.assertEqual(self.maker.call_count, 1); self.audit.assert_not_called()

    def test_duplicate_key_different_content_is_still_409(self):
        db = self.session("first", flush_error=IntegrityError("INSERT", {}, Exception(1062, "duplicate")),
                          winner=self.winner("other-content"))
        self.maker.return_value = db
        with self.assertRaises(self.service.AppException) as caught:
            self.publish()
        self.assertEqual(caught.exception.http_status, 409)
        self.assertEqual(self.maker.call_count, 1); self.service.sleep.assert_not_called()

    def test_existing_immutable_different_content_is_409(self):
        db = self.session("first", existing=self.winner("other-content")); self.maker.return_value = db
        with self.assertRaises(self.service.AppException) as caught:
            self.publish()
        self.assertEqual(caught.exception.http_status, 409)
        db.add.assert_not_called(); self.audit.assert_not_called(); self.service.sleep.assert_not_called()

    def test_audit_outage_rolls_back_and_is_never_ignored_or_retried(self):
        db = self.session("first"); self.maker.return_value = db
        self.audit.side_effect = RuntimeError("audit unavailable")
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            self.publish()
        self.assertEqual(self.maker.call_count, 1)
        db.rollback.assert_called_once(); db.commit.assert_not_called(); db.close.assert_called_once()
        self.service.sleep.assert_not_called()

    def test_invalid_contract_never_writes_or_retries(self):
        db = self.session("first"); self.maker.return_value = db
        self.payload["revision"] = 0
        with self.assertRaises(self.service.AppException) as caught:
            self.publish()
        self.assertEqual(caught.exception.http_status, 422)
        db.add.assert_not_called(); db.commit.assert_not_called(); self.service.sleep.assert_not_called()

    def test_db_disabled_rejects_before_opening_session(self):
        self.enabled.return_value = False
        with self.assertRaises(self.service.AppException):
            self.publish()
        self.maker.assert_not_called(); self.service.sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()

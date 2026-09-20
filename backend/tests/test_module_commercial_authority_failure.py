"""Behavioral fault injection at real access/upload/import entrypoints.

Only IO dependencies are replaced. Actual gate modules, exception envelope,
module-key resolution and feature allowlist execute unchanged. No MySQL, customer
rows or storage writes are performed; these tests are not M0/M1 stage approval.
Run directly (the schema-evidence job has the committed application dependencies).
"""
from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend/app"


def verified(features):
    return {"verified": True, "authoritySource": "MODULE_V2", "features": features}


def module(name, **attributes):
    result = ModuleType(name)
    for key, value in attributes.items():
        setattr(result, key, value)
    return result


class AuthorityFailureTests(unittest.TestCase):
    def setUp(self):
        self.authority = Mock(return_value=verified({"internship": True, "graduation": True,
                                                    "fileUpload": True, "studentImport": True}))
        self.trace = Mock(return_value="request-one")
        self.tenant = Mock(return_value=42)
        self.permission = Mock(return_value=True)
        self.storage = Mock(side_effect=AssertionError("storage must not be reached"))
        self.school = Mock(return_value={})
        self.tenant_state = Mock(return_value={"effectiveStatus": "ACTIVE", "errors": []})
        replacements = {
            "app": module("app", __path__=[str(APP)]),
            "app.core": module("app.core", __path__=[str(APP / "core")]),
            "app.services": module("app.services", __path__=[str(APP / "services")]),
            "app.db": module("app.db", __path__=[str(APP / "db")]),
            "app.core.config": module("app.core.config", settings=SimpleNamespace(
                TIMEZONE_OFFSET_HOURS=8, support_contact_display="平台支持")),
            "app.core.context": module("app.core.context", get_trace_id=self.trace,
                current_tenant_id=self.tenant, get_current_user_ctx=Mock(return_value={})),
            "app.core.permissions": module("app.core.permissions", has_permission=self.permission,
                is_super_admin=Mock(return_value=False)),
            "app.db.session": module("app.db.session", db_enabled=Mock(return_value=True),
                get_sessionmaker=Mock(side_effect=AssertionError("DB must not be reached"))),
            "app.services.storage": module("app.services.storage", get_backend=self.storage),
            "app.services.commercial_entitlement_authority_service": module(
                "app.services.commercial_entitlement_authority_service", commercial_state=self.authority),
            "app.services.platform_service": module("app.services.platform_service",
                effective_features=Mock(side_effect=AssertionError("lossy feature-only projection used")),
                feature_enabled=Mock(side_effect=AssertionError("lossy compatibility check used"))),
            "app.services.system_governance_service": module("app.services.system_governance_service",
                get_module_features=self.school),
            "app.services.tenant_effective_state_service": module("app.services.tenant_effective_state_service",
                get_effective_state=self.tenant_state),
            "app.services.audit_log": module("app.services.audit_log", record=Mock()),
        }
        # Clear only this sandbox's app namespace, and restore all prior modules
        # afterwards so pytest collection in the full repository stays isolated.
        saved = {name: value for name, value in sys.modules.items()
                 if name == "app" or name.startswith("app.")}

        def restore_app_modules():
            for name in list(sys.modules):
                if name == "app" or name.startswith("app."):
                    del sys.modules[name]
            sys.modules.update(saved)

        self.addCleanup(restore_app_modules)
        for name in saved:
            del sys.modules[name]
        sys.modules.update(replacements)
        self.errors = importlib.import_module("app.core.exceptions")
        self.reader = importlib.import_module("app.services.commercial_authority_read")
        self.access = importlib.import_module("app.services.module_access_service")
        self.files = importlib.import_module("app.services.file_service_legacy")
        self.imports = importlib.import_module("app.core.import_export_auth")
        self.addCleanup(self.access._request_snapshot.set, None)

    def assert_outage(self, callback):
        with self.assertRaises(self.errors.AppException) as caught:
            callback()
        self.assertEqual(caught.exception.code, "AUTHORITY_UNAVAILABLE")
        self.assertEqual(caught.exception.http_status, 503)
        self.assertTrue(caught.exception.details["retryable"])
        return caught.exception

    def test_purchase_true_is_preserved(self):
        self.assertTrue(self.reader.feature_enabled(42, "internship"))
        self.authority.assert_called_once_with(42)

    def test_not_purchased_and_absent_key_stay_false(self):
        self.authority.return_value = verified({"internship": False})
        self.assertFalse(self.reader.feature_enabled(42, "internship"))
        self.assertFalse(self.reader.feature_enabled(42, "graduation"))

    def test_unknown_key_cannot_grant_or_query_authority(self):
        self.assertFalse(self.reader.feature_enabled(42, "not-a-commercial-feature"))
        self.authority.assert_not_called()

    def test_graduation_alias_uses_existing_canonical_key(self):
        self.assertTrue(self.reader.feature_enabled(42, "graduationDesign"))
        self.authority.assert_called_once_with(42)

    def test_no_implicit_employment_or_api_entitlement(self):
        self.assertFalse(self.reader.feature_enabled(42, "employment"))
        self.assertFalse(self.reader.feature_enabled(42, "apiAccess"))

    def test_read_exception_becomes_503_not_false(self):
        self.authority.side_effect = RuntimeError("mysql://private-credentials")
        error = self.assert_outage(lambda: self.reader.feature_enabled(42, "internship"))
        self.assertNotIn("private-credentials", str(error))
        self.assertNotIn("mysql", str(error.details))

    def test_existing_5xx_becomes_authority_unavailable(self):
        self.authority.side_effect = self.errors.AppException("SERVER_ERROR", "private", http_status=500)
        self.assert_outage(lambda: self.reader.effective_features(42))

    def test_explicit_business_denial_is_not_relabelled_outage(self):
        for code, status in [("NO_PERMISSION", 403), ("DATA_NOT_FOUND", 404)]:
            error = self.errors.AppException(code, "explicit denial", http_status=status)
            self.authority.side_effect = error
            with self.subTest(status=status), self.assertRaises(self.errors.AppException) as caught:
                self.reader.effective_features(42)
            self.assertIs(caught.exception, error)

    def test_non_boolean_or_malformed_snapshots_cannot_grant(self):
        for value in [None, [], True, {"internship": "false"}, {"internship": 1},
                      {"internship": None}, {7: True}]:
            self.authority.return_value = verified(value)
            with self.subTest(value=value):
                self.assert_outage(lambda: self.reader.effective_features(42))

    def test_snapshot_is_detached_from_authority_dict(self):
        snapshot = self.reader.effective_features(42)
        snapshot["internship"] = False
        self.assertTrue(self.authority.return_value["features"]["internship"])

    def test_successful_request_reads_authority_school_and_state_once(self):
        self.assertTrue(self.access.module_access_state(42, "internship")["allowed"])
        self.assertTrue(self.access.module_access_state(42, "graduationDesign")["allowed"])
        self.authority.assert_called_once_with(42)
        self.school.assert_called_once_with(42)
        self.tenant_state.assert_called_once_with(42, strict=False)

    def test_request_snapshot_is_isolated_by_tenant(self):
        self.access.module_access_state(42, "internship")
        self.access.module_access_state(43, "internship")
        self.assertEqual(self.authority.call_count, 2)

    def test_request_snapshot_is_isolated_by_trace(self):
        self.access.module_access_state(42, "internship")
        self.trace.return_value = "request-two"
        self.access.module_access_state(42, "internship")
        self.assertEqual(self.authority.call_count, 2)

    def test_non_http_calls_never_reuse_snapshot(self):
        self.trace.return_value = "-"
        self.access.module_access_state(42, "internship")
        self.access.module_access_state(42, "internship")
        self.assertEqual(self.authority.call_count, 2)

    def test_failure_is_not_cached_and_same_request_can_recover(self):
        self.authority.side_effect = [RuntimeError("offline"), verified({"internship": True})]
        self.assert_outage(lambda: self.access.assert_module_access(42, "internship", write=True))
        self.assertIsNone(self.access._request_snapshot.get())
        self.school.assert_not_called()
        self.assertTrue(self.access.assert_module_access(42, "internship", write=True)["writable"])
        self.assertEqual(self.authority.call_count, 2)

    def test_module_not_purchased_remains_403(self):
        self.authority.return_value = verified({"internship": False})
        with self.assertRaises(self.errors.AppException) as caught:
            self.access.assert_module_access(42, "internship", write=True)
        self.assertEqual(caught.exception.http_status, 403)

    def test_school_disabled_cannot_be_bypassed(self):
        self.school.return_value = {"internship": {"enabled": False}}
        with self.assertRaises(self.errors.AppException) as caught:
            self.access.assert_module_access(42, "internship", write=True)
        self.assertEqual(caught.exception.http_status, 403)

    def test_school_outage_is_not_cached(self):
        self.school.side_effect = self.errors.AppException("TENANT_GUARD_UNAVAILABLE", "offline", http_status=503)
        with self.assertRaises(self.errors.AppException) as caught:
            self.access.module_access_state(42, "internship")
        self.assertEqual(caught.exception.http_status, 503)
        self.assertIsNone(self.access._request_snapshot.get())

    def test_readonly_tenant_still_blocks_write(self):
        self.tenant_state.return_value = {"effectiveStatus": "READONLY", "errors": []}
        with self.assertRaises(self.errors.AppException) as caught:
            self.access.assert_module_access(42, "internship", write=True)
        self.assertEqual(caught.exception.http_status, 403)

    def test_upload_purchased_is_allowed(self):
        self.assertIsNone(self.files._ensure_upload_allowed())
        self.authority.assert_called_once_with(42)

    def test_upload_not_purchased_is_403(self):
        self.authority.return_value = verified({"fileUpload": False})
        with self.assertRaises(self.errors.AppException) as caught:
            self.files._ensure_upload_allowed()
        self.assertEqual(caught.exception.code, "MODULE_NOT_AUTHORIZED")
        self.assertEqual(caught.exception.http_status, 403)

    def test_upload_outage_never_reads_body_or_opens_storage(self):
        self.authority.side_effect = RuntimeError("offline")
        upload = SimpleNamespace(filename="report.pdf", read=AsyncMock())
        self.assert_outage(lambda: asyncio.run(self.files.store_upload(upload)))
        upload.read.assert_not_awaited()
        self.storage.assert_not_called()

    def test_upload_missing_tenant_is_denied_before_authority(self):
        self.tenant.return_value = None
        with self.assertRaises(self.errors.AppException) as caught:
            self.files._ensure_upload_allowed()
        self.assertEqual(caught.exception.code, "TENANT_CONTEXT_REQUIRED")
        self.authority.assert_not_called()

    def test_student_import_requires_exact_permission_first(self):
        self.permission.return_value = False
        self.authority.side_effect = RuntimeError("offline")
        with self.assertRaises(self.errors.AppException) as caught:
            self.imports.enforce_student_import({"userId": "1"})
        self.assertEqual(caught.exception.http_status, 403)
        self.permission.assert_called_once_with({"userId": "1"}, "student.import")
        self.authority.assert_not_called()

    def test_student_import_authority_failure_is_503(self):
        self.authority.side_effect = RuntimeError("offline")
        self.assert_outage(lambda: self.imports.enforce_student_import({"userId": "1"}))

    def test_student_import_not_purchased_is_403(self):
        self.authority.return_value = verified({"studentImport": False})
        with self.assertRaises(self.errors.AppException) as caught:
            self.imports.enforce_student_import({"userId": "1"})
        self.assertEqual(caught.exception.code, "MODULE_NOT_AUTHORIZED")
        self.assertEqual(caught.exception.http_status, 403)

    def test_student_import_permission_and_purchase_pass(self):
        self.assertIsNone(self.imports.enforce_student_import({"userId": "1"}))
        self.authority.assert_called_once_with(42)

    def test_student_import_missing_tenant_does_not_read_authority(self):
        self.tenant.return_value = None
        with self.assertRaises(self.errors.AppException):
            self.imports.enforce_student_import({"userId": "1"})
        self.authority.assert_not_called()

    def test_student_export_permission_is_not_upgraded(self):
        self.permission.return_value = False
        with self.assertRaises(self.errors.AppException) as caught:
            self.imports.enforce_student_export({"userId": "1"})
        self.assertEqual(caught.exception.http_status, 403)
        self.authority.assert_not_called()


    def test_m2_swallowed_outage_is_503_even_with_all_false_features(self):
        for source in ("COMMERCIAL_READER_UNAVAILABLE", "MODULE_V2_UNAVAILABLE"):
            with self.subTest(source=source):
                self.authority.return_value = {"verified": False, "authoritySource": source,
                    "features": {"internship": False, "fileUpload": False, "studentImport": False}}
                self.assert_outage(lambda: self.access.module_access_state(42, "internship"))
                self.assertIsNone(self.access._request_snapshot.get())
                self.assert_outage(self.files._ensure_upload_allowed)
                self.assert_outage(lambda: self.imports.enforce_student_import({"userId": "1"}))

    def test_explicit_negative_authority_states_remain_denied(self):
        for source in self.reader._DENIED_SOURCES:
            with self.subTest(source=source):
                self.authority.return_value = {"verified": False, "authoritySource": source,
                                               "features": {"internship": False}}
                self.assertFalse(self.reader.feature_enabled(42, "internship"))

    def test_all_existing_verified_sources_are_supported(self):
        for source in self.reader._VERIFIED_SOURCES:
            with self.subTest(source=source):
                self.authority.return_value = {"verified": True, "authoritySource": source,
                                               "features": {"internship": True}}
                self.assertTrue(self.reader.feature_enabled(42, "internship"))

    def test_unverified_positive_and_unknown_authority_are_rejected(self):
        for state in ({"verified": False, "authoritySource": "COMMERCIAL_ORDER_REQUIRED", "features": {"internship": True}},
                      {"verified": True, "authoritySource": "UNKNOWN_VERSION", "features": {"internship": True}},
                      {"verified": False, "authoritySource": "UNKNOWN_VERSION", "features": {}},
                      {"verified": "false", "authoritySource": "MODULE_V2", "features": {}},
                      None, {}, {"features": {"internship": True}}):
            with self.subTest(state=state):
                self.authority.return_value = state
                self.assert_outage(lambda: self.reader.effective_features(42))

    def test_invalid_tenant_never_queries_authority(self):
        for tenant in (None, 0, -1, True, "not-a-tenant", 1.5):
            with self.subTest(tenant=tenant), self.assertRaises(self.errors.AppException) as caught:
                self.reader.effective_features(tenant)
            self.assertEqual(caught.exception.http_status, 400)
        self.authority.assert_not_called()

    def test_actual_m2_adapter_fault_envelopes_reach_strict_gate(self):
        # Execute the real M2 wrapper; substitute only storage/lifecycle inputs.
        authority = sys.modules["app.services.commercial_entitlement_authority_service"]
        authority._LOG = Mock()
        authority._zero_features = lambda: {"internship": False}
        authority._tenant_snapshot = Mock(return_value={"tenantStatus": "ACTIVE"})
        platform = sys.modules["app.services.platform_service"]
        original_writer = Mock(side_effect=AssertionError("writer must not run"))
        platform.order_action = original_writer
        platform.paid_order_activation_state = Mock()
        platform.tenant_meta = Mock(return_value={"status": "active"})
        subscriptions = module("app.services.module_subscription_service",
            reader_version=Mock(side_effect=RuntimeError("profile unavailable")),
            module_projection=Mock(side_effect=RuntimeError("ledger unavailable")))
        sys.modules[subscriptions.__name__] = subscriptions
        sys.modules["app.services.commercial_order_item_service"] = module("app.services.commercial_order_item_service")
        sys.modules["app.services.tenant_effective_state_service"].effective_state_from_records = Mock(return_value={"writable": True})
        importlib.import_module("app.services.module_commerce_runtime_guard").install(platform)
        self.assert_outage(lambda: self.access.module_access_state(42, "internship"))
        self.assertIsNone(self.access._request_snapshot.get())
        subscriptions.reader_version.side_effect = None
        subscriptions.reader_version.return_value = "MODULE_V2"
        self.assert_outage(lambda: self.access.module_access_state(42, "internship"))
        self.assertIsNone(self.access._request_snapshot.get())
        subscriptions.module_projection.side_effect = None
        subscriptions.module_projection.return_value = {**verified({"internship": True}), "readerVersion": "MODULE_V2"}
        self.assertTrue(self.access.module_access_state(42, "internship")["allowed"])
        original_writer.assert_not_called()

    def test_http_outage_envelope_is_503_and_contains_no_secret(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        self.errors.register_exception_handlers(app)
        self.authority.side_effect = RuntimeError("mysql://private-credentials")

        @app.get("/gate")
        def gate():
            self.access.assert_module_access(42, "internship", write=True)
            return {"unexpected": "allowed"}

        with TestClient(app) as client:
            response = client.get("/gate")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["bizCode"], "AUTHORITY_UNAVAILABLE")
        self.assertEqual(body["code"], 500001)
        self.assertEqual(body["traceId"], "request-one")
        self.assertNotIn("private-credentials", response.text)
        self.assertIsNone(body["data"])

class FinalCommitFenceFaultTests(unittest.TestCase):
    """Real guard/SQL expressions with deterministic IO faults, not a MySQL proof.

    The disposable-MySQL write-fence suite separately covers real ORM identity
    maps. This sandbox does not open a database or install global ORM listeners.
    """
    def setUp(self):
        from datetime import datetime, timedelta
        self.time = datetime(2030, 1, 1, 12)
        self.delta = timedelta
        saved = {n: v for n, v in sys.modules.items() if n == 'app' or n.startswith('app.')}
        def restore():
            for name in list(sys.modules):
                if name == 'app' or name.startswith('app.'):
                    del sys.modules[name]
            sys.modules.update(saved)
        self.addCleanup(restore)
        for name in saved:
            del sys.modules[name]
        sys.modules.update({
            'app': module('app', __path__=[str(APP)]),
            'app.core': module('app.core', __path__=[str(APP / 'core')]),
            'app.models': module('app.models', __path__=[str(APP / 'models')]),
            'app.services': module('app.services', __path__=[str(APP / 'services')]),
            'app.core.context': module('app.core.context', get_trace_id=lambda: '-'),
        })
        self.models = importlib.import_module('app.models.commercial')
        for name in ('TenantModuleState', 'TenantModuleSubscriptionSource', 'TenantCommercialProfile'):
            setattr(sys.modules['app.models'], name, getattr(self.models, name))
        self.guard = importlib.import_module('app.services.module_commerce_access_guard')
        self.guard.datetime = SimpleNamespace(utcnow=lambda: self.time)
        self.errors = importlib.import_module('app.core.exceptions')
        self.guard._write_fence_ctx.set({'kind': 'WORKER', 'modules': {
            '42:internship': {'tenantId': 42, 'moduleKey': 'internship', 'generation': 1},
        }})
        self.states = {'internship': SimpleNamespace(generation=1, data_state='AVAILABLE')}
        self.profile = SimpleNamespace(reader_version='MODULE_V2')
        self.sources = [SimpleNamespace(tenant_id=42, module_key='internship', module_generation=1,
            status='ACTIVE', is_deleted=False, starts_at=self.time - self.delta(days=1),
            ends_at=self.time + self.delta(seconds=2))]
        self.cached = {}
        self.after_read = lambda _model: None
        self.queries = []
        self.db = SimpleNamespace(scalars=self.scalars)

    def scalars(self, statement):
        entity = statement.column_descriptions[0]['entity']
        params = statement.compile().params
        self.queries.append(statement)
        self.assertEqual(params['tenant_id_1'], 42)
        if entity is self.models.TenantModuleState:
            row = self.states.get(params['module_key_1'])
            values = [] if row is None else [row]
        elif entity is self.models.TenantCommercialProfile:
            values = [] if self.profile is None else [self.profile]
        else:
            self.assertIs(entity, self.models.TenantModuleSubscriptionSource)
            values = [r for r in self.sources if r.tenant_id == params['tenant_id_1']
                and r.module_key == params['module_key_1']
                and r.module_generation == params['module_generation_1']
                and r.status in params['status_1'] and not r.is_deleted
                and r.ends_at > params['ends_at_1']
                and ('starts_at_1' not in params or r.starts_at <= params['starts_at_1'])]
        self.after_read(entity)
        # Simulate a resident ORM value: a new SQL result alone does not replace
        # it unless the real query explicitly requests populate_existing.
        if values and not statement.get_execution_options().get('populate_existing'):
            values = self.cached.get(entity, values)
        return SimpleNamespace(first=lambda: values[0] if values else None, all=lambda: values)

    def deny(self, status=403):
        with self.assertRaises(self.errors.AppException) as caught:
            self.guard._assert_final_fences(self.db)
        self.assertEqual(caught.exception.http_status, status)

    def test_live_contract_passes_with_refresh_and_current_profile_lock(self):
        from sqlalchemy.dialects import mysql
        self.guard._assert_final_fences(self.db)
        for query in self.queries:
            self.assertTrue(query.get_execution_options().get('populate_existing'))
            self.assertIsNotNone(query._for_update_arg)
        self.assertEqual([q.column_descriptions[0]['entity'] for q in self.queries], [
            self.models.TenantModuleState, self.models.TenantModuleSubscriptionSource,
            self.models.TenantCommercialProfile])
        self.assertIn('LOCK IN SHARE MODE', str(self.queries[-1].compile(dialect=mysql.dialect())))

    def test_cached_available_state_cannot_hide_frozen_locked_row(self):
        self.cached[self.models.TenantModuleState] = [SimpleNamespace(generation=1, data_state='AVAILABLE')]
        self.states['internship'].data_state = 'FROZEN'
        self.deny()

    def test_cached_generation_cannot_hide_recreated_module(self):
        self.cached[self.models.TenantModuleState] = [SimpleNamespace(generation=1, data_state='AVAILABLE')]
        self.states['internship'].generation = 2
        self.deny(409)

    def test_cached_legacy_profile_cannot_skip_v2_source_check(self):
        self.cached[self.models.TenantCommercialProfile] = [SimpleNamespace(reader_version='LEGACY')]
        self.sources = []
        self.deny()

    def test_expiry_while_waiting_on_source_lock_is_denied(self):
        def wait(entity):
            if entity is self.models.TenantModuleSubscriptionSource:
                self.time += self.delta(seconds=3)
        self.after_read = wait
        self.deny()

    def test_expiry_while_waiting_on_profile_lock_is_denied(self):
        self.after_read = lambda entity: setattr(self, 'time', self.time + self.delta(seconds=3)) \
            if entity is self.models.TenantCommercialProfile else None
        self.deny()

    def test_old_cached_source_end_cannot_extend_locked_contract(self):
        self.cached[self.models.TenantModuleSubscriptionSource] = [SimpleNamespace(
            starts_at=self.time - self.delta(days=1), ends_at=self.time + self.delta(days=30))]
        self.test_expiry_while_waiting_on_source_lock_is_denied()

    def test_future_source_is_not_authorized_before_start(self):
        self.sources[0].starts_at = self.time + self.delta(seconds=1)
        self.deny()

    def test_scheduled_source_starting_during_wait_is_usable(self):
        self.sources[0].starts_at = self.time + self.delta(seconds=1)
        self.sources[0].status = 'SCHEDULED'
        self.after_read = lambda entity: setattr(self, 'time', self.time + self.delta(seconds=1)) \
            if entity is self.models.TenantCommercialProfile else None
        self.guard._assert_final_fences(self.db)

    def test_foreign_tenant_module_generation_and_cancelled_sources_do_not_grant(self):
        for key, value in [('tenant_id', 43), ('module_key', 'graduationDesign'),
                           ('module_generation', 2), ('status', 'CANCELLED'), ('is_deleted', True)]:
            original = getattr(self.sources[0], key)
            with self.subTest(field=key):
                setattr(self.sources[0], key, value)
                self.deny()
                setattr(self.sources[0], key, original)

    def test_legacy_compatibility_and_missing_module_are_not_reinterpreted(self):
        self.profile.reader_version = 'LEGACY'
        self.sources = []
        self.guard._assert_final_fences(self.db)
        self.states = {}
        self.deny(409)

    def test_no_active_fence_performs_no_queries(self):
        self.guard._write_fence_ctx.set(None)
        self.guard._assert_final_fences(self.db)
        self.assertEqual(self.queries, [])

    def test_all_modules_are_rechecked_after_last_contended_lock(self):
        self.guard._write_fence_ctx.get()['modules']['42:studentAffairs'] = {
            'tenantId': 42, 'moduleKey': 'studentAffairs', 'generation': 1}
        self.states['studentAffairs'] = SimpleNamespace(generation=1, data_state='AVAILABLE')
        self.sources.append(SimpleNamespace(**{**vars(self.sources[0]), 'module_key': 'studentAffairs',
            'ends_at': self.time + self.delta(days=1)}))
        def wait(entity):
            if entity is self.models.TenantModuleSubscriptionSource and len(self.queries) >= 4:
                self.time += self.delta(seconds=3)
        self.after_read = wait
        self.deny()


if __name__ == "__main__":
    unittest.main()

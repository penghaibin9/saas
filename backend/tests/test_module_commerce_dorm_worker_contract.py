"""Isolated production-function tests; no application bootstrap or database replacement.

Run directly with Python. MySQL transaction/rollback evidence is kept separately in
``test_module_commerce_dorm_worker_runtime.py``.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "app/services/dorm_allocation_publish_job.py"


class BusinessError(Exception):
    def __init__(self, code, message, *, http_status=400):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status


class Query:
    def __getattr__(self, _):
        return self

    def __call__(self, *_, **__):
        return self

    def __eq__(self, _):
        return self


class DormWorkerContract(unittest.TestCase):
    def setUp(self):
        self.state = {"generation": 4}
        self.mode = "MODULE_V2"
        self.access_error = None
        self.events, self.active = [], []
        access = ModuleType("app.services.module_access_service")
        subscriptions = ModuleType("app.services.module_subscription_service")
        guard = ModuleType("app.services.module_commerce_access_guard")

        def assert_access(tid, module, *, write):
            self.events.append(("authority", tid, module, write))
            if self.access_error:
                raise self.access_error
            return dict(self.state)

        @contextmanager
        def fence(tid, module, generation):
            self.active.append((tid, module, generation))
            self.events.append(("fence-enter", generation))
            try:
                yield
            finally:
                self.events.append(("fence-exit", generation))
                self.active.pop()

        access.assert_module_access = assert_access
        subscriptions.reader_version = lambda _: self.mode
        guard.module_write_fence = fence
        modules = {m.__name__: m for m in (access, subscriptions, guard)}
        for name in ("app", "app.services"):
            if name not in sys.modules:
                parent = ModuleType(name)
                parent.__path__ = []
                modules[name] = parent
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        names = {"_module_generation", "_publication_fence", "_row", "run_one"}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in functions}, names)
        self.code = {
            "AppException": BusinessError, "_tid": lambda: 91,
            "nullcontext": nullcontext, "ExitStack": ExitStack,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), self.code)

    def test_capture_uses_canonical_write_authority(self):
        self.assertEqual(self.code["_module_generation"](), 4)
        self.assertIn(("authority", 91, "studentAffairs", True), self.events)

    def test_only_verified_legacy_reader_has_generation_zero(self):
        self.mode, self.state = "LEGACY", {}
        self.assertEqual(self.code["_module_generation"](), 0)
        self.state = {"generation": 0}
        self.assertEqual(self.code["_module_generation"](), 0)

    def test_v2_or_unknown_reader_cannot_fall_back_to_legacy(self):
        for mode in ("MODULE_V2", "UNKNOWN", ""):
            for generation in (None, 0):
                with self.subTest(mode=mode, generation=generation):
                    self.mode, self.state = mode, {"generation": generation}
                    with self.assertRaises(BusinessError) as caught:
                        self.code["_module_generation"]()
                    self.assertEqual(caught.exception.http_status, 503)

    def test_malformed_live_generation_is_never_coerced(self):
        self.mode = "LEGACY"
        for value in (True, False, 0.0, 1.5, "4", -1):
            with self.subTest(value=value):
                self.state = {"generation": value}
                with self.assertRaises(BusinessError) as caught:
                    self.code["_module_generation"]()
                self.assertEqual(caught.exception.http_status, 503)

    def test_exact_saved_generation_stays_active_until_scope_exit(self):
        payload = {"moduleGeneration": 4, "batchId": "9007199254740993"}
        before = deepcopy(payload)
        with self.code["_publication_fence"](payload):
            self.assertEqual(self.active, [(91, "studentAffairs", 4)])
        self.assertEqual(self.active, [])
        self.assertEqual(payload, before)

    def test_stale_task_is_not_retargeted_to_new_generation(self):
        with self.assertRaises(BusinessError) as caught:
            self.code["_publication_fence"]({"moduleGeneration": 3})
        self.assertEqual(caught.exception.http_status, 409)
        self.assertFalse(any(e[0] == "fence-enter" for e in self.events))

    def test_missing_or_zero_legacy_task_cannot_cross_cutover(self):
        for payload in ({}, {"moduleGeneration": 0}):
            with self.subTest(payload=payload):
                with self.assertRaises(BusinessError):
                    self.code["_publication_fence"](payload)

    def test_historical_legacy_job_can_finish_before_cutover(self):
        self.mode, self.state = "LEGACY", {}
        with self.code["_publication_fence"]({}):
            self.assertEqual(self.active, [])
        with self.code["_publication_fence"]({"moduleGeneration": 0}):
            self.assertEqual(self.active, [])

    def test_explicit_invalid_task_generation_cannot_use_legacy_exception(self):
        self.mode, self.state = "LEGACY", {}
        for value in (None, True, False, "0", 0.0, -1, {}, []):
            with self.subTest(value=value):
                with self.assertRaises(BusinessError):
                    self.code["_publication_fence"]({"moduleGeneration": value})

    def test_permission_denial_and_authority_outage_propagate(self):
        for code, status in (("NO_PERMISSION", 403), ("MODULE_STATE_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.access_error = BusinessError(code, "authority denied", http_status=status)
                with self.assertRaises(BusinessError) as caught:
                    self.code["_publication_fence"]({"moduleGeneration": 4})
                self.assertIs(caught.exception, self.access_error)
                self.assertEqual(self.active, [])

    def _run_worker(self, *, domain_error=None, savepoint_error=False, outer_error=False):
        harness = self
        job = SimpleNamespace(id=5, tenant_id=91, status="PENDING", started_at=None,
                              total_count=3, success_count=0, last_error=None,
                              request_json={"actor": {}, "batchId": "7", "version": 2,
                                            "moduleGeneration": 4})
        item = SimpleNamespace(attempt_count=0, biz_id=7, expected_version=2)
        previous_user, previous_tenant = {"name": "old"}, {"tenantId": "8"}
        current = {"user": previous_user, "tenant": previous_tenant}

        class DB:
            def __init__(self, claim):
                self.claim = claim
                self.rows = iter([job] if claim else [job, item])

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def scalar(self, _):
                return next(self.rows)

            def flush(self):
                harness.events.append(("flush", bool(harness.active)))

            @contextmanager
            def begin_nested(self):
                try:
                    yield
                    harness.events.append(("savepoint-release", bool(harness.active)))
                    if savepoint_error:
                        raise BusinessError("NO_PERMISSION", "frozen at savepoint", http_status=403)
                except BaseException:
                    harness.events.append(("savepoint-rollback", bool(harness.active)))
                    raise

            def commit(self):
                harness.events.append(("claim-commit" if self.claim else "outer-commit", bool(harness.active)))
                if not self.claim and outer_error:
                    raise BusinessError("NO_PERMISSION", "frozen at final commit", http_status=403)

        def publish(*_, **__):
            self.assertEqual(self.active, [(91, "studentAffairs", 4)])
            if domain_error:
                raise domain_error
            return {"status": "PUBLISHED"}

        self.code.update({
            "get_sessionmaker": lambda: lambda: DB(True), "session": lambda: DB(False),
            "select": lambda *_: Query(), "AffairsBatchJob": Query(),
            "AffairsBatchJobItem": Query(), "JOB_TYPE": "DORM_ALLOCATION_PUBLISH",
            "utc_now_naive": lambda: "test-time", "_live_actor": lambda *_: {"userId": "new"},
            "get_tenant": lambda: current["tenant"],
            "get_current_user_ctx": lambda: current["user"],
            "set_tenant": lambda value: current.update(tenant=value),
            "set_current_user": lambda value: current.update(user=value),
            "allocation": SimpleNamespace(publish_in_transaction=publish),
        })
        try:
            return self.code["run_one"]()
        finally:
            self.assertIs(current["tenant"], previous_tenant)
            self.assertIs(current["user"], previous_user)
            self.assertEqual(self.active, [])

    def test_success_fence_spans_savepoint_and_final_commit_but_not_claim(self):
        self.assertEqual(self._run_worker()["status"], "SUCCESS")
        self.assertIn(("claim-commit", False), self.events)
        self.assertIn(("savepoint-release", True), self.events)
        self.assertIn(("outer-commit", True), self.events)

    def test_business_rejection_releases_fence_only_after_savepoint_rollback(self):
        result = self._run_worker(domain_error=BusinessError("DATA_CONFLICT", "version changed"))
        self.assertEqual(result["status"], "FAILED")
        self.assertLess(self.events.index(("savepoint-rollback", True)), self.events.index(("fence-exit", 4)))
        self.assertIn(("outer-commit", False), self.events)

    def test_savepoint_fence_rejection_can_persist_failure_not_success(self):
        self.assertEqual(self._run_worker(savepoint_error=True)["status"], "FAILED")
        self.assertIn(("savepoint-rollback", True), self.events)
        self.assertIn(("outer-commit", False), self.events)

    def test_final_commit_rejection_never_returns_success(self):
        with self.assertRaises(BusinessError):
            self._run_worker(outer_error=True)
        self.assertIn(("outer-commit", True), self.events)

    def test_infrastructure_failure_propagates_without_false_failed_receipt(self):
        with self.assertRaises(RuntimeError):
            self._run_worker(domain_error=RuntimeError("storage unavailable"))
        self.assertFalse(any(e[0] == "outer-commit" for e in self.events))


if __name__ == "__main__":
    unittest.main()

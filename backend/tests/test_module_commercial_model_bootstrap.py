"""Cold model-registry regressions; no database or customer data is accessed."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]
COMMERCE_DYNAMIC_MODELS = {
    "CommercialInvoiceCase",
    "CommercialOrderItem",
    "CommercialRefundCase",
    "CommercialSkuVersion",
    "TenantCommercialProfile",
    "TenantModuleState",
    "TenantModuleSubscriptionSource",
}
REQUIRED_MODELS = {
    "CommercialInvoiceCase": "t_commercial_invoice_case",
    "CommercialOrderItem": "t_commercial_order_item",
    "CommercialRefundCase": "t_commercial_refund_case",
    "CommercialSkuVersion": "t_commercial_sku_version",
    "TenantCommercialProfile": "t_tenant_commercial_profile",
    "TenantModuleState": "t_tenant_module_state",
    "TenantModuleSubscriptionSource": "t_tenant_module_subscription_source",
    "DisciplineDecisionVersion": "t_affairs_discipline_decision_version",
    "FileStorageQuotaReservation": "t_file_storage_quota_reservation",
    "AaGraduationAuditResult": "t_aa_graduation_audit_result",
    "StudentLifecycleFact": "t_student_lifecycle_fact",
    "PasswordResetSmsJob": "t_password_reset_sms_job",
}


class ModelBootstrapTests(unittest.TestCase):
    def test_all_registered_model_sources_are_utf8_python(self):
        for path in sorted((BACKEND / "app/models").rglob("*.py")):
            with self.subTest(path=path.relative_to(BACKEND).as_posix()):
                # Strict decoding catches corruption, including bytes in comments.
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_critical_registry_imports_are_not_truncated(self):
        tree = ast.parse((BACKEND / "app/models/__init__.py").read_text(encoding="utf-8"))
        names = {
            item.name
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for item in node.names
        }
        # Commerce models are intentionally exposed by app.models.platform while that
        # module is imported by the aggregator; legacy consumers remain explicit imports.
        legacy_names = set(REQUIRED_MODELS) - COMMERCE_DYNAMIC_MODELS
        self.assertTrue(legacy_names.issubset(names), legacy_names - names)

    def test_fresh_process_registers_commerce_and_existing_consumers(self):
        code = """
import json
import app.models as models
from app.db.base import metadata
from sqlalchemy.orm import configure_mappers
configure_mappers()
required = json.loads(__import__('sys').argv[1])
for name, table in required.items():
    assert getattr(models, name).__tablename__ == table, name
    assert table in metadata.tables, table
print(json.dumps({'status': 'MODEL_BOOTSTRAP_OK', 'tableCount': len(metadata.tables)}))
"""
        env = {**os.environ, "APP_ENV": "test", "DB_ENABLED": "false",
               "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, json.dumps(REQUIRED_MODELS)],
            cwd=BACKEND, env=env, capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(report["status"], "MODEL_BOOTSTRAP_OK")
        self.assertGreaterEqual(report["tableCount"], len(REQUIRED_MODELS))


if __name__ == "__main__":
    unittest.main()

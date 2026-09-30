"""Local launcher must not inherit another task's database or reset the persistent sandbox."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "sandbox_runtime_guard", Path(__file__).resolve().parents[2] / "scripts/dev/check-sandbox-runtime.py",
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class SandboxRuntimeProfileTest(unittest.TestCase):
    def profile(self):
        return {
            "DATABASE_URL": "mysql+pymysql://test@127.0.0.1:3307/student_lifecycle_runtime_20260902",
            "DEFAULT_TENANT_CODE": "sandbox-school", "DB_ENABLED": "true",
            "SANDBOX_AUTO_RESET": "false", "APP_ENV": "development", "DEPLOYMENT_MODE": "local",
        }

    def test_other_task_environment_cannot_redirect_daily_database(self):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///other-task"}), patch.object(guard, "dotenv_values", return_value=self.profile()):
            self.assertEqual(guard.load_environment().database, guard.DATABASE)
            self.assertEqual(os.environ["DATABASE_URL"], self.profile()["DATABASE_URL"])

    def test_wrong_database_school_and_reset_modes_fail_before_connecting(self):
        for key, value in [
            ("DATABASE_URL", "mysql+pymysql://test@127.0.0.1:3306/student_lifecycle_dev"),
            ("DEFAULT_TENANT_CODE", "demo"), ("SANDBOX_AUTO_RESET", "true"),
            ("DB_ENABLED", "false"), ("DEPLOYMENT_MODE", "production"),
        ]:
            with self.subTest(key=key), patch.object(guard, "dotenv_values", return_value={**self.profile(), key: value}), self.assertRaises(RuntimeError):
                guard.load_environment()

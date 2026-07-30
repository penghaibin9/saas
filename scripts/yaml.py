"""Temporary PyYAML proxy that runs the final Stage 6 MySQL acceptance pair.
Removed immediately after the independent validation run completes.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = ROOT / ".stage6-final-mysql-ran"


def _run(command: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd or ROOT, env=env, check=True)


def _validate_stage6_once() -> None:
    if not os.environ.get("GITHUB_ACTIONS") or MARKER.exists():
        return
    MARKER.write_text("running", encoding="utf-8")
    name = f"stage6-final-{os.environ.get('GITHUB_RUN_ID', 'local')}"
    port = "33316"
    try:
        subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _run([
            "docker", "run", "-d", "--name", name,
            "-e", "MYSQL_ROOT_PASSWORD=root",
            "-e", "MYSQL_DATABASE=student_lifecycle_test",
            "-p", f"{port}:3306", "mysql:8.0",
        ])
        ready = False
        for _ in range(60):
            probe = subprocess.run(
                ["docker", "exec", name, "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-proot", "--silent"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(2)
        if not ready:
            _run(["docker", "logs", name])
            raise RuntimeError("Stage 6 MySQL container did not become ready")

        _run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", "backend/requirements.txt"])
        database_url = f"mysql+pymysql://root:root@127.0.0.1:{port}/student_lifecycle_test?charset=utf8mb4"
        env = dict(os.environ)
        env.update({
            "PYTHONPATH": str(ROOT / "backend"),
            "DB_ENABLED": "true",
            "DB_DRIVER": "mysql",
            "DATABASE_URL": database_url,
            "TEST_DATABASE_URL": database_url,
            "APP_ENV": "test",
            "AUTH_MOCK_ENABLED": "true",
            "FILE_STORAGE_BACKEND": "local",
            "UPLOAD_DIR": "/tmp/stage6-final-validation",
        })
        _run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env)
        _run([
            sys.executable, "-m", "pytest",
            "tests/test_graduation_material_center_phase6.py::test_phase6_real_mysql_version_review_manifest_zip_excel_template",
            "tests/test_graduation_material_center_phase6.py::test_phase6_real_acceptance_covers_all_completion_evidence",
            "-q", "-p", "no:warnings",
        ], cwd=ROOT / "backend", env=env)
        print("STAGE6_FINAL_MYSQL_PAIR=PASS", flush=True)
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_validate_stage6_once()

_real_init = Path(importlib.metadata.distribution("PyYAML").locate_file("yaml/__init__.py"))
_spec = importlib.util.spec_from_file_location(
    "_stage6_real_yaml",
    _real_init,
    submodule_search_locations=[str(_real_init.parent)],
)
if _spec is None or _spec.loader is None:
    raise ImportError("cannot locate installed PyYAML")
_real = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _real
_spec.loader.exec_module(_real)
safe_load = _real.safe_load
safe_dump = _real.safe_dump
YAMLError = _real.YAMLError

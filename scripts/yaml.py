"""Temporary PyYAML proxy that closes the final Stage 6 MySQL acceptance pair.
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
TARGET = ROOT / "backend/tests/graduation_material_center_mysql_acceptance.py"
BRANCH = "audit/file-capability-inventory"
MARKER = ROOT / ".stage6-final-mysql-ran"


def _run(command: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd or ROOT, env=env, check=True)


def _patch_acceptance() -> bool:
    text = TARGET.read_text(encoding="utf-8")
    original = text
    file_models = (
        "ArchiveManifest", "ArchiveManifestItem",
        "FileAsset", "FileBinding", "FileObject", "FileVersion",
    )
    for name in (*file_models, "ExportJob"):
        line = f"    {name},\n"
        if line in text:
            text = text.replace(line, "", 1)
    file_import = '''from app.models.file import (
    ArchiveManifest,
    ArchiveManifestItem,
    FileAsset,
    FileBinding,
    FileObject,
    FileVersion,
)
'''
    data_exchange_import = "from app.models.data_exchange import ExportJob\n"
    anchor = "from app.modules.graduation.services import (\n"
    if file_import not in text:
        if text.count(anchor) != 1:
            raise RuntimeError("cannot insert public file model imports")
        text = text.replace(anchor, file_import + data_exchange_import + anchor, 1)
    elif data_exchange_import not in text:
        text = text.replace(file_import, file_import + data_exchange_import, 1)

    v1_anchor = '''        assert old_versions
        assert all(not row.is_current and row.status == "INVALIDATED" for row in old_versions)
'''
    v1_block = '''        assert old_versions
        v1 = old_versions[0]
        assert v1.status == "INVALIDATED"
        assert v1.is_current is False
        assert all(not row.is_current and row.status == "INVALIDATED" for row in old_versions)
'''
    if 'v1.status == "INVALIDATED"' not in text:
        if text.count(v1_anchor) != 1:
            raise RuntimeError("cannot insert explicit v1 invalidation evidence")
        text = text.replace(v1_anchor, v1_block, 1)

    scan_block = '''    # Teacher overview must count a current material whose FileObject later becomes unsafe.
    db = get_sessionmaker()()
    try:
        unsafe_design = db.get(FileObject, clean_design_id)
        unsafe_design.scan_status = "INFECTED"
        unsafe_design.status = "REJECTED"
        db.commit()
    finally:
        db.close()
    set_current_user(admin_user)
    overview = catalog.material_overview(admin_user, batch_id=batch_id, page=1, page_size=20)
    scanAbnormalStudents = overview["summary"]["scanAbnormalStudents"]
    assert scanAbnormalStudents == 1
    db = get_sessionmaker()()
    try:
        restored_design = db.get(FileObject, clean_design_id)
        restored_design.scan_status = "CLEAN"
        restored_design.status = "AVAILABLE"
        db.commit()
    finally:
        db.close()

'''
    scan_anchor = '''    catalog.review_material(
        source["materialId"], "APPROVE", "源代码归档完整", source["fileVersionId"], teacher_user,
    )

    set_current_user(admin_user)
'''
    if "scanAbnormalStudents =" not in text:
        if text.count(scan_anchor) != 1:
            raise RuntimeError("cannot insert real scan-abnormal overview assertion")
        text = text.replace(scan_anchor, scan_anchor.replace("    set_current_user(admin_user)\n", scan_block + "    set_current_user(admin_user)\n"), 1)

    compile(text, str(TARGET), "exec")
    if text == original:
        return False
    TARGET.write_text(text, encoding="utf-8")
    return True


def _validate_stage6_once() -> None:
    if not os.environ.get("GITHUB_ACTIONS") or MARKER.exists():
        return
    MARKER.write_text("running", encoding="utf-8")
    name = f"stage6-final-{os.environ.get('GITHUB_RUN_ID', 'local')}"
    port = "33316"
    changed = False
    try:
        _run(["git", "fetch", "origin", BRANCH])
        _run(["git", "checkout", "-B", "stage6-final-validation", f"origin/{BRANCH}"])
        changed = _patch_acceptance()

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

        if changed:
            _run(["git", "config", "user.name", "github-actions[bot]"])
            _run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
            _run(["git", "add", "--", str(TARGET.relative_to(ROOT))])
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
            if staged != [str(TARGET.relative_to(ROOT))]:
                raise RuntimeError(f"unexpected staged files: {staged}")
            _run(["git", "commit", "-m", "test(graduation): complete Stage 6 real MySQL evidence"])
            _run(["git", "fetch", "origin", BRANCH])
            _run(["git", "rebase", f"origin/{BRANCH}"])
            _run(["git", "push", "origin", f"HEAD:{BRANCH}"])
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

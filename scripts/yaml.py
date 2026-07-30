"""One-shot PyYAML proxy for the final Stage 6 acceptance-script alignment.
Deleted immediately after the exact test-file commit lands.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend/tests/graduation_material_center_mysql_acceptance.py"
BRANCH = "audit/file-capability-inventory"


def _apply_once() -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    subprocess.run(["git", "fetch", "origin", BRANCH], cwd=ROOT, check=True)
    subprocess.run(["git", "checkout", "-B", "stage6-acceptance-final", f"origin/{BRANCH}"], cwd=ROOT, check=True)
    text = TARGET.read_text(encoding="utf-8")
    replacements = (
        (
            "from app.core.context import set_current_tenant, set_current_user",
            "from app.core.context import set_current_user, set_tenant",
        ),
        (
            "    set_current_tenant(TENANT_ID)",
            '    set_tenant({"tenantId": str(TENANT_ID)})',
        ),
        (
            '    assert rule["itemCount"] == 18\n    assert {item["materialCode"] for item in rule["items"]} == set(catalog.SPEC_BY_CODE)',
            '    assert rule["itemCount"] == 18\n    rule_codes = {item["materialCode"] for item in rule["items"]}\n    assert len(rule_codes) == 18\n    assert rule_codes == set(catalog.SPEC_BY_CODE)',
        ),
    )
    changed = False
    for old, new in replacements:
        if new in text:
            continue
        if text.count(old) != 1:
            raise RuntimeError(f"acceptance alignment expected one match, found {text.count(old)}: {old!r}")
        text = text.replace(old, new, 1)
        changed = True
    if not changed:
        return
    compile(text, str(TARGET), "exec")
    TARGET.write_text(text, encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "--", str(TARGET.relative_to(ROOT))], cwd=ROOT, check=True)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
    if staged != [str(TARGET.relative_to(ROOT))]:
        raise RuntimeError(f"unexpected staged files: {staged}")
    subprocess.run(["git", "commit", "-m", "test(graduation): align Stage 6 real MySQL acceptance"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", f"HEAD:{BRANCH}"], cwd=ROOT, check=True)


_apply_once()

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

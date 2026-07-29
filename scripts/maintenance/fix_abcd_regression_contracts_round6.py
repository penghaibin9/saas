#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(
    str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts_round5.py"),
    run_name="__main__",
)


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) < count:
        raise SystemExit(f"round6 expected snippet not found: {path}\n---\n{old[:600]}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")
    print(f"round6 patched {path}")


replace(
    "backend/tests/test_mobile_wave10.py",
    '''def test_notify_publish_class_scope_and_student_receives(client, db_mode):
    cid = _seed_class(660001)
''',
    '''def _force_non_quiet_publish(monkeypatch):
    from app.services import message_governance_service as governance
    monkeypatch.setattr(
        governance,
        "apply_quiet_hours_policy",
        lambda **kwargs: {
            "publishMode": str(kwargs.get("publish_mode") or "IMMEDIATE").upper(),
            "scheduledAt": kwargs.get("scheduled_at"),
            "quietBypassed": False,
            "note": None,
        },
    )


def test_notify_publish_class_scope_and_student_receives(client, db_mode, monkeypatch):
    _force_non_quiet_publish(monkeypatch)
    cid = _seed_class(660001)
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''def test_notify_preference_filters_messages(client, db_mode):
    cid = _seed_class(660005, n_students=1)
''',
    '''def test_notify_preference_filters_messages(client, db_mode, monkeypatch):
    _force_non_quiet_publish(monkeypatch)
    cid = _seed_class(660005, n_students=1)
''',
)

print("ABCD D-stage deterministic notification patch complete")

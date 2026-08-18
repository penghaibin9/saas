"""A-C1 listener bootstrap must not depend on academic service import order."""
from __future__ import annotations

import subprocess
import sys


def test_current_term_authority_listeners_install_on_cold_models_import():
    code = r'''
import sys
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.models import AaTerm
from app.models.academic_calendar import (
    AcademicCalendarGovernance,
    _active_term_authority_on_set,
    _current_term_authority_before_flush,
    _current_term_authority_on_set,
)

assert event.contains(AaTerm.is_current, "set", _current_term_authority_on_set)
assert event.contains(AcademicCalendarGovernance.active_key, "set", _active_term_authority_on_set)
assert event.contains(Session, "before_flush", _current_term_authority_before_flush)
assert "app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_current_term" not in sys.modules
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

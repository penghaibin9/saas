"""Runtime activation gate for the local Program DEFINITION writer.

The pure write-plan stays non-executable by design; this gate is the only place
that upgrades the plan into writes. It verifies the ORM schema exactly matches
the nullable expand-first contract before any transaction is opened.
"""
from __future__ import annotations

from sqlalchemy import String


def assert_program_definition_execution_ready() -> dict:
    from app.models import AaProgram, AaProgramCourse

    required = (
        (AaProgram, "series_key", 64),
        (AaProgramCourse, "formation_mode", 20),
    )
    evidence = []
    for model, name, length in required:
        if not hasattr(model, name):
            raise RuntimeError(f"Program definition writer schema missing: {model.__name__}.{name}")
        column = model.__table__.c[name]
        if not isinstance(column.type, String) or column.type.length != length:
            raise RuntimeError(
                f"Program definition writer schema mismatch: {model.__name__}.{name}"
            )
        if column.nullable is not True:
            raise RuntimeError(
                f"Program definition writer requires nullable expand column: {model.__name__}.{name}"
            )
        if column.default is not None or column.server_default is not None:
            raise RuntimeError(
                f"Program definition writer forbids historical defaults: {model.__name__}.{name}"
            )
        evidence.append(
            {
                "model": model.__name__,
                "column": name,
                "nullable": True,
                "historicalDefault": None,
            }
        )
    return {"ready": True, "columns": evidence}

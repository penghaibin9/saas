"""Incremental ORM mapping for Program stable identity/provenance expand columns.

The Alembic expand migration owns physical DDL.  This module mirrors those
nullable columns into ORM metadata through the repository's established academic
affairs extension mechanism, so long-lived branches do not have to text-edit the
large shared ``academic_affairs.py`` model file.

Historical rows deliberately remain NULL here as well: no default, backfill,
NOT NULL, or uniqueness policy belongs in model registration.
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import mapped_column

from app.models.academic_affairs import AaProgram, AaProgramCourse


def _add_column(model, name: str, column) -> None:
    if hasattr(model, name):
        return
    setattr(model, name, column)


def install_academic_program_extensions() -> None:
    _add_column(
        AaProgram,
        "series_key",
        mapped_column(
            String(64),
            nullable=True,
            comment="Stable Program series identity; historical rows require evidence-backed backfill",
        ),
    )
    _add_column(
        AaProgramCourse,
        "formation_mode",
        mapped_column(
            String(30),
            nullable=True,
            comment="ProgramCourse formation provenance; historical rows require explicit source evidence",
        ),
    )


install_academic_program_extensions()

"""E integration M7: complete EmpCompany public profile columns required by V3 E4.

Revision ID: 20260815_internship_e_m7
Revises: 20260815_internship_e_m6

This migration is additive only. The canonical enterprise fact remains t_emp_company.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m7"
down_revision = "20260815_internship_e_m6"
branch_labels = None
depends_on = None

_TABLE = "t_emp_company"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m7 requires MySQL")


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    return {column["name"] for column in insp.get_columns(_TABLE)} if insp.has_table(_TABLE) else set()


def upgrade() -> None:
    _require_mysql()
    columns = _columns()
    if not columns:
        raise RuntimeError("t_emp_company must exist before internship E M7")
    additions = (
        ("logo_file_id", sa.Column("logo_file_id", sa.String(64))),
        ("cover_file_id", sa.Column("cover_file_id", sa.String(64))),
        ("short_name", sa.Column("short_name", sa.String(100))),
        ("short_intro", sa.Column("short_intro", sa.String(500))),
        ("website", sa.Column("website", sa.String(300))),
        ("main_business", sa.Column("main_business", sa.Text())),
        ("established_year", sa.Column("established_year", sa.Integer())),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    _require_mysql()
    columns = _columns()
    for name in (
        "established_year",
        "main_business",
        "website",
        "short_intro",
        "short_name",
        "cover_file_id",
        "logo_file_id",
    ):
        if name in columns:
            op.drop_column(_TABLE, name)

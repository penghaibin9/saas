"""student-affairs money columns use DECIMAL(14,2)

Revision ID: 0139_affairs_money_decimal
Revises: 0138_intern_position_facts
"""
from alembic import op
import sqlalchemy as sa

revision = "0139_affairs_money_decimal"
down_revision = "0138_intern_position_facts"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("t_affairs_funding_project", "amount", 12),
    ("t_affairs_funding_application", "amount", 12),
    ("t_affairs_funding_disbursement", "amount", 12),
    ("t_affairs_work_study_post", "salary", 10),
    ("t_affairs_work_study_record", "subsidy_total", 12),
    ("t_affairs_work_study_monthly", "subsidy_amount", 10),
    ("t_affairs_student_loan", "amount", 12),
    ("t_affairs_fee_reduction", "amount", 12),
)


def upgrade():
    for table, column, precision in _COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(precision, 2),
            type_=sa.Numeric(14, 2),
            existing_nullable=True,
        )


def downgrade():
    for table, column, precision in reversed(_COLUMNS):
        op.alter_column(
            table, column,
            existing_type=sa.Numeric(14, 2),
            type_=sa.Numeric(precision, 2),
            existing_nullable=True,
        )

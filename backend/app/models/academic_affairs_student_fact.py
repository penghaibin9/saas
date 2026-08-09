"""Stage C1: temporal academic identity facts for historical replay."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, UniqueConstraint, event, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin
from app.models.student import StudentProfile


_FACT_DATETIME = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


class StudentAcademicFact(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """A student's effective-dated academic identity.

    ``StudentProfile`` remains the current projection for hot-path reads. Historical
    reads must resolve this ledger by ``as_of`` instead of reading today's profile.
    Facts are append-oriented: a transition only closes the current row's
    ``valid_to`` and inserts the next version.

    MySQL uses DATETIME(6) here because second-only precision can collapse a pre-change
    read and the following fact switch into the same timestamp, making historical
    replay nondeterministic under fast consecutive operations.
    """

    __tablename__ = "t_aa_student_academic_fact"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "version_no", name="uk_aa_student_fact_version"),
        Index("ix_aa_student_fact_asof", "tenant_id", "student_id", "valid_from", "valid_to"),
        Index("ix_aa_student_fact_active", "tenant_id", "student_id", "valid_to"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(_FACT_DATETIME, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(_FACT_DATETIME)

    student_status: Mapped[str] = mapped_column(String(50), nullable=False)
    college_id: Mapped[int | None] = mapped_column(BigInteger)
    major_id: Mapped[int | None] = mapped_column(BigInteger)
    class_id: Mapped[int | None] = mapped_column(BigInteger)
    grade: Mapped[str | None] = mapped_column(String(20))

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    source_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EXACT", comment="EXACT/DERIVED/INFERRED/UNKNOWN"
    )


def _fact_table_ready(connection) -> bool:
    """Check table presence without permanently caching a pre-migration ``False``.

    During ``alembic upgrade head`` the ORM can be imported before the C1 migration
    creates this table.  A pooled connection that observed "missing" must check again
    later; otherwise all StudentProfile inserts on that connection would silently miss
    their version-1 fact even after the migration completed.  ``True`` is safe to cache,
    ``False`` is deliberately not cached.
    """
    key = "stage_c1_academic_fact_table_ready"
    if connection.info.get(key) is True:
        return True
    ready = inspect(connection).has_table(StudentAcademicFact.__tablename__)
    if ready:
        connection.info[key] = True
    else:
        connection.info.pop(key, None)
    return bool(ready)


@event.listens_for(StudentProfile, "after_insert", propagate=True)
def _bootstrap_new_student_academic_fact(_mapper, connection, target: StudentProfile) -> None:
    """Keep every newly-created profile and its version-1 academic fact atomic.

    Existing rows are handled by the Alembic baseline backfill. This mapper hook is
    intentionally insert-only: later status/organization changes must go through the
    canonical Stage C1 append command, never an automatic update hook that could hide
    a bypass. Raw SQL profile inserts remain detectable by reconciliation/bypass gates.
    """
    if not _fact_table_ready(connection):
        return
    created_at = target.created_at or datetime.utcnow()
    connection.execute(
        StudentAcademicFact.__table__.insert().values(
            tenant_id=int(target.tenant_id),
            student_id=int(target.id),
            version_no=1,
            valid_from=created_at,
            valid_to=None,
            student_status=target.student_status or "NORMAL",
            college_id=target.college_id,
            major_id=target.major_id,
            class_id=target.class_id,
            grade=target.grade,
            source_type="PROFILE_CREATE",
            source_ref_id=None,
            source_quality="EXACT",
            created_at=created_at,
            created_by=target.created_by,
        )
    )

"""Teaching-building catalogue. Classroom IDs and historical location snapshots stay stable."""
from sqlalchemy import String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, PKMixin, TenantMixin, CommonMixin


class AaTeachingBuilding(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_teaching_building"
    building_code: Mapped[str] = mapped_column(String(50), nullable=False)
    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    campus_code: Mapped[str | None] = mapped_column(String(50))
    floor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "building_code", name="uk_aa_teaching_building"),)

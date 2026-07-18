"""学生主档（冻结册 §4.7 表卡，字段级 DDL 见 01 中心；此处为第一批骨架，缺失字段以 TODO 标注）。
敏感字段一律 *_encrypted + *_hash（§17.2），库中不存明文：手机号/身份证/家庭住址/监护人电话/紧急联系人电话/邮箱。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.student_lifecycle import ENROLLED
from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class StudentProfile(PKMixin, TenantMixin, CommonMixin, Base):
    """t_student_profile 学生主档——全平台唯一学生身份，id 即 student_id。"""
    __tablename__ = "t_student_profile"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_no", name="uk_tenant_student_no"),
        Index("ix_student_tenant_active_id", "tenant_id", "is_deleted", "id"),
        Index("ix_student_tenant_class_active_id", "tenant_id", "class_id", "is_deleted", "id"),
        Index("ix_student_tenant_college_active_id", "tenant_id", "college_id", "is_deleted", "id"),
        Index("ix_student_tenant_major_active_id", "tenant_id", "major_id", "is_deleted", "id"),
    )

    student_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="学号")
    real_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                            comment="姓名（冻结册：非敏感）；建索引:审批/巡访/迁移期姓名兜底查询消全表扫描")
    gender: Mapped[str | None] = mapped_column(String(10))
    id_card_encrypted: Mapped[str | None] = mapped_column(String(500), comment="敏感：身份证密文（id_card）")
    id_card_hash: Mapped[str | None] = mapped_column(String(128), index=True, comment="身份证 hash（查重）")
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    major_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    grade: Mapped[str | None] = mapped_column(String(20))
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default=ENROLLED,
                                               comment="生命周期阶段（冻结册 §5.1 枚举）")
    student_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL",
                                                comment="学生状态（§5.2：NORMAL/MERGED/RECYCLED 等）")
    data_quality_status: Mapped[str | None] = mapped_column(String(50), comment="数据质量状态")
    enroll_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE",
                                        comment="TODO：与 student_status 口径以 01 中心为准")
    remark: Mapped[str | None] = mapped_column(String(500))


class StudentContact(PKMixin, TenantMixin, CommonMixin, Base):
    """t_student_contact 联系方式（手机/邮箱/地址/紧急联系人，加密存储）。"""
    __tablename__ = "t_student_contact"
    __table_args__ = (
        Index("ix_contact_tenant_student_type_active",
              "tenant_id", "student_id", "contact_type", "is_deleted"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="= t_student_profile.id")
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                              comment="PHONE/EMAIL/HOME_ADDRESS/GUARDIAN_PHONE/EMERGENCY_PHONE")
    contact_value_encrypted: Mapped[str | None] = mapped_column(String(500), comment="敏感：联系值密文")
    contact_value_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), comment="联系人姓名（紧急联系人/监护人）")
    verified_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNVERIFIED",
                                                 comment="UNVERIFIED/VERIFIED/EXPIRED")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(500))


class StudentStageEvent(PKMixin, TenantMixin, Base):
    """t_student_stage_event 阶段流转留痕（学籍状态记录）——append-only：
    无 is_deleted / updated_at / updated_by / version（冻结册 §1.2 例外）。"""
    __tablename__ = "t_student_stage_event"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_stage: Mapped[str | None] = mapped_column(String(50))
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    source_module: Mapped[str | None] = mapped_column(String(50))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class StudentImportBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_student_import_batch 导入批次（Dry-Run + 整批事务回滚，§4.7）。"""
    __tablename__ = "t_student_import_batch"

    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, comment="批次号")
    file_id: Mapped[int | None] = mapped_column(BigInteger, comment="上传文件 t_file_object.id")
    total_rows: Mapped[int | None] = mapped_column(BigInteger)
    success_rows: Mapped[int | None] = mapped_column(BigInteger)
    error_rows: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UPLOADED",
        comment="UPLOADED/DRY_RUN_PASSED/DRY_RUN_FAILED/CONFIRMED/WRITING/SUCCESS/FAILED/ROLLED_BACK")
    remark: Mapped[str | None] = mapped_column(String(500))

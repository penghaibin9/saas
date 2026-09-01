"""13A-P6 宿舍房源台账（楼/房/床）+ 调宿 + 宿舍检查模型（草案 §3.8）。

房源三级：building(楼) → room(房,含 floor_no/capacity) → bed(床,占用事实源)。
床位占用变更事务内回写 t_cs_dorm_record（既有"我的宿舍"读链路零改动）。
调宿：原床释放/新床占用,走审批。检查：异常回写 t_cs_dorm_exception + 生成风险(source=DORM)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, CheckConstraint, DateTime, Index,
                        Integer, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class DormBuilding(PKMixin, TenantMixin, CommonMixin, Base):
    """楼栋（宿管 scope_type=DORM_BUILDING 的 ref 对象）。ENABLED/DISABLED。"""
    __tablename__ = "t_affairs_dorm_building"

    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    building_code: Mapped[str | None] = mapped_column(String(50), index=True)
    gender_limit: Mapped[str] = mapped_column(String(20), nullable=False, default="MIXED",
                                              comment="MALE/FEMALE/MIXED 男寝/女寝/混合")
    manager_teacher_key: Mapped[str | None] = mapped_column(String(100), comment="宿管 teacher_key")
    floor_count: Mapped[int | None] = mapped_column(Integer, comment="层数（生成器用）")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENABLED")


class DormRoom(PKMixin, TenantMixin, CommonMixin, Base):
    """房间。ENABLED/DISABLED/MAINTAIN。capacity=几人间（=床位数）。"""
    __tablename__ = "t_affairs_dorm_room"

    building_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    floor_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几层")
    room_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="房号")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4, comment="床位数/几人间")
    room_type: Mapped[str | None] = mapped_column(String(50), comment="STANDARD/... 房型")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENABLED")

    __table_args__ = (UniqueConstraint("tenant_id", "building_id", "room_no",
                                       name="uk_dorm_room_building_no"),)


class DormBed(PKMixin, TenantMixin, CommonMixin, Base):
    """床位（占用事实源）。student_id 空=空床；占用变更事务内回写 t_cs_dorm_record。"""
    __tablename__ = "t_affairs_dorm_bed"

    building_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    bed_no: Mapped[str] = mapped_column(String(50), nullable=False, comment="床号 如 512-1")
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="占用学生,空=空床")
    occupied_at: Mapped[datetime | None] = mapped_column(DateTime)
    cs_dorm_record_id: Mapped[int | None] = mapped_column(BigInteger, comment="回写 t_cs_dorm_record 回链")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="VACANT",
                                        comment="VACANT/OCCUPIED/LOCKED")

    __table_args__ = (UniqueConstraint("tenant_id", "room_id", "bed_no",
                                       name="uk_dorm_bed_room_no"),)


class DormStay(PKMixin, TenantMixin, CommonMixin, Base):
    """住宿历史 Authority；DormBed.student_id 仍只表示当前占用指针。"""
    __tablename__ = "t_affairs_dorm_stay"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_type", "source_biz_id",
            name="uk_dorm_stay_source",
        ),
        Index(
            "ix_dorm_stay_student_status",
            "tenant_id", "student_id", "status", "is_deleted",
        ),
        Index(
            "ix_dorm_stay_bed_status",
            "tenant_id", "bed_id", "status", "is_deleted",
        ),
        CheckConstraint(
            "status IN ('RESERVED','ACTIVE','ENDED','CANCELLED')",
            name="ck_dorm_stay_status",
        ),
        CheckConstraint(
            "(status IN ('RESERVED','ACTIVE') AND checkout_at IS NULL) "
            "OR (status='ENDED' AND checkout_at IS NOT NULL) "
            "OR status='CANCELLED'",
            name="ck_dorm_stay_lifecycle",
        ),
    )

    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="学生 Authority → t_student_profile.id",
    )
    bed_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="床位 Authority → t_affairs_dorm_bed.id",
    )
    building_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="楼栋稳定 ID 快照",
    )
    room_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="房间稳定 ID 快照",
    )
    stay_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="CURRENT_OCCUPANCY/ALLOCATION/TRANSFER/HISTORY_IMPORT",
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="DORM_BED_BACKFILL/ALLOCATION/TRANSFER/MANUAL",
    )
    source_biz_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="来源业务稳定键",
    )
    checkin_at: Mapped[datetime | None] = mapped_column(DateTime)
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="RESERVED/ACTIVE/ENDED/CANCELLED",
    )
    checkin_operator_id: Mapped[int | None] = mapped_column(BigInteger)
    checkout_operator_id: Mapped[int | None] = mapped_column(BigInteger)


class DormCheckoutRequest(PKMixin, TenantMixin, CommonMixin, Base):
    """正式退宿单；确认前不释放床位，毕业批退只通过来源键接入。"""
    __tablename__ = "t_affairs_dorm_checkout_request"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "client_request_id", name="uk_dorm_checkout_client_request",
        ),
        UniqueConstraint(
            "tenant_id", "source_type", "source_biz_id", name="uk_dorm_checkout_source",
        ),
        Index(
            "ix_dorm_checkout_student_status",
            "tenant_id", "student_id", "status", "is_deleted",
        ),
        Index(
            "ix_dorm_checkout_building_status",
            "tenant_id", "building_id", "status", "is_deleted",
        ),
        CheckConstraint(
            "request_type IN ('GRADUATION','LEAVE_OF_ABSENCE','WITHDRAWAL','DAY_STUDENT','SPECIAL')",
            name="ck_dorm_checkout_request_type",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL','GRADUATION_BATCH')",
            name="ck_dorm_checkout_source_type",
        ),
        CheckConstraint(
            "status IN ('PENDING_CONFIRMATION','BLOCKED','CONFIRMED','CANCELLED')",
            name="ck_dorm_checkout_status",
        ),
        CheckConstraint(
            "status <> 'CONFIRMED' OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)",
            name="ck_dorm_checkout_confirmed",
        ),
        CheckConstraint(
            "status <> 'CANCELLED' OR (cancelled_at IS NOT NULL AND cancelled_by IS NOT NULL)",
            name="ck_dorm_checkout_cancelled",
        ),
    )

    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="学生 Authority → t_student_profile.id",
    )
    stay_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="发起时 ACTIVE DormStay 稳定 ID",
    )
    bed_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="发起时当前床位稳定 ID",
    )
    building_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="GRADUATION/LEAVE_OF_ABSENCE/WITHDRAWAL/DAY_STUDENT/SPECIAL",
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="MANUAL/GRADUATION_BATCH",
    )
    source_biz_id: Mapped[str | None] = mapped_column(
        String(100), comment="毕业批退等上游稳定来源键；人工发起为空",
    )
    client_request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    blockers_json: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="PENDING_CONFIRMATION/BLOCKED/CONFIRMED/CANCELLED",
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    requested_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_by: Mapped[int | None] = mapped_column(BigInteger)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger)
    cancel_reason: Mapped[str | None] = mapped_column(String(500))


class DormAllocationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """住宿分配批次；D3 才开放自动/人工/学生自选运行链。"""
    __tablename__ = "t_affairs_dorm_allocation_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_no", name="uk_dorm_alloc_batch_no"),
        Index(
            "ix_dorm_alloc_batch_orientation",
            "tenant_id", "orientation_batch_id", "is_deleted",
        ),
        Index(
            "ix_dorm_alloc_batch_status_window",
            "tenant_id", "status", "open_at", "close_at", "is_deleted",
        ),
        CheckConstraint("open_at < close_at", name="ck_dorm_alloc_batch_window"),
        CheckConstraint(
            "mode IN ('ADMIN_AUTO','ADMIN_MANUAL','STUDENT_SELECT','POST_CHECKIN_PUBLISH')",
            name="ck_dorm_alloc_batch_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','CLOSED','CANCELLED')",
            name="ck_dorm_alloc_batch_status",
        ),
        CheckConstraint(
            "status <> 'PUBLISHED' OR published_at IS NOT NULL",
            name="ck_dorm_alloc_batch_publish_time",
        ),
    )

    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="ORIENTATION/GENERAL/ROLLING",
    )
    orientation_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="可选迎新批次 Authority → t_orientation_batch.id",
    )
    mode: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="ADMIN_AUTO/ADMIN_MANUAL/STUDENT_SELECT/POST_CHECKIN_PUBLISH",
    )
    open_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    close_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="DRAFT/PUBLISHED/CLOSED/CANCELLED",
    )
    rules_json: Mapped[dict | None] = mapped_column(JSON)
    resource_scope_json: Mapped[dict | None] = mapped_column(JSON)
    student_scope_json: Mapped[dict | None] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)


class DormAllocationItem(PKMixin, TenantMixin, CommonMixin, Base):
    """一名学生在一个住宿分配批次中的唯一分配项。"""
    __tablename__ = "t_affairs_dorm_allocation_item"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "allocation_batch_id", "student_id",
            name="uk_dorm_alloc_item_student",
        ),
        UniqueConstraint(
            "tenant_id", "allocation_batch_id", "bed_id",
            name="uk_dorm_alloc_item_bed",
        ),
        Index(
            "ix_dorm_alloc_item_bed_status",
            "tenant_id", "bed_id", "status", "is_deleted",
        ),
        Index(
            "ix_dorm_alloc_item_batch_status",
            "tenant_id", "allocation_batch_id", "status", "is_deleted",
        ),
        CheckConstraint(
            "status IN ('PENDING','PROPOSED','RESERVED','CONFIRMED','CONFLICT','CANCELLED')",
            name="ck_dorm_alloc_item_status",
        ),
    )

    allocation_batch_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="住宿分配批次稳定 ID",
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="学生 Authority → t_student_profile.id",
    )
    bed_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="提议/预留/确认的床位稳定 ID",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="PENDING/PROPOSED/RESERVED/CONFIRMED/CONFLICT/CANCELLED",
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="AUTO/MANUAL/STUDENT_SELECT/IMPORT",
    )
    conflict_code: Mapped[str | None] = mapped_column(String(100))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DormTransfer(PKMixin, TenantMixin, CommonMixin, Base):
    """调宿申请（原床释放/新床占用）。8 态,走审批 AFFAIRS_DORM_TRANSFER。"""
    __tablename__ = "t_affairs_dorm_transfer"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_bed_id: Mapped[int | None] = mapped_column(BigInteger)
    to_bed_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/COUNSELOR_REVIEW/DORM_MANAGER_REVIEW/APPROVED/REJECTED/RETURNED/CANCELLED/EXECUTED")
    current_node: Mapped[str | None] = mapped_column(String(50))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    return_reason: Mapped[str | None] = mapped_column(String(500))


class DormCheckTask(PKMixin, TenantMixin, CommonMixin, Base):
    """宿舍检查任务（按楼/层圈定）。DRAFT/RUNNING/DONE/CANCELLED。"""
    __tablename__ = "t_affairs_dorm_check_task"

    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    building_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, default="HYGIENE",
                                            comment="HYGIENE/SAFETY/CONTRABAND/NIGHT_ABSENCE 卫生/安全/违禁/夜不归宿")
    checker_key: Mapped[str | None] = mapped_column(String(100))
    planned_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class DormCheckRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """检查记录（异常回写 t_cs_dorm_exception + 生成风险 source=DORM）。"""
    __tablename__ = "t_affairs_dorm_check_record"

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    room_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL",
                                        comment="NORMAL/ABNORMAL")
    issue_type: Mapped[str | None] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(String(1000))
    rectify_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    related_exception_id: Mapped[int | None] = mapped_column(BigInteger, comment="回写 t_cs_dorm_exception 回链")
    related_risk_id: Mapped[int | None] = mapped_column(BigInteger)
    student_ids_json: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL", index=True,
                                        comment="NORMAL/ABNORMAL/RECTIFYING/CLOSED")

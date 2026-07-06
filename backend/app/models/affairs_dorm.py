"""13A-P6 宿舍房源台账（楼/房/床）+ 调宿 + 宿舍检查模型（草案 §3.8）。

房源三级：building(楼) → room(房,含 floor_no/capacity) → bed(床,占用事实源)。
床位占用变更事务内回写 t_cs_dorm_record（既有"我的宿舍"读链路零改动）。
调宿：原床释放/新床占用,走审批。检查：异常回写 t_cs_dorm_exception + 生成风险(source=DORM)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
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

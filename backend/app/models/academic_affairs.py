"""13B-P1 教务中心模型（t_aa_* 前缀；草案 §4.1/§4.2）。

时间轴基座：term(学年学期) / calendar_event(校历) / time_slot(作息节次)。
学籍：status_change(异动流水，change_student_status 单一入口写入) / registration_batch / registration。
禁建学生主表——学籍状态受控扩展 t_student_profile.student_status 枚举（零加列），写侧唯一经 change_student_status()。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, Integer, Numeric, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaTerm(PKMixin, TenantMixin, CommonMixin, Base):
    """学年学期（学年编码并入）。DRAFT/PUBLISHED/FROZEN/ARCHIVED。唯一(tenant,year_code,term_no)。"""
    __tablename__ = "t_aa_term"

    year_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="学年 如 2026-2027")
    term_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="学期 1/2")
    term_name: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    teaching_weeks: Mapped[int | None] = mapped_column(Integer)
    exam_week_start: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "year_code", "term_no", name="uk_aa_term"),)


class AaCalendarEvent(PKMixin, TenantMixin, CommonMixin, Base):
    """校历事件（回链 term_id）。TEACHING/EXAM/INTERNSHIP/HOLIDAY/SWAP。"""
    __tablename__ = "t_aa_calendar_event"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="TEACHING")
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    swap_to_date: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class AaTimeSlot(PKMixin, TenantMixin, CommonMixin, Base):
    """作息节次（课表坐标系）。ENABLED/DISABLED。"""
    __tablename__ = "t_aa_time_slot"

    slot_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="第 N 节")
    slot_name: Mapped[str | None] = mapped_column(String(50))
    start_time: Mapped[str | None] = mapped_column(String(10), comment="HH:MM")
    end_time: Mapped[str | None] = mapped_column(String(10))
    campus_code: Mapped[str | None] = mapped_column(String(50), comment="预留多校区")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ENABLED")


class AaStatusChange(PKMixin, TenantMixin, CommonMixin, Base):
    """学籍异动流水单（change_student_status 单一入口写入；P1 仅注册类，异动全类 P2）。"""
    __tablename__ = "t_aa_status_change"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                             comment="ENROLL_REGISTER/ANNUAL_REGISTER/TRANSFER_MAJOR/SUSPEND/RESUME/WITHDRAW/RETAIN/TRANSFER_SCHOOL/GRADUATE/COMPLETE")
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str | None] = mapped_column(String(50))
    from_college_id: Mapped[int | None] = mapped_column(BigInteger)
    from_major_id: Mapped[int | None] = mapped_column(BigInteger)
    from_class_id: Mapped[int | None] = mapped_column(BigInteger)
    to_college_id: Mapped[int | None] = mapped_column(BigInteger)
    to_major_id: Mapped[int | None] = mapped_column(BigInteger)
    to_class_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500), comment="异动原因(敏感脱敏)")
    effective_date: Mapped[datetime | None] = mapped_column(DateTime)
    expire_date: Mapped[datetime | None] = mapped_column(DateTime, comment="休学到期日(P2真实补充:最长年限)")
    term_code: Mapped[str | None] = mapped_column(String(50))
    current_node: Mapped[str | None] = mapped_column(String(50), comment="多节点审批当前节点")
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger, comment="来源单据(注册/异动)")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="EFFECTIVE", index=True,
                                        comment="DRAFT/SUBMITTED/IN_REVIEW/APPROVED/REJECTED/RETURNED/CANCELLED/EFFECTIVE/ARCHIVED")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class AaRegistrationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """注册批次（入学/学年注册共用引擎）。DRAFT/OPEN/CONFIRMING/CLOSED/ARCHIVED。"""
    __tablename__ = "t_aa_registration_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    register_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ENROLL",
                                               comment="ENROLL 入学 / ANNUAL 学年")
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime)
    window_end: Mapped[datetime | None] = mapped_column(DateTime)
    scope_json: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)


class AaRegistration(PKMixin, TenantMixin, CommonMixin, Base):
    """学生注册记录（预检快照+结果）。PENDING_REGISTER/REGISTERED/UNREGISTERED。唯一(tenant,batch,student)。"""
    __tablename__ = "t_aa_registration"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    precheck_json: Mapped[str | None] = mapped_column(String(2000), comment="报到·缴费·材料·绿通快照")
    register_at: Mapped[datetime | None] = mapped_column(DateTime)
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REGISTER", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id", name="uk_aa_registration"),)


# ═══════════ 培养方案组（13B-P2 建表 + 编制骨架；审批发布 P3）═══════════


class AaProgram(PKMixin, TenantMixin, CommonMixin, Base):
    """培养方案主档（毕业要求 JSONB 并入）。发布后改动强制新版本(prev_version_id 链)。"""
    __tablename__ = "t_aa_program"

    program_name: Mapped[str] = mapped_column(String(200), nullable=False)
    major_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    grade_year: Mapped[str | None] = mapped_column(String(20), comment="适用年级 如 2026")
    total_credits: Mapped[float | None] = mapped_column(Integer)
    requirement_json: Mapped[str | None] = mapped_column(String(2000), comment="分模块学分要求")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prev_version_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/COLLEGE_REVIEW/ACADEMIC_REVIEW/RETURNED/PUBLISHED/ENABLED/FROZEN/DISABLED")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class AaProgramCourse(PKMixin, TenantMixin, CommonMixin, Base):
    """方案-课程明细（学期安排）。course_id→t_aa_course(P3)；P2 编制期以 course_name 文本占位。"""
    __tablename__ = "t_aa_program_course"

    program_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_aa_course(P3);编制期可空")
    course_name: Mapped[str | None] = mapped_column(String(200), comment="P2 编制期课程名占位")
    open_term_no: Mapped[int | None] = mapped_column(Integer, comment="第几学期开课")
    module: Mapped[str | None] = mapped_column(String(50), comment="课程模块 公共/专业/实践…")
    credit_snapshot: Mapped[float | None] = mapped_column(Integer)


class AaProgramBinding(PKMixin, TenantMixin, CommonMixin, Base):
    """方案-年级/班级绑定（历史年级锁旧版本）。ACTIVE/SUPERSEDED。"""
    __tablename__ = "t_aa_program_binding"

    program_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    major_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    grade_year: Mapped[str | None] = mapped_column(String(20))
    class_id: Mapped[int | None] = mapped_column(BigInteger, comment="nullable=全专业")
    bound_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")


# ═══════════ 课程库与教学任务组（13B-P3；商业教务软件全字段）═══════════


class AaCourse(PKMixin, TenantMixin, CommonMixin, Base):
    """课程库（版本化字典，两级审核）。字段对齐正方/强智等成熟教务软件。唯一(tenant,course_code,version)。"""
    __tablename__ = "t_aa_course"

    course_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="课程代码")
    course_name: Mapped[str] = mapped_column(String(200), nullable=False)
    course_name_en: Mapped[str | None] = mapped_column(String(200), comment="课程英文名")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="MAJOR_CORE",
                                          comment="PUBLIC_BASIC/DISCIPLINE_BASIC/MAJOR_CORE/MAJOR_ELECTIVE/PRACTICE 公共基础/学科基础/专业核心/专业选修/集中实践")
    nature: Mapped[str] = mapped_column(String(50), nullable=False, default="REQUIRED",
                                        comment="REQUIRED/ELECTIVE/LIMITED_ELECTIVE/PUBLIC_ELECTIVE 必修/选修/限选/公选")
    credit: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False, default=0, comment="学分")
    hours_total: Mapped[int | None] = mapped_column(Integer, comment="总学时")
    hours_theory: Mapped[int | None] = mapped_column(Integer, comment="理论学时")
    hours_practice: Mapped[int | None] = mapped_column(Integer, comment="实践学时")
    hours_experiment: Mapped[int | None] = mapped_column(Integer, comment="实验学时")
    hours_computer: Mapped[int | None] = mapped_column(Integer, comment="上机学时")
    exam_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="EXAM",
                                           comment="EXAM/CHECK 考试/考查")
    owner_college_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="开课单位")
    owner_teacher_id: Mapped[int | None] = mapped_column(BigInteger, comment="课程负责人")
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否核心课/学位课")
    prerequisite_codes_json: Mapped[str | None] = mapped_column(String(500), comment="先修课代码 JSON")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prev_version_id: Mapped[int | None] = mapped_column(BigInteger, comment="上一版本(改动强制新版本链)")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/COLLEGE_REVIEW/ACADEMIC_REVIEW/ENABLED/RETURNED/DISABLED")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "course_code", "version", name="uk_aa_course"),)


class AaTeachingTaskBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """学期教学任务批次（按方案生成应开课程，generate 幂等）。DRAFT/COLLEGE_CONFIRMED/TEACHER_CONFIRMED/SUBMITTED/APPROVED。"""
    __tablename__ = "t_aa_teaching_task_batch"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    generate_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class AaTeachingTask(PKMixin, TenantMixin, CommonMixin, Base):
    """教学任务（课程×教学班×教师）。含教学班(可合班)+周学时/起止周。PENDING_ASSIGN/ASSIGNED/TEACHER_CONFIRMED/REJECTED_BY_TEACHER。"""
    __tablename__ = "t_aa_teaching_task"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_code: Mapped[str | None] = mapped_column(String(50))
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teaching_class_code: Mapped[str | None] = mapped_column(String(50), comment="教学班代码")
    teaching_class_name: Mapped[str | None] = mapped_column(String(200), comment="教学班名(可合班)")
    is_merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否合班")
    teacher_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100))
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    expected_students: Mapped[int | None] = mapped_column(Integer, comment="预计人数")
    weekly_hours: Mapped[int | None] = mapped_column(Integer, comment="周学时")
    total_hours: Mapped[int | None] = mapped_column(Integer, comment="计划总学时")
    start_week: Mapped[int | None] = mapped_column(Integer, comment="起始周")
    end_week: Mapped[int | None] = mapped_column(Integer, comment="结束周")
    confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_ASSIGN", index=True)


# ═══════════ 课表组（13B-P4；三重冲突检测 + 单双周，对齐正方/强智）═══════════


class AaScheduleBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """课表批次（预发布→发布通知→归档）。DRAFT/PRE_PUBLISHED/PUBLISHED/ARCHIVED。"""
    __tablename__ = "t_aa_schedule_batch"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)


class AaScheduleItem(PKMixin, TenantMixin, CommonMixin, Base):
    """课表项（手工/导入双通道，同一冲突检测器）。EFFECTIVE/CHANGED/CANCELLED（V1 仅 EFFECTIVE）。"""
    __tablename__ = "t_aa_schedule_item"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_teaching_task")
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_name: Mapped[str | None] = mapped_column(String(100))
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, comment="星期 1-7")
    slot_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="节次 →t_aa_time_slot")
    start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="起始周")
    end_week: Mapped[int] = mapped_column(Integer, nullable=False, default=18, comment="结束周")
    week_parity: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL",
                                             comment="ALL/ODD/EVEN 全周/单周/双周")
    classroom_text: Mapped[str | None] = mapped_column(String(100), index=True, comment="教室(V1文本)")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="EFFECTIVE", index=True)

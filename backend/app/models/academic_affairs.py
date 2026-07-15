"""13B-P1 教务中心模型（t_aa_* 前缀；草案 §4.1/§4.2）。

时间轴基座：term(学年学期) / calendar_event(校历) / time_slot(作息节次)。
学籍：status_change(异动流水，change_student_status 单一入口写入) / registration_batch / registration。
禁建学生主表——学籍状态受控扩展 t_student_profile.student_status 枚举（零加列），写侧唯一经 change_student_status()。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, Integer, Numeric, String,
                        Text, UniqueConstraint)
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
    """学生注册记录（预检快照+结果）。PENDING_REGISTER/REGISTERED/UNREGISTERED。唯一(tenant,batch,student)。

    13B-P1-R1（注册管理 Tier1 六叶）加列：注册资格核验结果独立于最终注册结果记录——
    eligibility_status 由「注册资格核验」页写入（PENDING/ELIGIBLE/INELIGIBLE），不影响 status 本身
    （register_student 仍是唯一使学生转 REGISTERED 的入口，核验只做前置留痕，不做硬阻断）。
    """
    __tablename__ = "t_aa_registration"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    precheck_json: Mapped[str | None] = mapped_column(String(2000), comment="报到·缴费·材料·绿通快照")
    register_at: Mapped[datetime | None] = mapped_column(DateTime)
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REGISTER", index=True)
    eligibility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                                     comment="资格核验结果 PENDING/ELIGIBLE/INELIGIBLE")
    eligibility_note: Mapped[str | None] = mapped_column(String(500), comment="核验意见/不合格原因")
    eligibility_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    eligibility_checked_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id", name="uk_aa_registration"),)


class AaRegistrationException(PKMixin, TenantMixin, CommonMixin, Base):
    """注册异常（身份不符/未缴费/材料缺失/其他）。核验或核对环节标记，通知辅导员，教务/学院处理后解除。"""
    __tablename__ = "t_aa_registration_exception"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    registration_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="关联注册记录(存在时)")
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(30), nullable=False, default="OTHER",
                                                comment="IDENTITY_MISMATCH/UNPAID/MATERIAL_MISSING/OTHER")
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True,
                                        comment="OPEN/RESOLVED")
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger)


class AaRegistrationDeferral(PKMixin, TenantMixin, CommonMixin, Base):
    """暂缓注册申请（材料未齐/特殊原因需延后注册窗口）。PENDING/APPROVED/REJECTED。"""
    __tablename__ = "t_aa_registration_deferral"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_until: Mapped[datetime | None] = mapped_column(DateTime, comment="申请延后至该日期前完成注册")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/APPROVED/REJECTED")
    review_note: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)


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


class AaProgramGraduationRequirement(PKMixin, TenantMixin, CommonMixin, Base):
    """培养方案毕业要求条目（知识/能力/素质/职业证书分类，独立于学分结构的结构化条目）。
    13B-培养方案 Tier1 补建（§2.9 编制页②毕业要求子步骤）；ACTIVE/REMOVED 逻辑态，配合 is_deleted 使用。"""
    __tablename__ = "t_aa_program_graduation_requirement"

    program_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="ABILITY",
                                          comment="KNOWLEDGE/ABILITY/QUALITY/CERTIFICATE 知识/能力/素质/职业证书")
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
    """学期教学任务批次（按方案生成应开课程，generate 幂等）。
    状态：DRAFT(生成/核对分配中)/COLLEGE_CONFIRMED(学院核对确认，待教务终审)/APPROVED(教务终审通过)/RETURNED(教务退回重办)。
    兼容：/submit 端点保留 DRAFT→APPROVED 单步直提（历史契约不变）；/college-confirm+/review 为 Tier1 新增两级确认链。"""
    __tablename__ = "t_aa_teaching_task_batch"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    generate_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class AaTeachingTask(PKMixin, TenantMixin, CommonMixin, Base):
    """教学任务（课程×教学班×教师）。含教学班(可合班)+周学时/起止周。
    状态：PENDING_ASSIGN/ASSIGNED/TEACHER_CONFIRMED/REJECTED_BY_TEACHER/READY(批次教务终审通过)/MERGED(已被合班并入他行)。
    合班：多行合并为一行(survivor, is_merged=True)，其余行 status=MERGED 且 merged_into_id 指向 survivor；
    survivor.merge_snapshot_json 记录合并前自身快照，供拆班（split）精确还原（Tier1 R1）。"""
    __tablename__ = "t_aa_teaching_task"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_code: Mapped[str | None] = mapped_column(String(50))
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teaching_class_code: Mapped[str | None] = mapped_column(String(50), comment="教学班代码")
    teaching_class_name: Mapped[str | None] = mapped_column(String(200), comment="教学班名(可合班)")
    is_merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否合班(本行为合班后 survivor)")
    merged_into_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="被并入的 survivor 教学任务 id(本行 status=MERGED 时有效)")
    merge_snapshot_json: Mapped[str | None] = mapped_column(String(1000), comment="合班快照(survivor 合并前自身字段+成员 taskId 列表)，供拆班还原")
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
    change_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
                                                  comment="→ t_aa_schedule_change 生成本项的调停课单(变更标记/回链)；null=原始排课")
    objection_status: Mapped[str | None] = mapped_column(String(20), index=True,
                                                          comment="11号卡·排课调整：教师异议状态 PENDING=待改排；null=无异议")
    objection_reason: Mapped[str | None] = mapped_column(String(500), comment="教师异议原因（≥5字）")


# ═══════════ 成绩录入组（13B-P5；平时+期末按比例，发布原子回写 t_acad_grade）═══════════


class AaGradeTask(PKMixin, TenantMixin, CommonMixin, Base):
    """成绩录入任务（对应教学任务/教学班）。平时+期末按比例合成。DRAFT/ENTERING/SUBMITTED/PUBLISHED。"""
    __tablename__ = "t_aa_grade_task"

    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    term_code: Mapped[str | None] = mapped_column(String(50))
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100))
    credit: Mapped[float | None] = mapped_column(Numeric(4, 1))
    usual_ratio: Mapped[int] = mapped_column(Integer, nullable=False, default=30, comment="平时占比%")
    final_ratio: Mapped[int] = mapped_column(Integer, nullable=False, default=70, comment="期末占比%")
    pass_line: Mapped[int] = mapped_column(Integer, nullable=False, default=60, comment="及格线")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    academic_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    academic_reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger)


class AaGradeRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """成绩明细（每生：平时分+期末分→合成总评）。发布时投影 t_acad_grade。"""
    __tablename__ = "t_aa_grade_record"

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    usual_score: Mapped[int | None] = mapped_column(Integer, comment="平时分")
    final_score: Mapped[int | None] = mapped_column(Integer, comment="期末分")
    total_score: Mapped[int | None] = mapped_column(Integer, comment="总评(合成)")
    pass_status: Mapped[str | None] = mapped_column(String(50), comment="PASSED/FAILED")
    acad_grade_id: Mapped[int | None] = mapped_column(BigInteger, comment="投影 t_acad_grade 回链")
    source: Mapped[str | None] = mapped_column(String(20), default="LEGACY", comment="LEGACY/PUBLISH/CHANGE/MANUAL")
    prev_usual_score: Mapped[int | None] = mapped_column(Integer)
    prev_final_score: Mapped[int | None] = mapped_column(Integer)
    prev_total_score: Mapped[int | None] = mapped_column(Integer)
    change_reason: Mapped[str | None] = mapped_column(String(500))
    change_by: Mapped[int | None] = mapped_column(BigInteger)
    change_at: Mapped[datetime | None] = mapped_column(DateTime)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    exception_flag: Mapped[str | None] = mapped_column(String(20), default="NORMAL",
                                                        comment="NORMAL/ABSENT/DEFERRED/EXEMPT")


# ═══════════ 毕业资格预审组（13B-P6；七项跨域供数三态判定）═══════════


class AaGraduationAuditBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """毕业预审批次（圈定应届生→生成→预审）。DRAFT/GENERATED/PRECHECKED/REVIEWING/ARCHIVED。"""
    __tablename__ = "t_aa_graduation_audit_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    grade_year: Mapped[str | None] = mapped_column(String(20), index=True, comment="毕业年级")
    major_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    scope_json: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    generate_at: Mapped[datetime | None] = mapped_column(DateTime)


class AaGraduationAuditResult(PKMixin, TenantMixin, CommonMixin, Base):
    """逐生预审结果（七项三态判定 item_results_json 收敛）。终审经 change_student_status 写主档。唯一(tenant,batch,student)。"""
    __tablename__ = "t_aa_graduation_audit_result"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_results_json: Mapped[str | None] = mapped_column(String(4000),
                                                          comment="七项：每项 PASS/FAIL/UNKNOWN + 证据引用")
    overall: Mapped[str | None] = mapped_column(String(50), comment="SYSTEM_PASSED/SYSTEM_ABNORMAL")
    conclusion: Mapped[str | None] = mapped_column(String(50), comment="GRADUATED/COMPLETED/DELAYED")
    rerun_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="WAIT_PRECHECK", index=True,
                                        comment="WAIT_PRECHECK/SYSTEM_PASSED/SYSTEM_ABNORMAL/COLLEGE_REVIEW/ACADEMIC_REVIEW/GRADUATED/COMPLETED/DELAYED/REJECTED/ARCHIVED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id", name="uk_aa_grad_audit"),)


# ═══════════ 教学资源组（13B-R4；教室字典最小闭环，方案A：字典独立，课表 classroom_text 保持自由文本快照）═══════════


class AaClassroom(PKMixin, TenantMixin, CommonMixin, Base):
    """教室字典（楼栋/教室/容量/类型/可用状态）。租户级基础数据；排课 UI 从本字典选择，
    课表 t_aa_schedule_item.classroom_text 保持自由文本快照不改列（方案A，classroom_id 外键化留 backlog）。
    唯一(tenant,building_code,room_code)。可用状态 AVAILABLE/DISABLED/MAINTENANCE。"""
    __tablename__ = "t_aa_classroom"

    building_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="楼栋编码")
    building_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="楼栋名称")
    room_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="教室编号")
    room_name: Mapped[str | None] = mapped_column(String(100), comment="教室名称(可空,默认楼栋+编号)")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="容量(座位数)")
    room_type: Mapped[str] = mapped_column(String(30), nullable=False, default="LECTURE",
                                           comment="LECTURE/MULTIMEDIA/COMPUTER/LAB/OTHER 普通/多媒体/机房/实验室/其他")
    campus_code: Mapped[str | None] = mapped_column(String(50), comment="预留多校区")
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AVAILABLE", index=True,
                                        comment="AVAILABLE/DISABLED/MAINTENANCE 可用/停用/维修中")

    __table_args__ = (UniqueConstraint("tenant_id", "building_code", "room_code", name="uk_aa_classroom"),)


class AaClassroomBooking(PKMixin, TenantMixin, CommonMixin, Base):
    """教室预约（占用登记）。同教室同日同节次已 APPROVED 冲突 → 409。PENDING/APPROVED/REJECTED/CANCELLED。"""
    __tablename__ = "t_aa_classroom_booking"

    classroom_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    classroom_text: Mapped[str | None] = mapped_column(String(100))
    booking_date: Mapped[str] = mapped_column(String(20), nullable=False, comment="YYYY-MM-DD")
    slot_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="节次")
    purpose: Mapped[str | None] = mapped_column(String(300), comment="用途")
    applicant_key: Mapped[str | None] = mapped_column(String(100), index=True)
    applicant_name: Mapped[str | None] = mapped_column(String(100))
    review_reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/APPROVED/REJECTED/CANCELLED")


# ═══════════ 调停课组（13B-R2/SM-08；调课/停课/补课，审批通过后改写课表保留原课位历史）═══════════


class AaScheduleChange(PKMixin, TenantMixin, CommonMixin, Base):
    """调停课单（SM-08，workflow_code=ACAD_SCHEDULE_CHANGE）。

    change_type=ADJUST(调课)/STOP(停课)/MAKEUP(补课)。教师就已发布课表项(origin_item)发起，
    提交即做目标课位三重冲突预检(复用 schedule_service._detect_conflict)，冲突则不落库。
    审批链：学院审→教务处审。终审通过后系统改写课表：原课位标 CHANGED(保留历史，禁直接 UPDATE 已发布项)，
    调课/补课生成新课表项并回链本单(new_item_id / schedule_item.change_id)。
    7 态：SUBMITTED / COLLEGE_REVIEW / ACADEMIC_REVIEW / APPROVED / REJECTED / CANCELLED / APPLIED。
    """
    __tablename__ = "t_aa_schedule_change"

    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="原课位所属已发布课表批次")
    origin_item_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_schedule_item 原课位")
    task_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_aa_teaching_task")
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
                                             comment="ADJUST 调课 / STOP 停课 / MAKEUP 补课")
    # 原课位快照（发起时冻结，独立于 origin_item 后续状态）
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_name: Mapped[str | None] = mapped_column(String(100))
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    origin_weekday: Mapped[int | None] = mapped_column(Integer)
    origin_slot_no: Mapped[int | None] = mapped_column(Integer)
    origin_start_week: Mapped[int | None] = mapped_column(Integer)
    origin_end_week: Mapped[int | None] = mapped_column(Integer)
    origin_week_parity: Mapped[str | None] = mapped_column(String(10))
    origin_classroom: Mapped[str | None] = mapped_column(String(100))
    # 目标课位（调课/补课填写；停课留空）
    target_weekday: Mapped[int | None] = mapped_column(Integer)
    target_slot_no: Mapped[int | None] = mapped_column(Integer)
    target_start_week: Mapped[int | None] = mapped_column(Integer)
    target_end_week: Mapped[int | None] = mapped_column(Integer)
    target_week_parity: Mapped[str | None] = mapped_column(String(10))
    target_classroom: Mapped[str | None] = mapped_column(String(100))
    makeup_plan: Mapped[str | None] = mapped_column(String(500), comment="补课/停课后续安排说明")
    reason: Mapped[str | None] = mapped_column(String(500), comment="调停课原因(≥5 字)")
    new_item_id: Mapped[int | None] = mapped_column(BigInteger, comment="终审生效后生成的新课表项(回链)")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, comment="课表改写生效时间")
    applicant_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="发起教师 user_id")
    current_node: Mapped[str | None] = mapped_column(String(50), comment="审批当前节点")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/COLLEGE_REVIEW/ACADEMIC_REVIEW/APPROVED/REJECTED/CANCELLED/APPLIED")


# ═══════════ 选课管理组（13B-SM-09；批次6态 + 课程供给 + 学生选课记录4态，容量行锁扣减）═══════════


class AaSelectionBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """选课批次头（SM-09 冻结，6 态 DRAFT/PUBLISHED/OPEN/CLOSED/LOCKED/ARCHIVED）。
    时间窗到达由定时任务迁移 PUBLISHED→OPEN→CLOSED；教务处发布/锁定/归档。
    apply_scope_json 存适用范围(年级/专业/班级白名单)，rule_json 存选课规则(最大学分等)。"""
    __tablename__ = "t_aa_selection_batch"

    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_term")
    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    select_start_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开选时间")
    select_end_at: Mapped[datetime | None] = mapped_column(DateTime, comment="截止时间")
    apply_scope_json: Mapped[str | None] = mapped_column(String(2000),
                                                         comment="适用范围JSON {grades:[],majorIds:[],classIds:[]}；空=全校")
    rule_json: Mapped[str | None] = mapped_column(String(2000),
                                                  comment="选课规则JSON {maxCredits:int,allowRetake:bool,...}")
    remark: Mapped[str | None] = mapped_column(String(500))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/PUBLISHED/OPEN/CLOSED/LOCKED/ARCHIVED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_name", "term_id", name="uk_aa_selection_batch"),)


class AaSelectionCourse(PKMixin, TenantMixin, CommonMixin, Base):
    """批次内课程供给项（ai_proposal 承载容量/限选/取消状态）。selected_count 行锁原子扣减防超卖。
    status OPEN/COURSE_CANCELLED（人数不足人工取消）。"""
    __tablename__ = "t_aa_selection_course"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="→ t_aa_course")
    course_name: Mapped[str | None] = mapped_column(String(200), comment="课程名快照")
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_aa_teaching_task(可空)")
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True, comment="任课教师键(名单授课关系校验)")
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    credit: Mapped[float | None] = mapped_column(Numeric(4, 1), comment="学分")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="容量上限")
    min_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="开课人数下限")
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已选人数(行锁扣减)")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True,
                                        comment="OPEN/COURSE_CANCELLED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "course_id", "teaching_task_id",
                                       name="uk_aa_selection_course"),)


class AaSelectionRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """学生选课记录（SM-09 冻结，4 态 SELECTED/DROPPED/COURSE_CANCELLED/LOCKED）。
    退课/复选复用同一行(D-09)；(tenant,batch,selection_course,student) 唯一。学生/课程快照冻结。"""
    __tablename__ = "t_aa_selection_record"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    selection_course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    credit: Mapped[float | None] = mapped_column(Numeric(4, 1))
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="→ t_student_profile")
    student_no: Mapped[str | None] = mapped_column(String(50), comment="学号快照")
    student_name: Mapped[str | None] = mapped_column(String(100), comment="姓名快照")
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime, comment="选课时间")
    dropped_at: Mapped[datetime | None] = mapped_column(DateTime, comment="退课时间")
    adjust_reason: Mapped[str | None] = mapped_column(String(500), comment="LOCKED后教务处人工调整原因")
    re_enroll: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否复选")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SELECTED", index=True,
                                        comment="SELECTED/DROPPED/COURSE_CANCELLED/LOCKED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "selection_course_id", "student_id",
                                       name="uk_aa_selection_record"),)


# ═══════════ 考务管理组（13B-SM-10；批次6态+课程3态+考场/座位/监考/巡考/异常+缓考8态四级审批）═══════════


class AaExamBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """考试批次（SM-10，6 态 DRAFT/COURSE_CONFIRMED/ARRANGED/PUBLISHED/FINISHED/ARCHIVED）。"""
    __tablename__ = "t_aa_exam_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False, default="FINAL", comment="FINAL 期末（V1 仅此）")
    college_scope_json: Mapped[str | None] = mapped_column(String(2000), comment="参与学院范围 {collegeIds:[]}")
    exam_week_start: Mapped[int | None] = mapped_column(Integer)
    exam_week_end: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/COURSE_CONFIRMED/ARRANGED/PUBLISHED/FINISHED/ARCHIVED")


class AaExamCourse(PKMixin, TenantMixin, CommonMixin, Base):
    """批次内考试课程（3 态 PENDING_CONFIRM/CONFIRMED/REMOVED）。college_id 冗余供范围过滤。"""
    __tablename__ = "t_aa_exam_course"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_name: Mapped[str | None] = mapped_column(String(100))
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="冗余，学院范围过滤")
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    expected_students: Mapped[int | None] = mapped_column(Integer)
    exam_date: Mapped[str | None] = mapped_column(String(20), comment="YYYY-MM-DD")
    start_time: Mapped[str | None] = mapped_column(String(10), comment="HH:MM")
    end_time: Mapped[str | None] = mapped_column(String(10))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_CONFIRM", index=True,
                                        comment="PENDING_CONFIRM/CONFIRMED/REMOVED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "teaching_task_id", name="uk_aa_exam_course"),)


class AaExamRoom(PKMixin, TenantMixin, CommonMixin, Base):
    """考场（classroom_id P2 可空 + classroom_text V1 兜底）。seat_mode SEQUENTIAL/RANDOM。"""
    __tablename__ = "t_aa_exam_room"

    exam_course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    room_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="考场序号")
    classroom_id: Mapped[int | None] = mapped_column(BigInteger)
    classroom_text: Mapped[str | None] = mapped_column(String(100), comment="考场文本(V1)")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seat_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="SEQUENTIAL",
                                           comment="SEQUENTIAL 按学号 / RANDOM 随机")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="ACTIVE/VOIDED")

    __table_args__ = (UniqueConstraint("tenant_id", "exam_course_id", "room_seq", name="uk_aa_exam_room"),)


class AaExamRoomStudent(PKMixin, TenantMixin, CommonMixin, Base):
    """座位明细。attendance_status NOT_STARTED/PRESENT/ABSENT/DISCIPLINE_VIOLATION。"""
    __tablename__ = "t_aa_exam_room_student"

    exam_room_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exam_course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_no: Mapped[str | None] = mapped_column(String(50))
    student_name: Mapped[str | None] = mapped_column(String(100))
    seat_no: Mapped[int | None] = mapped_column(Integer)
    admission_no: Mapped[str | None] = mapped_column(String(50), comment="准考证号")
    attendance_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_STARTED",
                                                   comment="NOT_STARTED/PRESENT/ABSENT/DISCIPLINE_VIOLATION")

    __table_args__ = (
        UniqueConstraint("tenant_id", "exam_room_id", "seat_no", name="uk_aa_exam_seat"),
        UniqueConstraint("tenant_id", "exam_course_id", "student_id", name="uk_aa_exam_course_student"),
    )


class AaExamInvigilator(PKMixin, TenantMixin, CommonMixin, Base):
    """监考安排。role CHIEF/ASSISTANT，confirm_status ASSIGNED/CONFIRMED。同教师同时段冲突检测。"""
    __tablename__ = "t_aa_exam_invigilator"

    exam_room_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSISTANT", comment="CHIEF/ASSISTANT")
    confirm_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSIGNED",
                                                comment="ASSIGNED/CONFIRMED")

    __table_args__ = (UniqueConstraint("tenant_id", "exam_room_id", "teacher_key", name="uk_aa_exam_invig"),)


class AaExamPatrol(PKMixin, TenantMixin, CommonMixin, Base):
    """巡考安排。同教师同时段冲突检测。"""
    __tablename__ = "t_aa_exam_patrol"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    patrol_date: Mapped[str | None] = mapped_column(String(20))
    start_time: Mapped[str | None] = mapped_column(String(10))
    end_time: Mapped[str | None] = mapped_column(String(10))
    area_scope_json: Mapped[str | None] = mapped_column(String(1000), comment="巡查范围")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSIGNED")


class AaExamIncident(PKMixin, TenantMixin, CommonMixin, Base):
    """考场异常（缺考/违纪）。缺考触发风险通知；违纪留处分线索引用位。status ACTIVE/VOIDED。"""
    __tablename__ = "t_aa_exam_incident"

    exam_room_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    exam_course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_no: Mapped[str | None] = mapped_column(String(50))
    student_name: Mapped[str | None] = mapped_column(String(100))
    incident_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True,
                                               comment="ABSENT/DISCIPLINE_VIOLATION/OTHER")
    description: Mapped[str | None] = mapped_column(String(1000), comment="违纪描述(敏感)")
    evidence_file_ids: Mapped[str | None] = mapped_column(String(1000), comment="证据附件JSON")
    recorded_by: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime)
    risk_alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discipline_case_ref: Mapped[str | None] = mapped_column(String(100), comment="处分线索引用位(供学工消费)")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="ACTIVE/VOIDED")

    __table_args__ = (UniqueConstraint("tenant_id", "exam_course_id", "student_id", "incident_type",
                                       name="uk_aa_exam_incident"),)


class AaDeferredExam(PKMixin, TenantMixin, CommonMixin, Base):
    """缓考（8 态四级审批 辅导员→任课教师→学院→教务处）。reason 脱敏，材料需授权。"""
    __tablename__ = "t_aa_deferred_exam"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_no: Mapped[str | None] = mapped_column(String(50))
    student_name: Mapped[str | None] = mapped_column(String(100))
    exam_course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_name: Mapped[str | None] = mapped_column(String(200))
    reason_type: Mapped[str | None] = mapped_column(String(50), comment="SICK/EMERGENCY/OTHER")
    reason: Mapped[str | None] = mapped_column(String(500), comment="原因(敏感脱敏)")
    material_file_ids: Mapped[str | None] = mapped_column(String(1000), comment="材料附件JSON")
    apply_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_node: Mapped[str | None] = mapped_column(String(50))
    return_reason: Mapped[str | None] = mapped_column(String(500))
    next_batch_ref: Mapped[str | None] = mapped_column(String(100), comment="进入下一批次引用位(R6)")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/COUNSELOR_REVIEW/TEACHER_CONFIRM/COLLEGE_REVIEW/ACADEMIC_FINAL/APPROVED/RETURNED/REJECTED")


class AaExamAuditTrail(PKMixin, TenantMixin, Base):
    """考务域级 append-only 审计（模块自有，D-10；待 t_aa_audit_trail 落地后总控收编）。"""
    __tablename__ = "t_aa_exam_audit_trail"

    biz_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    biz_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(1000))
    after_val: Mapped[str | None] = mapped_column(String(1000))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


# ═══════════ 补考重修缓考免修组（13B-SM-12；补考批次5态 / 重修申请6态单节点 / 免修申请7态三级审批）═══════════


class AaMakeupBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """补考批次（SM-12.1，5 态 DRAFT/ARRANGED/PUBLISHED/SCORING/FINISHED）。
    关联考务批次编排考试；FINISHED 按计分规则回写 t_acad_grade(source=MAKEUP)/t_acad_makeup。"""
    __tablename__ = "t_aa_makeup_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    term_code: Mapped[str | None] = mapped_column(String(50))
    exam_batch_ref: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_aa_exam_batch 关联考务批次")
    score_rule: Mapped[str] = mapped_column(String(20), nullable=False, default="CAP60",
                                            comment="计分规则 CAP60 及格封顶60")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/ARRANGED/PUBLISHED/SCORING/FINISHED")


class AaRetakeApply(PKMixin, TenantMixin, CommonMixin, Base):
    """重修申请（SM-12.2，6 态，workflow_code=ACAD_RETAKE_APPLY，教务处单节点审批）。
    次数上限读规则 academicAffairs.retake.maxCount(默2)；APPROVED 后编入教学任务跟班重修。"""
    __tablename__ = "t_aa_retake_apply"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_no: Mapped[str | None] = mapped_column(String(50))
    student_name: Mapped[str | None] = mapped_column(String(100))
    acad_student_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_acad_student")
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    term_code: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    retake_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="第几次重修")
    review_reason: Mapped[str | None] = mapped_column(String(500), comment="审批意见/驳回原因")
    teaching_task_ref: Mapped[int | None] = mapped_column(BigInteger, comment="编入的教学任务(跟班)")
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/ACADEMIC_REVIEW/APPROVED/REJECTED/ENROLLED/FINISHED")


class AaExemption(PKMixin, TenantMixin, CommonMixin, Base):
    """免修申请（SM-12.3，7 态，workflow_code=ACAD_COURSE_EXEMPT，三级审批 任课教师→学院→教务处）。
    已获成绩课程申请 422；每学期免修上限 academicAffairs.exemption.maxCount(默2)。"""
    __tablename__ = "t_aa_exemption"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_no: Mapped[str | None] = mapped_column(String(50))
    student_name: Mapped[str | None] = mapped_column(String(100))
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    term_code: Mapped[str | None] = mapped_column(String(50))
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True, comment="任课教师(初审节点)")
    reason: Mapped[str | None] = mapped_column(String(500))
    material_file_ids: Mapped[str | None] = mapped_column(String(1000), comment="证书/先修证明材料JSON")
    current_node: Mapped[str | None] = mapped_column(String(50))
    return_reason: Mapped[str | None] = mapped_column(String(500))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/TEACHER_REVIEW/COLLEGE_REVIEW/ACADEMIC_REVIEW/APPROVED/REJECTED/CANCELLED")


# ═══════════ 教材管理组（13B；目录/选用/审核/征订/发放/费用，挂教学任务）═══════════


class AaTextbook(PKMixin, TenantMixin, CommonMixin, Base):
    """教材目录字典。唯一(tenant,isbn)（isbn 非空时）。DRAFT/ENABLED/DISABLED。"""
    __tablename__ = "t_aa_textbook"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(30), index=True)
    publisher: Mapped[str | None] = mapped_column(String(200))
    edition: Mapped[str | None] = mapped_column(String(50))
    author: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(100))
    unit_price: Mapped[float | None] = mapped_column(Numeric(8, 2), comment="定价")
    is_national_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否国家统编")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ENABLED", index=True,
                                        comment="DRAFT/ENABLED/DISABLED")


class AaTextbookSelection(PKMixin, TenantMixin, CommonMixin, Base):
    """教材选用（挂教学任务）。DRAFT/SUBMITTED/REVIEWING/APPROVED/RETURNED/ORDERED。"""
    __tablename__ = "t_aa_textbook_selection"

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="→ t_aa_teaching_task")
    textbook_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_name: Mapped[str | None] = mapped_column(String(300))
    course_name: Mapped[str | None] = mapped_column(String(200))
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    officer_teacher_id: Mapped[int | None] = mapped_column(BigInteger, comment="教材负责人")
    officer_key: Mapped[str | None] = mapped_column(String(100), index=True)
    expected_qty: Mapped[int | None] = mapped_column(Integer, comment="预计数量")
    remark: Mapped[str | None] = mapped_column(String(500))
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/SUBMITTED/REVIEWING/APPROVED/RETURNED/ORDERED")


class AaTextbookReviewBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """教材审核批次。DRAFT/COLLEGE_REVIEWING/COLLEGE_APPROVED/ACADEMIC_APPROVED/PUBLISHED/RETURNED。"""
    __tablename__ = "t_aa_textbook_review_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    publicity_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    publicity_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_reviewer: Mapped[str | None] = mapped_column(String(100))
    academic_reviewer: Mapped[str | None] = mapped_column(String(100))
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/COLLEGE_REVIEWING/COLLEGE_APPROVED/ACADEMIC_APPROVED/PUBLISHED/RETURNED")


class AaTextbookReviewBatchItem(PKMixin, TenantMixin, CommonMixin, Base):
    """审核批次-选用关联。唯一(tenant,batch,selection)。"""
    __tablename__ = "t_aa_textbook_review_batch_item"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    selection_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "selection_id", name="uk_aa_tb_review_item"),)


class AaTextbookOrderBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """教材征订批次。DRAFT/ORDERED/PARTIALLY_ARRIVED/ARRIVED/ARCHIVED。"""
    __tablename__ = "t_aa_textbook_order_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    college_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/ORDERED/PARTIALLY_ARRIVED/ARRIVED/ARCHIVED")


class AaTextbookOrderItem(PKMixin, TenantMixin, CommonMixin, Base):
    """征订明细（同教材合并）。唯一(tenant,order_batch,textbook)。"""
    __tablename__ = "t_aa_textbook_order_item"

    order_batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_name: Mapped[str | None] = mapped_column(String(300))
    order_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    arrived_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price_snapshot: Mapped[float | None] = mapped_column(Numeric(8, 2))

    __table_args__ = (UniqueConstraint("tenant_id", "order_batch_id", "textbook_id", name="uk_aa_tb_order_item"),)


class AaTextbookDistributionBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """发放批次。DRAFT/DISTRIBUTING/COMPLETED。唯一(tenant,order_batch,class)。"""
    __tablename__ = "t_aa_textbook_distribution_batch"

    order_batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    class_name: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/DISTRIBUTING/COMPLETED")

    __table_args__ = (UniqueConstraint("tenant_id", "order_batch_id", "class_id", name="uk_aa_tb_dist_batch"),)


class AaTextbookDistributionRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """发放明细（只带 student_id 外键，不冗余隐私）。PENDING/RECEIVED/EXCLUDED/EXCHANGED。"""
    __tablename__ = "t_aa_textbook_distribution_record"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_name: Mapped[str | None] = mapped_column(String(300))
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_by: Mapped[str | None] = mapped_column(String(100))
    exclude_reason: Mapped[str | None] = mapped_column(String(500))
    exchange_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/RECEIVED/EXCLUDED/EXCHANGED")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "student_id", "textbook_id", name="uk_aa_tb_dist_record"),)


class AaTextbookFeeLedger(PKMixin, TenantMixin, CommonMixin, Base):
    """教材费用台账（签收后自动生成应收）。UNPAID/PARTIAL/PAID/WAIVED。唯一(tenant,distribution_record)。"""
    __tablename__ = "t_aa_textbook_fee_ledger"

    distribution_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    textbook_name: Mapped[str | None] = mapped_column(String(300))
    amount: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0, comment="已收金额(部分收款)")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    waive_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNPAID", index=True,
                                        comment="UNPAID/PARTIAL/PAID/WAIVED")

    __table_args__ = (UniqueConstraint("tenant_id", "distribution_record_id", name="uk_aa_tb_fee"),)


# ═══════════ 排课管理组（13B-SM-07；排课规则中心 + 教师可用时间 + 全量冲突报告，复用既有课表批次/条目/冲突检测）═══════════


class AaScheduleRule(PKMixin, TenantMixin, CommonMixin, Base):
    """排课规则中心（教师可用时间要求/教室类型要求/周学时分布等约束）。挂学期或批次。"""
    __tablename__ = "t_aa_schedule_rule"

    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_aa_schedule_batch(可空,学期级规则)")
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True,
                                          comment="规则键 如 maxDailySlots/avoidEvening/roomTypeRequired")
    rule_value_json: Mapped[str | None] = mapped_column(String(2000), comment="规则值JSON")
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ENABLED", index=True,
                                        comment="ENABLED/DISABLED")

    __table_args__ = (UniqueConstraint("tenant_id", "term_id", "batch_id", "rule_key", name="uk_aa_sched_rule"),)


class AaTeacherAvailability(PKMixin, TenantMixin, CommonMixin, Base):
    """教师可用时间（不可排课时段采集）。教师提交 → 学院采纳/驳回。PENDING/ADOPTED/REJECTED。"""
    __tablename__ = "t_aa_teacher_availability"

    teacher_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, comment="星期 1-7")
    slot_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="节次")
    reason: Mapped[str | None] = mapped_column(String(300), comment="不可排课原因")
    review_reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/ADOPTED/REJECTED")

    __table_args__ = (UniqueConstraint("tenant_id", "teacher_key", "term_id", "weekday", "slot_no",
                                       name="uk_aa_teacher_avail"),)


# ═══════════ 教学评价组（13B；评教批次6态 + 4类评价 + 结果均分分级 + 申诉两级；学生评教匿名不存身份）═══════════


class AaEvaluationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """评教批次（6 态 DRAFT/PUBLISHED/OPEN/CLOSED/RESULT_READY/ARCHIVED）。含问卷模板 JSON + 匿名开关 + 窗口。"""
    __tablename__ = "t_aa_evaluation_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    scope_json: Mapped[str | None] = mapped_column(String(2000), comment="应评范围 {collegeIds,majorIds,courseIds}")
    template_json: Mapped[str | None] = mapped_column(String(4000), comment="问卷题目JSON(客观5级量表+主观)")
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="学生评教是否匿名")
    window_start: Mapped[datetime | None] = mapped_column(DateTime)
    window_end: Mapped[datetime | None] = mapped_column(DateTime)
    result_published_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/PUBLISHED/OPEN/CLOSED/RESULT_READY/ARCHIVED")


class AaEvaluationTask(PKMixin, TenantMixin, CommonMixin, Base):
    """应评任务（挂教学任务，按评价类型）。evaluator_type STUDENT/SELF/PEER/SUPERVISOR。PENDING/SUBMITTED。"""
    __tablename__ = "t_aa_evaluation_task"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_name: Mapped[str | None] = mapped_column(String(200))
    class_id: Mapped[int | None] = mapped_column(BigInteger)
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True, comment="被评教师")
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    evaluator_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STUDENT", index=True,
                                                comment="STUDENT/SELF/PEER/SUPERVISOR")
    evaluator_key: Mapped[str | None] = mapped_column(String(100), index=True,
                                                      comment="评价人(SELF/PEER/SUPERVISOR记;STUDENT匿名不记具体学生)")
    submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="学生类:已提交人数")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True,
                                        comment="PENDING/SUBMITTED")


class AaEvaluationRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """评价记录。学生评教匿名：不存 evaluator_id，仅存答卷与得分（D-04 架构级匿名）。"""
    __tablename__ = "t_aa_evaluation_record"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    evaluator_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STUDENT")
    answers_json: Mapped[str | None] = mapped_column(String(4000), comment="答卷JSON")
    objective_score: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="客观题均分")
    comment: Mapped[str | None] = mapped_column(String(1000), comment="主观评语")


class AaEvaluationResult(PKMixin, TenantMixin, CommonMixin, Base):
    """评价结果（教师×课程维度）。仅按学生评教均分分级 EXCELLENT/GOOD/PASS/NEED_IMPROVE（D-06 不加权）。"""
    __tablename__ = "t_aa_evaluation_result"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teaching_task_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    course_name: Mapped[str | None] = mapped_column(String(200))
    student_avg: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="学生评教均分")
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[str | None] = mapped_column(String(20), index=True,
                                              comment="EXCELLENT/GOOD/PASS/NEED_IMPROVE")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已对教师发布")

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "teaching_task_id", name="uk_aa_eval_result"),)


class AaEvaluationAppeal(PKMixin, TenantMixin, CommonMixin, Base):
    """评价申诉（教师对本人结果，两级 学院初审→教务终审）。SUBMITTED/COLLEGE_REVIEW/RESOLVED/REJECTED。"""
    __tablename__ = "t_aa_evaluation_appeal"

    result_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True)
    reason: Mapped[str | None] = mapped_column(String(1000))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    current_node: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True,
                                        comment="SUBMITTED/COLLEGE_REVIEW/RESOLVED/REJECTED")


# ═══════════ 教务归档组（13B-R7；按学年学期归档批次 + 9数据域物料 + 完整性检查 + 学期封存）═══════════


class AaArchiveBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """教务归档批次（一学期一批次，D-01）。DRAFT/CHECKING/READY/MISSING_ITEMS/ARCHIVED/CANCELLED。
    确认归档后学期 status→ARCHIVED（D-04，该学期写端点应 409，横切拦截见欠账）。"""
    __tablename__ = "t_aa_archive_batch"

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    term_code: Mapped[str | None] = mapped_column(String(50))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, comment="完整性检查时间")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="缺失数据域数")
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/CHECKING/READY/MISSING_ITEMS/ARCHIVED/CANCELLED")

    __table_args__ = (UniqueConstraint("tenant_id", "term_id", name="uk_aa_archive_batch"),)


class AaArchiveItem(PKMixin, TenantMixin, CommonMixin, Base):
    """归档物料（9 数据域：学籍/注册/异动/培养方案/教学任务/课表/考务/成绩/毕业资格）。
    domain 域码；record_count 该域记录数；present 是否有数据。"""
    __tablename__ = "t_aa_archive_item"

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                        comment="STUDENT_STATUS/REGISTRATION/STATUS_CHANGE/PROGRAM/TEACHING_TASK/SCHEDULE/EXAM/GRADE/GRADUATION")
    domain_label: Mapped[str | None] = mapped_column(String(100))
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", "domain", name="uk_aa_archive_item"),)


# ═══════════ 课堂考勤（13B-P8·移动端首创；教师按行政班/课程逐次考勤，DRAFT→SUBMITTED）═══════════


class AaAttendanceSession(PKMixin, TenantMixin, CommonMixin, Base):
    """课堂考勤场次（V1：教师按行政班圈定名单逐生标记，提交后不可再改，走教务处人工更正线下流程）。"""
    __tablename__ = "t_aa_attendance_session"

    class_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="行政班")
    course_name: Mapped[str | None] = mapped_column(String(200))
    term_code: Mapped[str | None] = mapped_column(String(50))
    teacher_key: Mapped[str | None] = mapped_column(String(100), index=True, comment="任课教师归属")
    session_date: Mapped[str] = mapped_column(String(20), nullable=False, comment="YYYY-MM-DD")
    slot_no: Mapped[int | None] = mapped_column(Integer, comment="第几节")
    roster_json: Mapped[str | None] = mapped_column(Text, comment="[{studentId,studentNo,realName,status}]")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    absent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/SUBMITTED")


# ═══════════ 学院专业班级 Tier1 R2（06 专业方向 / 08 班级调整申请单）═══════════


class AaMajorDirection(PKMixin, TenantMixin, CommonMixin, Base):
    """专业方向（t_aa_major_direction，13B-学院专业班级 06 号卡）：专业下的方向细分主数据。
    受总开关控制（默认关闭，见 academic_affairs_org_service._major_direction_enabled），
    未启用时全部端点 400 FEATURE_DISABLED；启用与否是学校业务政策待确认项，非技术缺口。"""
    __tablename__ = "t_aa_major_direction"
    __table_args__ = (UniqueConstraint("tenant_id", "major_id", "code", name="uk_aa_major_direction_code"),)

    major_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    direction_name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True,
                                        comment="ACTIVE/DISABLED")


class AaClassAdjustmentRequest(PKMixin, TenantMixin, CommonMixin, Base):
    """班级调整申请单（t_aa_class_adjustment_request，13B-学院专业班级 08 号卡）：
    行政班层面的组织性批量调整（合班登记/拆班登记/停用撤销/毕业清班），DRAFT→CHECKED→EXECUTED/CANCELLED。
    区别于既有 /orgs/class-adjustments（org_service.adjust_student_class）——那是既有的单个学生转班
    轻量端点（写 t_student_profile.class_id）；本表是组织级批量调整申请单，不改写学生 class_id，
    真实学籍仍在原行政班，避免破坏"单一写入口"约束（见融合设计 §1.2 change_student_status）。"""
    __tablename__ = "t_aa_class_adjustment_request"

    adjust_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
                                              comment="MERGE/SPLIT/DISBAND/GRADUATE_CLEAR")
    from_class_ids: Mapped[str] = mapped_column(String(500), nullable=False, comment="JSON数组，来源行政班id列表")
    to_class_id: Mapped[int | None] = mapped_column(BigInteger, comment="合班目标班级（MERGE专用）")
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    check_result_json: Mapped[str | None] = mapped_column(String(2000))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/CHECKED/EXECUTED/CANCELLED")

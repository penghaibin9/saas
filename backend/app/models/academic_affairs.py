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
    change_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
                                                  comment="→ t_aa_schedule_change 生成本项的调停课单(变更标记/回链)；null=原始排课")


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

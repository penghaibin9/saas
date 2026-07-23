"""毕业设计域模型（P7-GRADUATION）。t_gd_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


def _audit_trace_id() -> str | None:
    from app.core.context import get_trace_id
    value = get_trace_id()
    return value if value and value != "-" else None


def _audit_request_path() -> str | None:
    from app.core.context import get_request_meta
    return get_request_meta().get("path")


def _audit_client_ip() -> str | None:
    from app.core.context import get_request_meta
    return get_request_meta().get("ip")


class GraduationBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_batch 毕设批次（一届/一轮毕业设计的组织与规则容器）。状态机 DRAFT→RUNNING→CLOSED→ARCHIVED。"""
    __tablename__ = "t_gd_batch"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_no", name="uk_gd_batch_no"),)

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year: Mapped[str | None] = mapped_column(String(20), comment="学年 如 2025-2026")
    grade_year: Mapped[str | None] = mapped_column(String(20), comment="届 如 2026届")
    college_scope: Mapped[str | None] = mapped_column(String(200), comment="适用学院/专业范围")
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="计划毕设人数")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/RUNNING/CLOSED/ARCHIVED/VOIDED")
    stage_config: Mapped[list | None] = mapped_column(JSON, comment="阶段/时间轴 [{code,name,startDate,endDate}]")
    rules_config: Mapped[dict | None] = mapped_column(JSON, comment="规则 {plagiarism/review/defense/score}")
    previous_status: Mapped[str | None] = mapped_column(String(50))
    last_transition_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_transition_by: Mapped[str | None] = mapped_column(String(100))
    transition_reason: Mapped[str | None] = mapped_column(String(500))
    archive_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_ARCHIVED",
                                                comment="NOT_ARCHIVED/ARCHIVED")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    void_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_student"
    __table_args__ = (
        Index("ix_gd_student_tenant_stage_active", "tenant_id", "stage", "record_status", "is_deleted"),
    )
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="毕设批次 t_gd_batch.id")
    topic_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="选题 t_gd_topic.id")
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    college_id: Mapped[str | None] = mapped_column(String(50), index=True, comment="学院ID（组织范围 claim 对齐）")
    major_id: Mapped[str | None] = mapped_column(String(50), index=True, comment="专业ID（组织范围 claim 对齐）")
    topic_title: Mapped[str | None] = mapped_column(String(300))
    topic_source: Mapped[str | None] = mapped_column(String(100))
    advisor_name: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="TOPIC_SELECTING")
    material_summary: Mapped[str | None] = mapped_column(String(200))
    plagiarism_rate: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    midterm_conclusion: Mapped[str | None] = mapped_column(String(100))
    defense_group: Mapped[str | None] = mapped_column(String(100))
    defense_group_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="答辩组 t_gd_defense_group.id")
    eligibility_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                                    comment="PENDING/QUALIFIED/UNQUALIFIED")
    mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="毕设导师 t_gd_mentor.id")
    student_group: Mapped[str | None] = mapped_column(String(100), comment="过程分组/答辩预备组")
    grad_qual_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN",
                                                  comment="UNKNOWN/NONE/PASS/FAIL/PENDING")
    grad_qual_note: Mapped[str | None] = mapped_column(String(500))
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class GraduationTopic(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_topic"
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="毕设批次 t_gd_batch.id")
    topic_no: Mapped[str | None] = mapped_column(String(50), index=True, comment="题目编号")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), comment="来源展示文案，与 source_type 对应")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="TEACHER",
                                            comment="TEACHER/ENTERPRISE/STUDENT/ADMIN")
    advisor_name: Mapped[str | None] = mapped_column(String(100))
    college_id: Mapped[str | None] = mapped_column(String(50))
    major_id: Mapped[str | None] = mapped_column(String(50))
    major_name: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
    difficulty: Mapped[str | None] = mapped_column(String(30))
    enterprise_name: Mapped[str | None] = mapped_column(String(200))
    requirements: Mapped[str | None] = mapped_column(String(2000))
    outcome: Mapped[str | None] = mapped_column(String(2000))
    skills: Mapped[str | None] = mapped_column(String(500))
    attachments_json: Mapped[list | None] = mapped_column(JSON)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                               comment="DRAFT/PENDING_REVIEW/APPROVED/REJECTED")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_CONFIRM",
                                        comment="PENDING_CONFIRM/CONFIRMED/DISABLED/ARCHIVED")
    students_json: Mapped[list | None] = mapped_column(JSON)
    disabled_note: Mapped[str | None] = mapped_column(String(300))
    archive_reason: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationTopicRound(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_topic_round 选题轮次（志愿制互选）。"""
    __tablename__ = "t_gd_topic_round"

    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    round_name: Mapped[str] = mapped_column(String(100), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_choices: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/OPEN/CLOSED/MATCHED")
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    college_scope: Mapped[str | None] = mapped_column(String(200))
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationTopicChoice(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_topic_choice 学生选题志愿。"""
    __tablename__ = "t_gd_topic_choice"
    __table_args__ = (
        UniqueConstraint("tenant_id", "round_id", "gd_student_id", "choice_order",
                         name="uk_gd_topic_choice_order"),
        Index("ix_gd_choice_round_status", "tenant_id", "round_id", "status", "is_deleted"),
    )

    round_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    choice_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/MATCHED/UNMATCHED/CONFIRMED/REJECTED")


class GraduationTopicChangeRequest(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_topic_change_request 选题变更申请（获批题目已有学生后，换题须走本流程重新审核，
    对齐商业系统"课题信息变更"惯例：提交后锁定，教师/管理员审核通过才生效）。"""
    __tablename__ = "t_gd_topic_change_request"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    new_topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED/CANCELLED")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    requested_by: Mapped[str | None] = mapped_column(String(100))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationMentor(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_mentor 毕设导师库（导师资格认证 + 容量 + 方向 + 工作量）。
    状态机：DRAFT→PENDING_REVIEW→QUALIFIED/REJECTED；QUALIFIED→DISABLED→ARCHIVED。"""
    __tablename__ = "t_gd_mentor"
    __table_args__ = (UniqueConstraint("tenant_id", "teacher_no", name="uk_gd_mentor_teacher_no"),)

    teacher_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="教师工号")
    teacher_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mentor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="INTERNAL",
                                             comment="INTERNAL校内导师/ENTERPRISE企业导师/DUAL双导师")
    title: Mapped[str | None] = mapped_column(String(50), comment="职称")
    college_id: Mapped[str | None] = mapped_column(String(50))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    research_direction: Mapped[str | None] = mapped_column(String(300), comment="指导方向")
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=8, comment="最大指导人数")
    current_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前指导人数(冗余)")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    qualification_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW",
                                                       comment="PENDING_REVIEW/QUALIFIED/REJECTED/DISABLED/ARCHIVED")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    disabled_reason: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationMentorAssignment(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_mentor_assignment 导师分配记录（分配/调导师历史，学生当前导师见 t_gd_student.mentor_id）。
    状态：ACTIVE 当前生效 / CHANGED 已被调整（历史） / CANCELLED 已取消。"""
    __tablename__ = "t_gd_mentor_assignment"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mentor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    previous_mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    assign_source: Mapped[str] = mapped_column(String(30), nullable=False, default="MANUAL",
                                               comment="MANUAL人工/BATCH批量/CHANGE调整")
    assign_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE",
                                        comment="ACTIVE/CHANGED/CANCELLED")
    confirmed_by_mentor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    assigned_by: Mapped[str | None] = mapped_column(String(100))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationTaskBook(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_task_book 任务书（导师下达→学生确认→变更需重确认）。一生一条当前记录，历史版本存 history_json。
    状态机：PENDING_CONFIRM→CONFIRMED→CHANGE_PENDING→CONFIRMED。"""
    __tablename__ = "t_gd_task_book"
    __table_args__ = (UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_task_book_student"),)

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    objective: Mapped[str | None] = mapped_column(String(2000), comment="任务目标")
    content: Mapped[str | None] = mapped_column(String(2000), comment="任务内容")
    progress_plan: Mapped[str | None] = mapped_column(String(2000), comment="进度计划")
    outcome_requirement: Mapped[str | None] = mapped_column(String(2000), comment="成果要求")
    taskbook_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="任务书业务版本号")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_CONFIRM",
                                        comment="PENDING_CONFIRM/CONFIRMED/CHANGE_PENDING")
    history_json: Mapped[list | None] = mapped_column(JSON, comment="历史版本快照")
    issued_by: Mapped[str | None] = mapped_column(String(100))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    change_reason: Mapped[str | None] = mapped_column(String(500))


class GraduationGuidance(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_guidance 指导过程记录（时间线留痕，用于指导频次统计/不足预警 GD-R06）。"""
    __tablename__ = "t_gd_guidance"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    guidance_date: Mapped[datetime | None] = mapped_column(DateTime)
    method: Mapped[str] = mapped_column(String(30), nullable=False, default="ONLINE",
                                        comment="ONLINE线上/OFFLINE线下")
    content: Mapped[str | None] = mapped_column(String(2000), comment="指导内容")
    issues: Mapped[str | None] = mapped_column(String(1000), comment="发现的问题")
    attachments_json: Mapped[list | None] = mapped_column(JSON)
    void_reason: Mapped[str | None] = mapped_column(String(500))


class GraduationMidterm(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_midterm 中期检查（三档结论+整改跟踪）。
    状态机：PENDING(待检查)→CHECKED_PASS/RECTIFYING/CHECKED_FAIL；
    RECTIFYING→RECTIFY_SUBMITTED→RECTIFIED_PASS/RECTIFYING(复核不通过)。"""
    __tablename__ = "t_gd_midterm"
    __table_args__ = (UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_midterm_student"),)

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                        comment="PENDING/CHECKED_PASS/RECTIFYING/RECTIFY_SUBMITTED/"
                                                "RECTIFIED_PASS/CHECKED_FAIL")
    conclusion: Mapped[str | None] = mapped_column(String(30), comment="PASS/RECTIFY/FAIL")
    check_comment: Mapped[str | None] = mapped_column(String(1000))
    check_by: Mapped[str | None] = mapped_column(String(100))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    rectify_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    rectify_content: Mapped[str | None] = mapped_column(String(2000))
    rectify_submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    rectify_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_comment: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationProposal(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_proposal"
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version: Mapped[str | None] = mapped_column(String(20))
    is_resubmit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    background: Mapped[str | None] = mapped_column(String(2000))
    plan: Mapped[str | None] = mapped_column(String(2000))
    outcome: Mapped[str | None] = mapped_column(String(2000))
    attachments_json: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    # 开题答辩（现场环节，区别于书面审核）
    defense_result: Mapped[str | None] = mapped_column(String(20), comment="PASS通过/FAIL不通过")
    defense_comment: Mapped[str | None] = mapped_column(String(500))
    defense_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationFinal(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_final"
    __table_args__ = (
        Index("ix_gd_final_tenant_student_status", "tenant_id", "gd_student_id", "status", "is_deleted"),
    )
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    final_type: Mapped[str] = mapped_column(String(20), nullable=False, default="初稿")
    version: Mapped[str | None] = mapped_column(String(20))
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    plagiarism_rate: Mapped[str | None] = mapped_column(String(20))
    plagiarism_status: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    attachments_json: Mapped[list | None] = mapped_column(JSON, comment="论文/材料附件 file_id 列表（文件中心 t_file_object.id）")


class GraduationDefenseGroup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_defense_group"
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    defense_date: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(100))
    chair: Mapped[str | None] = mapped_column(String(100))
    members_json: Mapped[list | None] = mapped_column(JSON)
    secretary: Mapped[str | None] = mapped_column(String(100))
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict: Mapped[str | None] = mapped_column(String(300))
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GraduationPlagiarismCheck(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_plagiarism 查重记录（对齐老系统 0检测中/1完成/2失败 + 复查申请）。"""
    __tablename__ = "t_gd_plagiarism"
    __table_args__ = (
        Index("ix_gd_plag_tenant_final_status", "tenant_id", "gd_final_id", "status", "is_deleted"),
    )

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    gd_final_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="关联成果 t_gd_final.id")
    submit_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CHECKING",
                                        comment="CHECKING检测中/DONE完成/FAILED失败")
    rate: Mapped[str | None] = mapped_column(String(20), comment="重复率，如 12.5%")
    report_url: Mapped[str | None] = mapped_column(String(500))
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    over_threshold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispute_reason: Mapped[str | None] = mapped_column(String(500))
    dispute_status: Mapped[str | None] = mapped_column(String(30), comment="NONE/PENDING/APPROVED/REJECTED")
    dispute_comment: Mapped[str | None] = mapped_column(String(500))


class GraduationReview(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_review 教师评阅（独立评阅角色，SoD：评阅人≠该生指导教师）。"""
    __tablename__ = "t_gd_review"
    __table_args__ = (
        Index("ix_gd_review_tenant_student_status", "tenant_id", "gd_student_id", "status", "is_deleted"),
    )

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    gd_final_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reviewer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ASSIGNED",
                                        comment="ASSIGNED/REVIEWING/COMPLETED/RETURNED")
    score: Mapped[int | None] = mapped_column(Integer)
    opinion: Mapped[str | None] = mapped_column(String(2000))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    assigned_by: Mapped[str | None] = mapped_column(String(100))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationDefenseScore(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_defense_score 答辩评分（每评委对每学生一条；缺席/二次答辩留痕）。"""
    __tablename__ = "t_gd_defense_score"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    defense_group_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    judge_name: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(1000))
    absent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    absent_reason: Mapped[str | None] = mapped_column(String(500))
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="1首次答辩/2二次答辩")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING",
                                        comment="PENDING/SCORED/CONFIRMED")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationGrade(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_grade 成绩评定（导师分/评阅分/答辩分/综合分；核算→复核→发布→撤回）。"""
    __tablename__ = "t_gd_grade"
    __table_args__ = (UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_grade_student"),)

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    advisor_score: Mapped[int | None] = mapped_column(Integer)
    reviewer_score: Mapped[int | None] = mapped_column(Integer)
    defense_score: Mapped[int | None] = mapped_column(Integer)
    total_score: Mapped[int | None] = mapped_column(Integer)
    grade_level: Mapped[str | None] = mapped_column(String(20), comment="优秀/良好/中等/及格/不及格")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT",
                                        comment="DRAFT/CALCULATED/PENDING_REVIEW/PUBLISHED/WITHDRAWN")
    remark: Mapped[str | None] = mapped_column(String(500))
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdraw_reason: Mapped[str | None] = mapped_column(String(500))
    source_snapshot_hash: Mapped[str | None] = mapped_column(
        String(64), comment="SHA-256 of authoritative review/defense inputs at calculation"
    )


class GraduationRiskCase(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_risk_case 问题预警处置台账（GD-R01~R13 扫描生成，受理→处理→复核→关闭）。"""
    __tablename__ = "t_gd_risk_case"
    __table_args__ = (UniqueConstraint("tenant_id", "risk_code", "gd_student_id", name="uk_gd_risk_case"),)

    risk_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="GD-R01~GD-R13")
    risk_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM",
                                       comment="LOW/MEDIUM/HIGH/CRITICAL")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN",
                                        comment="OPEN/PROCESSING/CLOSED")
    assignee: Mapped[str | None] = mapped_column(String(100))
    handle_note: Mapped[str | None] = mapped_column(String(1000))
    close_reason: Mapped[str | None] = mapped_column(String(500))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationArchiveRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_archive_record 毕设归档（材料清单核验→归档；对齐老系统 filingModel 0-4 语义）。"""
    __tablename__ = "t_gd_archive_record"
    __table_args__ = (
        UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_archive_student"),
        Index("ix_gd_archive_tenant_status", "tenant_id", "status", "is_deleted"),
    )

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    checklist_json: Mapped[list | None] = mapped_column(JSON, comment="[{item,required,present}]")
    missing_items: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_GENERATED",
                                        comment="NOT_GENERATED/PENDING_SUBMIT/SUBMITTED/FILED/REJECTED")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(100))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime)
    archive_batch_no: Mapped[str | None] = mapped_column(String(100))
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    manifest_hash: Mapped[str | None] = mapped_column(
        String(64), comment="SHA-256 evidence manifest fixed at filing"
    )


class GraduationAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_gd_audit_trail"
    __table_args__ = (Index("ix_gd_audit_request_id", "tenant_id", "request_id"),)
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    request_id: Mapped[str | None] = mapped_column(String(64), default=_audit_trace_id)
    request_path: Mapped[str | None] = mapped_column(String(500), default=_audit_request_path)
    client_ip: Mapped[str | None] = mapped_column(String(64), default=_audit_client_ip)


class GraduationTemplate(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_template 毕设模板中心（材料/任务书/开题模板统一底座）。
    状态机 DRAFT→ENABLED↔DISABLED→ARCHIVED；同租户同类型默认模板唯一。"""
    __tablename__ = "t_gd_template"

    template_type: Mapped[str] = mapped_column(String(30), nullable=False,
                                               comment="MATERIAL材料/TASKBOOK任务书/PROPOSAL开题")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_version: Mapped[str | None] = mapped_column(String(20), comment="业务版本号，避免与乐观锁 version 冲突")
    content: Mapped[str | None] = mapped_column(String(8000), comment="模板正文")
    variables_json: Mapped[list | None] = mapped_column(JSON, comment="可用占位变量说明")
    applicable_note: Mapped[str | None] = mapped_column(String(500), comment="适用范围说明（学院/专业/年级/批次）")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT",
                                        comment="DRAFT/ENABLED/DISABLED/ARCHIVED")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationMentorEval(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_mentor_eval 导师评价（学院/管理端周期评价，含历史）。"""
    __tablename__ = "t_gd_mentor_eval"

    mentor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    period: Mapped[str | None] = mapped_column(String(50), comment="评价周期，如 2026春")
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 0-100")
    level: Mapped[str] = mapped_column(String(20), nullable=False, comment="优秀/良好/合格/不合格")
    note: Mapped[str | None] = mapped_column(String(1000))
    evaluated_by: Mapped[str | None] = mapped_column(String(100))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class GraduationPeerReview(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_peer_review 成果互查整改（学生互评+被评学生整改）。"""
    __tablename__ = "t_gd_peer_review"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="被评学生")
    reviewer_gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="互查学生")
    gd_final_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    opinion: Mapped[str | None] = mapped_column(String(1000), comment="互查意见")
    rectify_note: Mapped[str | None] = mapped_column(String(1000), comment="整改说明")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ASSIGNED",
                                        comment="ASSIGNED待互查/REVIEWED已互查/RECTIFIED已整改")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationDefenseExpert(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_defense_expert 答辩专家库（评委抽取 + 回避）。"""
    __tablename__ = "t_gd_defense_expert"

    expert_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(50), comment="职称")
    college_name: Mapped[str | None] = mapped_column(String(100))
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否校外专家")
    avoid_note: Mapped[str | None] = mapped_column(String(300), comment="回避说明（如不评本院学生）")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE",
                                        comment="ACTIVE启用/DISABLED停用")


class GraduationGradeAppeal(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_grade_appeal 成绩更正申诉（学生对已发布成绩申诉→复核）。"""
    __tablename__ = "t_gd_grade_appeal"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False, comment="申诉理由")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING",
                                        comment="PENDING待复核/APPROVED受理/REJECTED驳回")
    review_comment: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationStudentEval(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_student_eval 导师对学生过程评价（区别于 t_gd_mentor_eval 学院评导师）。"""
    __tablename__ = "t_gd_student_eval"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    period: Mapped[str | None] = mapped_column(String(50), comment="评价周期，如 中期/终期/2026春")
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 0-100")
    level: Mapped[str] = mapped_column(String(20), nullable=False, comment="优秀/良好/合格/不合格")
    content: Mapped[str | None] = mapped_column(String(2000), comment="评价意见")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUBMITTED",
                                        comment="DRAFT草稿/SUBMITTED已提交")
    submitted_by: Mapped[str | None] = mapped_column(String(100))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationGuidancePlan(PKMixin, TenantMixin, CommonMixin, Base):
    """t_gd_guidance_plan 指导计划条目；签到写回本行（MVP 一计划一次签到）。"""
    __tablename__ = "t_gd_guidance_plan"

    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mentor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_date: Mapped[datetime | None] = mapped_column(DateTime, comment="计划指导日期")
    content: Mapped[str | None] = mapped_column(String(2000), comment="计划内容/要求")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PLANNED",
                                        comment="PLANNED待签到/CHECKED_IN已签到/CANCELLED已取消")
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    checked_in_by: Mapped[str | None] = mapped_column(String(100))
    checkin_role: Mapped[str | None] = mapped_column(String(20), comment="STUDENT/MENTOR/STAFF")
    checkin_note: Mapped[str | None] = mapped_column(String(500))
    checkin_method: Mapped[str | None] = mapped_column(String(30), comment="ONLINE/OFFLINE/MANUAL")
    void_reason: Mapped[str | None] = mapped_column(String(500))

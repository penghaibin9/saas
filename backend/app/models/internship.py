"""岗位实习域模型（P7-INTERNSHIP）。对齐 DB 冻结册命名：t_ 前缀 / snake_case / BIGINT PK /
公共字段（tenant_id/created_at/...）。审计链 append-only（AuditTimeMixin）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class InternshipBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_batch 实习批次（组织实习工作的时间轴 + 规则骨架，状态机
    DRAFT草稿 → RUNNING进行中 → CLOSED已结束 → ARCHIVED已归档；VOIDED仅草稿可作废）。"""
    __tablename__ = "t_internship_batch"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_no", name="uk_intern_batch_no"),)

    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year: Mapped[str | None] = mapped_column(String(20), comment="学年，如 2025-2026")
    term: Mapped[str | None] = mapped_column(String(20), comment="学期")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="实习起")
    end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="实习止")
    signup_start_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报名/资格确认窗口起")
    signup_end_date: Mapped[datetime | None] = mapped_column(DateTime, comment="报名/资格确认窗口止")
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="计划实习人数")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT",
                                        comment="DRAFT/RUNNING/CLOSED/ARCHIVED/VOIDED")
    stage_config: Mapped[list | None] = mapped_column(JSON, comment="阶段/时间轴 [{code,name,startDate,endDate}]")
    rules_config: Mapped[dict | None] = mapped_column(
        JSON, comment="规则配置 {checkin/weeklyReport/guidance/evaluation/score}")
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="已生效规则版本")
    previous_status: Mapped[str | None] = mapped_column(String(50))
    last_transition_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_transition_by: Mapped[str | None] = mapped_column(String(100))
    transition_reason: Mapped[str | None] = mapped_column(String(500))
    archive_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_ARCHIVED",
                                                comment="NOT_ARCHIVED/ARCHIVED")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    archive_batch_no: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_record 学生实习记录（一名学生一个批次一条）。"""
    __tablename__ = "t_internship_record"
    __table_args__ = (UniqueConstraint("tenant_id", "student_id", "batch_id",
                                       name="uk_intern_stu_batch"),)

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                            comment="= t_student_profile.id")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    enterprise_name: Mapped[str | None] = mapped_column(String(200), comment="实习单位（冗余展示）")
    position_name: Mapped[str | None] = mapped_column(String(100), comment="岗位（冗余展示）")
    advisor_name: Mapped[str | None] = mapped_column(String(100), comment="校内指导教师")
    enterprise_mentor_name: Mapped[str | None] = mapped_column(String(100), comment="企业导师（冗余展示）")
    advisor_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="校内指导教师 t_user.id")
    # ── 与企业库/岗位库真实关联（additive；分配岗位时回填，退岗时清空）──
    enterprise_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_emp_company.id")
    position_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ t_internship_position.id")
    mentor_contact_id: Mapped[int | None] = mapped_column(BigInteger, comment="→ t_internship_enterprise_contact.id")
    eligibility_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                                    comment="实习资格 PENDING/QUALIFIED/UNQUALIFIED")
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE",
                                                  comment="实习去向 ASSIGNED/SELF_ARRANGED/EXEMPTED/NONE")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PREPARING",
                                        comment="PREPARING/READY/ONBOARD/ASSESSING/ARCHIVED")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NONE",
                                            comment="NONE/LOW/MEDIUM/HIGH")
    intern_start_date: Mapped[datetime | None] = mapped_column(DateTime)
    intern_end_date: Mapped[datetime | None] = mapped_column(DateTime)
    insurance_info: Mapped[str | None] = mapped_column(String(200), comment="实习保险")
    agreement_info: Mapped[str | None] = mapped_column(String(200), comment="三方协议状态")
    remark: Mapped[str | None] = mapped_column(String(500))


class AttendanceException(PKMixin, TenantMixin, CommonMixin, Base):
    """t_attendance_exception 打卡异常（超范围/模拟定位/缺卡）。"""
    __tablename__ = "t_attendance_exception"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                                comment="OUT_OF_RANGE/MOCK_LOCATION/MISSING")
    exception_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    distance_km: Mapped[float | None] = mapped_column(Float, comment="偏离距离(km)")
    gps_accuracy: Mapped[float | None] = mapped_column(Float, comment="定位精度(m)")
    device_risk_flag: Mapped[str | None] = mapped_column(String(50), comment="normal/is_mock")
    address: Mapped[str | None] = mapped_column(String(300))
    student_note: Mapped[str | None] = mapped_column(String(1000), comment="学生说明")
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="连续异常天数")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE",
                                        comment="PENDING_HANDLE/COMPLETED")
    handle_action: Mapped[str | None] = mapped_column(String(50),
                                                      comment="REASONABLE/ABNORMAL/TO_RISK")
    handle_comment: Mapped[str | None] = mapped_column(String(500))
    handled_by_name: Mapped[str | None] = mapped_column(String(100))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    appeal_status: Mapped[str | None] = mapped_column(String(30), comment="PENDING/ACCEPTED/REJECTED")
    appeal_note: Mapped[str | None] = mapped_column(String(1000), comment="学生异常申诉说明")
    appeal_file_id: Mapped[str | None] = mapped_column(String(64), comment="申诉凭证文件")
    appealed_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipCheckin(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_checkin 实习每日打卡（真实落库；一天一次，唯一约束兜底并发）。
    企业电子围栏未配置时 result=RECORDED（仅留痕定位），配置后可算 NORMAL/OUT_OF_RANGE。"""
    __tablename__ = "t_internship_checkin"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "checkin_date",
                                       name="uk_internship_checkin_day"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    checkin_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="YYYY-MM-DD")
    checkin_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(300))
    result: Mapped[str] = mapped_column(String(30), nullable=False, default="RECORDED",
                                        comment="RECORDED/NORMAL/OUT_OF_RANGE/NO_LOCATION")
    note: Mapped[str | None] = mapped_column(String(500), comment="学生备注")
    gps_accuracy: Mapped[float | None] = mapped_column(Float, comment="定位精度(m)")
    device_risk_flag: Mapped[str | None] = mapped_column(String(30), comment="normal/mock/rooted")
    distance_m: Mapped[float | None] = mapped_column(Float, comment="距岗位围栏中心距离(m)")
    evidence_file_id: Mapped[str | None] = mapped_column(String(64), comment="打卡凭证文件")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), comment="客户端幂等键")


class InternshipMakeup(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_makeup 补卡申请（学生对某日缺卡发起，指导教师审批）。
    状态机：PENDING 待审核 →(教师) APPROVED 已通过 / REJECTED 已驳回；PENDING →(学生) WITHDRAWN 已撤回。
    owner 边界：学生只能对本人实习记录申请/撤回；教师只能审批本人指导学生的申请（advisor_name）。"""
    __tablename__ = "t_internship_makeup"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    checkin_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="补卡日期 YYYY-MM-DD")
    makeup_type: Mapped[str] = mapped_column(String(20), nullable=False, default="MISSING",
                                             comment="MISSING 缺卡 / OUT_OF_RANGE 超范围补录")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="补卡事由")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED/WITHDRAWN")
    apply_by_name: Mapped[str | None] = mapped_column(String(50), comment="申请人（学生）")
    review_by_name: Mapped[str | None] = mapped_column(String(50), comment="审批人")
    review_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))


class InternshipGuidance(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_guidance 指导记录（指导教师对本人指导学生的过程指导留痕）。
    owner：教师只能对本人指导学生（advisor_name）新增/撤销。撤销走软删（status=VOIDED）。"""
    __tablename__ = "t_internship_guidance"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    advisor_name: Mapped[str | None] = mapped_column(String(50), comment="指导教师")
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="ONSITE",
                                        comment="ONLINE/PHONE/ONSITE/ENTERPRISE_FEEDBACK/VIDEO")
    topic: Mapped[str | None] = mapped_column(String(200), comment="指导主题")
    content: Mapped[str | None] = mapped_column(Text, comment="指导内容")
    problem_type: Mapped[str | None] = mapped_column(String(50), comment="问题类型")
    suggestion: Mapped[str | None] = mapped_column(String(1000), comment="处理建议")
    next_follow_date: Mapped[str | None] = mapped_column(String(10), comment="下次跟进日期 YYYY-MM-DD")
    to_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否形成风险")
    notify_counselor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                   comment="是否通知辅导员")
    file_id: Mapped[str | None] = mapped_column(String(64), comment="附件 file_id 预留（文件中心）")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="NORMAL",
                                        comment="NORMAL/VOIDED")


class InternshipVisit(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_visit 教师巡访记录（含企业/学生反馈、安全隐患与整改跟进）。
    owner：教师只能对本人指导学生新增巡访；整改状态 NONE→PENDING→DONE。"""
    __tablename__ = "t_internship_visit"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    advisor_name: Mapped[str | None] = mapped_column(String(50), comment="巡访教师")
    enterprise_name: Mapped[str | None] = mapped_column(String(200))
    visit_at: Mapped[datetime | None] = mapped_column(DateTime, comment="巡访时间")
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="ONSITE",
                                        comment="ONSITE/ONLINE/PHONE")
    enterprise_feedback: Mapped[str | None] = mapped_column(String(1000), comment="企业反馈")
    student_feedback: Mapped[str | None] = mapped_column(String(1000), comment="学生反馈")
    safety_issue: Mapped[str | None] = mapped_column(String(500), comment="安全隐患")
    rectify_require: Mapped[str | None] = mapped_column(String(500), comment="整改要求")
    rectify_deadline: Mapped[str | None] = mapped_column(String(10), comment="整改截止 YYYY-MM-DD")
    rectify_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE",
                                                comment="NONE/PENDING/DONE")
    monthly_report: Mapped[str | None] = mapped_column(Text, comment="巡访月报")
    file_id: Mapped[str | None] = mapped_column(String(64), comment="附件 file_id 预留")


class InternshipAgreement(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_agreement 三方协议签署实例（区别于 t_internship_agreement_template 模板库）。
    三方确认流：DRAFT 草稿 → PENDING_STUDENT 待学生确认 → PENDING_ENTERPRISE 待企业确认
    → PENDING_SCHOOL 待学校确认 → EFFECTIVE 已生效；旁支 REJECTED/VOIDED/ARCHIVED。
    无电子签章时，企业确认以「上传纸质三方协议签署扫描件(file_id)」为准（不伪造电子签），
    电子签章能力预留。owner：学生本人确认；教师/管理员生成/推进/作废/归档。"""
    __tablename__ = "t_internship_agreement"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    template_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="→ 模板库")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    enterprise_name: Mapped[str | None] = mapped_column(String(200))
    position_name: Mapped[str | None] = mapped_column(String(100))
    student_confirm_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                                        comment="PENDING/CONFIRMED/REJECTED")
    student_confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_confirm_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    enterprise_confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_confirm_by: Mapped[str | None] = mapped_column(String(50), comment="记录企业签署的经办人")
    school_confirm_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    school_confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_confirm_by: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True,
                                        comment="DRAFT/PENDING_STUDENT/PENDING_ENTERPRISE/PENDING_SCHOOL/"
                                                "EFFECTIVE/REJECTED/VOIDED/ARCHIVED")
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    file_id: Mapped[str | None] = mapped_column(String(64), comment="签署扫描件 file_id（文件中心）")
    esign_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE",
                                              comment="电子签章预留 NONE/PENDING/SIGNED")
    # ── 模板渲染正文快照（0036）──
    rendered_body: Mapped[str | None] = mapped_column(Text, comment="生成时模板变量渲染快照")
    # ── 电子签流转（0038；无签章时仅记录时间线，不伪造电子签）──
    esign_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="INTERNAL",
                                                comment="电子签渠道 INTERNAL/第三方")
    esign_initiated_at: Mapped[datetime | None] = mapped_column(DateTime)
    esign_initiated_by: Mapped[str | None] = mapped_column(String(50))
    esign_student_at: Mapped[datetime | None] = mapped_column(DateTime)
    esign_enterprise_at: Mapped[datetime | None] = mapped_column(DateTime)
    esign_school_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipEnterpriseEval(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_enterprise_eval 企业评价（企业导师对学生的五维评价 + 学校审核）。
    来源 source：ENTERPRISE 企业导师本人提交（门户权限预留）/ SCHOOL_RECORDED 学校录入企业纸质评价
    （须填企业导师姓名 + 建议附签署扫描件，源可追溯，避免学校代填假闭环）。
    审核：submit_status SUBMITTED；school_review_status PENDING→APPROVED/RETURNED。"""
    __tablename__ = "t_internship_enterprise_eval"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    position_name: Mapped[str | None] = mapped_column(String(100))
    mentor_name: Mapped[str | None] = mapped_column(String(50), comment="企业导师姓名")
    attendance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="出勤 0-100")
    skill_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="技能 0-100")
    attitude_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="态度 0-100")
    collaboration_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="协作 0-100")
    safety_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="安全纪律 0-100")
    overall_comment: Mapped[str | None] = mapped_column(Text, comment="综合评语")
    recommend_hire: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否建议录用")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHOOL_RECORDED",
                                        comment="ENTERPRISE/SCHOOL_RECORDED")
    submit_status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUBMITTED",
                                               comment="DRAFT/SUBMITTED")
    school_review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                                      comment="PENDING/APPROVED/RETURNED")
    school_review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    file_id: Mapped[str | None] = mapped_column(String(64), comment="企业签署评价扫描件 file_id")


class InternshipStudentEval(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_student_eval 学生实习鉴定/自评（学生自评 + 教师/企业意见 + 学校审核）。
    学生本人提交自评(mobile) SUBMITTED；指导教师补意见；学校审核 PENDING→APPROVED/RETURNED。"""
    __tablename__ = "t_internship_student_eval"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    self_summary: Mapped[str | None] = mapped_column(Text, comment="实习总结")
    self_harvest: Mapped[str | None] = mapped_column(Text, comment="学习收获")
    self_problem: Mapped[str | None] = mapped_column(Text, comment="存在问题")
    advisor_opinion: Mapped[str | None] = mapped_column(String(1000), comment="指导教师意见")
    mentor_opinion: Mapped[str | None] = mapped_column(String(1000), comment="企业导师意见")
    submit_status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT",
                                               comment="DRAFT/SUBMITTED")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                                      comment="PENDING/APPROVED/RETURNED")
    school_review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    file_id: Mapped[str | None] = mapped_column(String(64), comment="鉴定表扫描件 file_id")
    # ── 学生对企业/岗位的评价（0037）──
    enterprise_rating: Mapped[int | None] = mapped_column(Integer, comment="对企业评分 1-5")
    position_rating: Mapped[int | None] = mapped_column(Integer, comment="对岗位评分 1-5")
    enterprise_feedback: Mapped[str | None] = mapped_column(String(1000), comment="对企业评价意见")
    position_feedback: Mapped[str | None] = mapped_column(String(1000), comment="对岗位评价意见")


class InternshipScoreConfig(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_score_config 实习成绩权重配置（五项权重，和须=100）。batch_id 空=租户默认。"""
    __tablename__ = "t_internship_score_config"

    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    checkin_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20, comment="打卡权重")
    weekly_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20, comment="周报权重")
    monthly_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10, comment="月报/总结权重")
    enterprise_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=30, comment="企业评价权重")
    school_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20, comment="学校/教师评价权重")
    pass_line: Mapped[float] = mapped_column(Float, nullable=False, default=60.0, comment="及格线")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class InternshipFinalScore(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_final_score 实习最终成绩（五项加权核算）。一名学生一条。
    状态机：PENDING_CALC 待核算 → PENDING_REVIEW 待复核 → PUBLISHED 已发布 → WITHDRAWN 已撤回 → ARCHIVED 已归档。
    缺项(incomplete)不得发布。"""
    __tablename__ = "t_internship_final_score"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    score_config_id: Mapped[int | None] = mapped_column(BigInteger, index=True, comment="核算时的评分配置快照 id")
    score_config_version: Mapped[int | None] = mapped_column(Integer, comment="核算时的评分配置版本")
    checkin_score: Mapped[int | None] = mapped_column(Integer, comment="打卡分 0-100")
    weekly_score: Mapped[int | None] = mapped_column(Integer, comment="周报分 0-100")
    monthly_score: Mapped[int | None] = mapped_column(Integer, comment="月报/总结分 0-100")
    enterprise_score: Mapped[int | None] = mapped_column(Integer, comment="企业评价分 0-100（可自动取企业评价均分）")
    school_score: Mapped[int | None] = mapped_column(Integer, comment="学校/指导教师评分 0-100")
    w_checkin: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="权重快照")
    w_weekly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    w_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    w_enterprise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    w_school: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[float | None] = mapped_column(Float, comment="加权总分")
    pass_line: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    incomplete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否缺项")
    incomplete_reason: Mapped[str | None] = mapped_column(String(300), comment="缺哪几项")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING_CALC",
                                        comment="PENDING_CALC/PENDING_REVIEW/PUBLISHED/WITHDRAWN/ARCHIVED")
    reviewed_by_name: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by_name: Mapped[str | None] = mapped_column(String(50))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipLeave(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_leave 实习请假（学生对实习期请假，指导教师审批）。
    状态机：PENDING 待审批 →(教师) APPROVED 已通过 / REJECTED 已驳回；PENDING →(学生) WITHDRAWN 已撤回。
    owner 边界：学生只能对本人实习记录申请/撤回；教师只能审批本人指导学生（advisor_name）。"""
    __tablename__ = "t_internship_leave"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False, default="PERSONAL",
                                            comment="SICK 病假 / PERSONAL 事假 / OTHER 其他")
    start_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="起 YYYY-MM-DD")
    end_date: Mapped[str] = mapped_column(String(10), nullable=False, comment="止 YYYY-MM-DD")
    days: Mapped[float] = mapped_column(Float, nullable=False, default=1, comment="请假天数")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="请假事由")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED/WITHDRAWN")
    apply_by_name: Mapped[str | None] = mapped_column(String(50), comment="申请人（学生）")
    review_by_name: Mapped[str | None] = mapped_column(String(50), comment="审批人")
    review_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))
    file_id: Mapped[str | None] = mapped_column(String(64), comment="证明附件 file_id（文件中心）")


    returned_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Actual return-from-leave time")
    return_note: Mapped[str | None] = mapped_column(String(500), comment="Student return note")
    return_file_id: Mapped[str | None] = mapped_column(String(64), comment="Return evidence file id")


class WeeklyReport(PKMixin, TenantMixin, CommonMixin, Base):
    """t_weekly_report 实习周报（支持重交版本）。"""
    __tablename__ = "t_weekly_report"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "week_number",
                                       name="uk_weekly_report_week"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    work_content: Mapped[str | None] = mapped_column(String(2000), comment="本周工作")
    harvest_content: Mapped[str | None] = mapped_column(String(2000), comment="学习收获")
    plan_content: Mapped[str | None] = mapped_column(String(2000), comment="下周计划")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                                comment="版本号，重交自增")
    risk_flag: Mapped[str | None] = mapped_column(String(50), comment="内容风险标记")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW",
                                        comment="PENDING_REVIEW/APPROVED/RETURNED/OVERDUE")
    review_action: Mapped[str | None] = mapped_column(String(50), comment="APPROVE/RETURN")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class RiskRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """t_risk_record 实习风险单（系统预警或人工创建）。"""
    __tablename__ = "t_risk_record"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    risk_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="如 INT-R07")
    risk_title: Mapped[str] = mapped_column(String(200), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="MEDIUM",
                                            comment="HIGH/MEDIUM/LOW")
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, default="system",
                                               comment="system/manual")
    owner_name: Mapped[str | None] = mapped_column(String(100), comment="跟进责任人")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_HANDLE",
                                        comment="PENDING_HANDLE/PROCESSING/RESOLVED/CLOSED")
    last_follow_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_follow_note: Mapped[str | None] = mapped_column(String(500))


class InternshipAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """t_internship_audit_trail 实习域操作留痕——append-only（无 is_deleted/updated_at/version）。"""
    __tablename__ = "t_internship_audit_trail"

    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                             comment="RECORD/EXCEPTION/REPORT/RISK/BATCH")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(100))
    detail_json: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# P3 深化：归档 / 过程报告 / 变更申请 / 计划书 / 计划确认 / 保险 / 计划任务完成度
# 表结构已由迁移 0035/0037/0038/0041 建好；此处仅补建缺失的 ORM 映射（无新增迁移）。
# ─────────────────────────────────────────────────────────────────────────────
class InternshipArchive(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_archive 实习归档快照（P3-A，迁移 0035）。一名学生一实习一条。"""
    __tablename__ = "t_internship_archive"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="材料完整度 0-100")
    missing_items: Mapped[str | None] = mapped_column(String(500), comment="缺失材料清单")
    material_snapshot: Mapped[dict | None] = mapped_column(JSON, comment="归档材料快照")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ARCHIVED",
                                        comment="ARCHIVED/REVOKED")
    package_file_id: Mapped[str | None] = mapped_column(String(64), comment="归档包 file_id")
    archived_by_name: Mapped[str | None] = mapped_column(String(50))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))


class InternshipProcessReport(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_process_report 实习过程报告（月报/总结等，迁移 0037）。"""
    __tablename__ = "t_internship_process_report"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "report_type", "period_key",
                                       name="uk_intern_process_report"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="报告类型 MONTHLY/SUMMARY 等")
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, comment="周期键，如 2026-03")
    content: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_REVIEW",
                                        comment="PENDING_REVIEW/APPROVED/RETURNED")
    review_action: Mapped[str | None] = mapped_column(String(50))
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipChangeRequest(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_change_request 实习变更申请（换单位/换岗位等，迁移 0037）。"""
    __tablename__ = "t_internship_change_request"

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="变更类型")
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    target_enterprise_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    target_position_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    target_enterprise_name: Mapped[str | None] = mapped_column(String(200))
    target_position_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED")
    review_comment: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipBatchPlan(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_batch_plan 实习计划书（批次级，迁移 0038）。一批次一份。"""
    __tablename__ = "t_internship_batch_plan"
    __table_args__ = (UniqueConstraint("tenant_id", "batch_id", name="uk_intern_batch_plan"),)

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objectives: Mapped[str | None] = mapped_column(Text, comment="实习目标")
    content: Mapped[str | None] = mapped_column(Text, comment="计划正文")
    tasks_json: Mapped[list | None] = mapped_column(JSON, comment="任务清单")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT",
                                        comment="DRAFT/PUBLISHED")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by_name: Mapped[str | None] = mapped_column(String(50))


class InternshipPlanAck(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_plan_ack 计划书学生确认回执（迁移 0038）。一学生一计划一条。"""
    __tablename__ = "t_internship_plan_ack"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "plan_id", name="uk_intern_plan_ack"),)

    plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/ACKNOWLEDGED")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipInsurance(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_insurance 实习保险核验（迁移 0038）。一学生一实习一条。"""
    __tablename__ = "t_internship_insurance"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", name="uk_intern_insurance"),)

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    policy_no: Mapped[str | None] = mapped_column(String(100), comment="保单号")
    insurer_name: Mapped[str | None] = mapped_column(String(200), comment="承保机构")
    coverage_type: Mapped[str | None] = mapped_column(String(100), comment="险种")
    effective_date: Mapped[str | None] = mapped_column(String(10), comment="生效日 YYYY-MM-DD")
    expiry_date: Mapped[str | None] = mapped_column(String(10), comment="失效日 YYYY-MM-DD")
    file_id: Mapped[str | None] = mapped_column(String(64), comment="保单扫描件 file_id")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_SUBMITTED",
                                        comment="NOT_SUBMITTED/SUBMITTED/VERIFIED/REJECTED")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    verify_comment: Mapped[str | None] = mapped_column(String(500))
    verified_by_name: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)


class InternshipPlanTaskProgress(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_plan_task_progress 计划任务逐项完成度（学生打卡，迁移 0041）。"""
    __tablename__ = "t_internship_plan_task_progress"
    __table_args__ = (UniqueConstraint("tenant_id", "internship_id", "plan_id", "task_sort_order",
                                       name="uk_intern_plan_task_prog"),)

    plan_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    task_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="任务序号")
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_STARTED",
                                        comment="NOT_STARTED/SUBMITTED/APPROVED/RETURNED")
    student_note: Mapped[str | None] = mapped_column(String(500))
    evidence_file_id: Mapped[str | None] = mapped_column(String(64))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by_name: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))

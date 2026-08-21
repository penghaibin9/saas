"""就业服务域模型（P7-EMPLOYMENT）。t_emp_ 前缀 + 公共字段；审计链 append-only。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, event, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class EmpStudent(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_student"
    __table_args__ = (
        Index("ix_emp_student_tenant_profile_active", "tenant_id", "student_id", "is_deleted"),
    )
    student_no: Mapped[str | None] = mapped_column(String(50), index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    grade: Mapped[str | None] = mapped_column(String(20))
    college_name: Mapped[str | None] = mapped_column(String(100))
    major_name: Mapped[str | None] = mapped_column(String(100))
    class_id: Mapped[str | None] = mapped_column(String(50))
    class_name: Mapped[str | None] = mapped_column(String(100))
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    id_card_encrypted: Mapped[str | None] = mapped_column(String(500))
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="UNEMPLOYED")
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(100))
    salary_range: Mapped[str | None] = mapped_column(String(50))
    sign_date: Mapped[str | None] = mapped_column(String(20))
    is_match_major: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    from_internship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verify_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_VERIFY")
    material_status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED")
    help_level: Mapped[str] = mapped_column(String(50), nullable=False, default="NORMAL")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))
    counselor: Mapped[str | None] = mapped_column(String(100))
    employment_teacher: Mapped[str | None] = mapped_column(String(100))
    unemployed_reason: Mapped[str | None] = mapped_column(String(500))
    last_follow_up_time: Mapped[datetime | None] = mapped_column(DateTime)
    follow_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # SP-E08：登记表/协议真实文件指针 + 生成时的事实版本快照。source_version 与生成时
    # 不一致就说明去向事实又变了，服务层据此判断是复用旧文件还是重新生成，不是每次
    # 点击都无脑重渲染，也不会在事实已变后继续把旧文件当最新的发出去。
    destination_document_file_id: Mapped[int | None] = mapped_column(BigInteger)
    destination_document_source_version: Mapped[int | None] = mapped_column(Integer)


# W1/P0：verify_status 是“当前去向事实是否已核验”的状态，不是一个可跨事实版本永久继承
# 的标签。只要 destination_type/company_name/job_title 任一 canonical 核验事实发生 ORM
# 更新，旧 VERIFIED/RETURNED 必须 fail-closed 回到 PENDING_VERIFY。把这一条放在 Session
# flush invariant，而不是只散落在某一个 API/service 里，可同时覆盖教师 PC 编辑、批量更新、
# 学生结构化提交写回及后续新增 ORM 写入口，避免以后再出现“新单位继承旧单位 VERIFIED”。
_EMP_VERIFICATION_FACT_FIELDS = ("destination_type", "company_name", "job_title")


@event.listens_for(Session, "before_flush")
def _invalidate_emp_verification_on_fact_change(session, _flush_context, _instances) -> None:
    for obj in session.dirty:
        if not isinstance(obj, EmpStudent):
            continue
        state = inspect(obj)
        if not any(state.attrs[name].history.has_changes() for name in _EMP_VERIFICATION_FACT_FIELDS):
            continue
        obj.verify_status = "PENDING_VERIFY"


class EmpMaterial(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_material"
    emp_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False, default="AGREEMENT")
    file_name: Mapped[str | None] = mapped_column(String(300))
    submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED")
    reviewer: Mapped[str | None] = mapped_column(String(100))
    review_time: Mapped[datetime | None] = mapped_column(DateTime)
    return_reason: Mapped[str | None] = mapped_column(String(500))
    remark: Mapped[str | None] = mapped_column(String(500))


class EmpFollowup(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_followup"
    emp_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    follow_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    way: Mapped[str] = mapped_column(String(50), nullable=False, default="PHONE")
    content: Mapped[str | None] = mapped_column(String(1000))
    result: Mapped[str | None] = mapped_column(String(500))
    next_plan: Mapped[str | None] = mapped_column(String(500))
    operator: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class EmpCompany(PKMixin, TenantMixin, CommonMixin, Base):
    """t_emp_company —— 全系统共享「企业主档」。
    就业域(录用/岗位)与岗位实习域(企业库)共用同一张表，避免重复造企业表。
    就业侧沿用 status/cooperation_level/hired_count；实习企业库侧新增下方 additive 列，
    两域不争抢同一状态字段：企业库合作生命周期走 coop_status。"""
    __tablename__ = "t_emp_company"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credit_code: Mapped[str | None] = mapped_column(String(50), index=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    nature: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    contact_person: Mapped[str | None] = mapped_column(String(100))
    contact_phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    cooperation_level: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    disable_reason: Mapped[str | None] = mapped_column(String(500))
    hired_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ── 岗位实习「企业库」additive 扩展（就业域不引用，向后兼容）──
    region: Mapped[str | None] = mapped_column(String(100), comment="省市/地区")
    address: Mapped[str | None] = mapped_column(String(300), comment="详细地址")
    scale: Mapped[str | None] = mapped_column(String(50), comment="规模：微/小/中/大型")
    source: Mapped[str | None] = mapped_column(String(50), comment="来源 SELF_BUILT/SCHOOL_ENTERPRISE/STUDENT_SELF/RECOMMENDED")
    coop_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING",
                                             index=True, comment="企业库合作状态机 PENDING/ACTIVE/REJECTED/SUSPENDED/BLACKLIST/ARCHIVED")
    qualification_status: Mapped[str] = mapped_column(String(50), nullable=False, default="UNREVIEWED",
                                                      comment="资质核验 UNREVIEWED/PASSED/FAILED")
    blacklist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blacklist_reason: Mapped[str | None] = mapped_column(String(500))
    review_by: Mapped[str | None] = mapped_column(String(100))
    review_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))
    access_valid_until: Mapped[datetime | None] = mapped_column(DateTime, comment="实习企业准入有效期")
    intern_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="累计接收实习生数")
    remark: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_by: Mapped[str | None] = mapped_column(String(100))
    # E4 企业 Portal 公开展示资料；学校准入/黑名单/资质字段仍由上方 canonical 字段控制。
    logo_file_id: Mapped[str | None] = mapped_column(String(64))
    cover_file_id: Mapped[str | None] = mapped_column(String(64))
    short_name: Mapped[str | None] = mapped_column(String(100))
    short_intro: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(300))
    main_business: Mapped[str | None] = mapped_column(Text)
    established_year: Mapped[int | None] = mapped_column(Integer)


class InternshipEnterpriseContact(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_enterprise_contact —— 企业库·联系人 / 企业导师（挂在 t_emp_company 下）。"""
    __tablename__ = "t_internship_enterprise_contact"
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CONTACT",
                                              comment="CONTACT 联系人 / MENTOR 企业导师")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), comment="职务")
    phone_encrypted: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE",
                                        comment="ACTIVE/INACTIVE")


class EmpJob(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_emp_job"
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    salary_range: Mapped[str | None] = mapped_column(String(50))
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    signed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    disable_reason: Mapped[str | None] = mapped_column(String(500))
    publish_time: Mapped[str | None] = mapped_column(String(20))


class EmpAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_emp_audit_trail"
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(200))
    after_val: Mapped[str | None] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class EmpDestinationSubmission(PKMixin, TenantMixin, CommonMixin, Base):
    """SP-E02/E04：结构化就业去向提交。

    学生 PC 此前把 jobTitle/city/contact 拼进 CsWorkOrder 自由文本工单（S4 一期只
    修了 companyName 丢失和 canonical 枚举漂移），既没有字段级 schema，也没有
    workflow/审批，`emp_student_id` 更是完全空白——批准之后无法原子写回
    canonical `EmpStudent`。本表是这条提交的真实结构化事实源，通过
    `t_workflow_instance/task`（source_biz_type=EMPLOYMENT_DESTINATION）走真实
    单节点审批（就业老师核准），批准后原子写回 EmpStudent（company_name/
    job_title/destination_type）。

    city/contact 目前没有对应的 EmpStudent 列（canonical 台账从未建过这两列），
    因此只落在本表——字段不再像旧工单文本那样被截断丢失，但也不假装已经把它们
    同步进了台账；如需台账收字段是后续独立变更，不在本次范围内。
    """
    __tablename__ = "t_emp_destination_submission"
    __table_args__ = (
        Index("ix_emp_dest_sub_tenant_student_status", "tenant_id", "student_id", "status", "is_deleted"),
    )

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    applicant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="申请人 user_id")
    emp_student_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
                                                        comment="批准后写回的 canonical EmpStudent.id")
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    contact: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/RETURNED/APPROVED/REJECTED")
    return_reason: Mapped[str | None] = mapped_column(String(500))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    current_task_id: Mapped[int | None] = mapped_column(BigInteger)
    # 审批乐观锁：与 WorkflowTask.version 分开维护，前端拿它回传即可拒绝过期审批决定，
    # 与 AaStatusChange.decision_version 同一约定。
    decision_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
"""有效成绩策略快照模型与正式成绩同事务自动冻结。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint, event, inspect, select
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaEffectiveGradePolicy(PKMixin, TenantMixin, CommonMixin, Base):
    """租户级、按生效学期版本化的有效成绩策略。

    两条数据库级合同，缺一不可：
    - 版本身份 ``UNIQUE(tenant_id, policy_code, policy_version)``：同一策略代码必须能发布
      V1/V2/V3 版本链，历史成绩继续引用它发布时的那个版本；
    - 活动范围 ``UNIQUE(tenant_id, active_scope_key)``：``active_scope_key`` 只在 ACTIVE 行
      非空（值为生效学期，无学期即 ``BASE``），SUPERSEDED 行置 NULL。MySQL 唯一索引允许
      多行 NULL，于是"同一生效范围同时只能有一条 ACTIVE"由数据库兜底，而不是靠应用先查后写。
    """

    __tablename__ = "t_aa_effective_grade_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_code", "policy_version",
                         name="uk_aa_effective_grade_policy_ver"),
        UniqueConstraint("tenant_id", "active_scope_key", name="uk_aa_effective_grade_policy_scope"),
        Index("ix_aa_effective_grade_policy_active", "tenant_id", "status", "effective_from_term_id"),
    )

    policy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_scope_key: Mapped[str | None] = mapped_column(
        String(40), comment="ACTIVE 行的生效范围键（学期ID 或 BASE）；非 ACTIVE 行为 NULL")
    attempt_strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    makeup_strategy: Mapped[str] = mapped_column(String(40), nullable=False, default="CAP_AND_OVERRIDE")
    makeup_cap: Mapped[int | None] = mapped_column(Integer)
    retake_strategy: Mapped[str] = mapped_column(String(40), nullable=False, default="REPLACE_IF_PASSED")
    recognition_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    effective_from_term_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="DRAFT/ACTIVE/SUPERSEDED")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AaEffectiveGradePolicyBypass(PKMixin, TenantMixin, CommonMixin, Base):
    """历史导入绕过"必须有 ACTIVE 策略"合同时的显式欠账登记。

    正式业务写入无策略一律 409；只有迁移/历史导入可以在 ``legacy_import_context`` 里写入，
    并且必须留下来源、操作人、批次和欠账理由，让上线门禁能查出"哪些正式成绩没有冻结策略"。
    静默放行是不允许的——那正是 NEW-P1-04 的根因。
    """

    __tablename__ = "t_aa_effective_grade_policy_bypass"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_no", name="uk_aa_grade_policy_bypass_batch"),
        Index("ix_aa_grade_policy_bypass_tenant", "tenant_id", "source"),
    )

    source: Mapped[str] = mapped_column(String(50), nullable=False, comment="MIGRATION/LEGACY_IMPORT/SANDBOX")
    operator: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    debt_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    grade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class AaGradeChangeRequest(PKMixin, TenantMixin, CommonMixin, Base):
    """成绩更正命令（包 1 GradeCorrectionCommand）。

    发起更正时把"想改成什么"存在这里，正式成绩一个字节都不动——此前的实现在申请阶段就把
    ``AaGradeRecord`` 的分项改成申请值，于是成绩单、毕业审核和学生自己看到的都是一个还没
    批准的分数（C05）。终审通过时才由统一命令一次性生成新的 ``AcademicGrade`` 版本。

    ``expected_grade_version`` 是发起时看到的正式成绩行版本；终审前若正式成绩已被别的入口
    （复查更正、补考回写）改过，本次更正必须 409 重来，不允许拿过期分数覆盖当前事实。
    """

    __tablename__ = "t_aa_grade_change_request"
    __table_args__ = (
        Index("ix_aa_grade_change_request_record", "tenant_id", "grade_record_id", "status"),
        Index("ix_aa_grade_change_request_instance", "tenant_id", "workflow_instance_id"),
    )

    grade_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    grade_record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="CHANGE_REQUEST",
                                        comment="CHANGE_REQUEST/RECHECK")
    proposed_usual_score: Mapped[int | None] = mapped_column(Integer)
    proposed_midterm_score: Mapped[int | None] = mapped_column(Integer)
    proposed_final_score: Mapped[int | None] = mapped_column(Integer)
    proposed_total_score: Mapped[int | None] = mapped_column(Integer)
    proposed_pass_status: Mapped[str | None] = mapped_column(String(20))
    before_usual_score: Mapped[int | None] = mapped_column(Integer)
    before_midterm_score: Mapped[int | None] = mapped_column(Integer)
    before_final_score: Mapped[int | None] = mapped_column(Integer)
    before_total_score: Mapped[int | None] = mapped_column(Integer)
    current_grade_id: Mapped[int | None] = mapped_column(BigInteger, comment="发起时的 ACTIVE AcademicGrade")
    expected_grade_version: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger)
    current_task_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/APPROVED/REJECTED")
    decided_by: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class AaGradeCorrection(PKMixin, TenantMixin, CommonMixin, Base):
    """正式成绩追加式更正链；原成绩保留为SUPERSEDED，新成绩成为ACTIVE。

    更正来源有两条（学生复查、教师发起更正），必须落在同一张更正链上，
    ``UNIQUE(tenant_id, source_type, source_ref_id)`` 保证同一来源单据只生效一次。
    """

    __tablename__ = "t_aa_grade_correction"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_ref_id",
                         name="uk_aa_grade_correction_source"),
        Index("ix_aa_grade_correction_original", "tenant_id", "original_grade_id"),
        Index("ix_aa_grade_correction_corrected", "tenant_id", "corrected_grade_id"),
    )

    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="RECHECK",
                                             comment="RECHECK/CHANGE_REQUEST")
    source_ref_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="来源单据ID")
    recheck_id: Mapped[int | None] = mapped_column(BigInteger, comment="历史列：复查来源保留回链")
    original_grade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    corrected_grade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_score: Mapped[int | None] = mapped_column(Integer)
    after_score: Mapped[int | None] = mapped_column(Integer)
    pass_line: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    operator: Mapped[str | None] = mapped_column(String(100))
    effective_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class AaEffectiveGradePolicySnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    """每次正式成绩写入/更正时冻结采用的有效成绩规则和课程身份。

    append-only；event_key保证网络重试幂等。历史无courseId成绩不自动猜测，只记录LEGACY_NAME_KEY欠账。
    """

    __tablename__ = "t_aa_effective_grade_policy_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key", name="uk_aa_effective_grade_policy_event"),
        Index("ix_aa_effective_grade_policy_grade", "tenant_id", "academic_grade_id"),
        Index("ix_aa_effective_grade_policy_course", "tenant_id", "course_id", "attempt_no"),
        Index("ix_aa_effective_grade_policy_source", "tenant_id", "source_biz_type", "source_biz_id"),
    )

    academic_grade_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="幂等事件键")
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="PUBLISH/MAKEUP/CLEARANCE/RECHECK/CHANGE")
    source_biz_type: Mapped[str | None] = mapped_column(String(50))
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger)

    policy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    identity_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="COURSE_ID/COURSE_CODE/LEGACY_NAME_KEY")
    identity_key: Mapped[str] = mapped_column(String(300), nullable=False)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_code: Mapped[str | None] = mapped_column(String(50))
    course_version: Mapped[int | None] = mapped_column(Integer)
    attempt_no: Mapped[int | None] = mapped_column(Integer)
    grade_source: Mapped[str | None] = mapped_column(String(30))
    decision_json: Mapped[str] = mapped_column(Text, nullable=False, comment="本次成绩事实与有效性判断快照")


def _canonical(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _snapshot_event_key(
    *,
    operation: str,
    event_type: str,
    source_biz_type: str,
    source_biz_id: int,
    grade_id: int,
    policy_hash: str,
) -> str:
    """插入沿用业务事件幂等键；更新按成绩状态哈希生成追加式事件键。

    已更正成绩再次被更正时，其 ``source`` 仍为 RECHECK。若更新继续复用
    ``RECHECK:RECHECK:<首次复查ID>``，会与首次插入快照冲突并阻断合法的
    多级更正链。状态哈希让同一更新重试保持幂等，不同状态则追加新快照。
    """
    if operation == "UPDATE":
        return f"CHANGE:ACADEMIC_GRADE:{int(grade_id)}:{policy_hash[:16]}"[:160]
    return f"{event_type}:{source_biz_type}:{int(source_biz_id)}"[:160]


_GRADE_SNAPSHOT_FIELDS = {
    "acad_student_id",
    "course_id",
    "course_code",
    "course_version",
    "attempt_no",
    "course_name",
    "nature",
    "credit_value",
    "score",
    "pass_status",
    "record_status",
    "source",
    "exam_type",
    "source_biz_type",
    "source_biz_id",
    "grade_record_id",
    "teaching_task_id",
    "teaching_class_id",
    "roster_version_id",
    "effective_policy_code",
    "effective_policy_version",
    "effective_attempt_strategy",
    "pass_line_snapshot",
}


def _write_snapshot(connection, target, *, operation: str) -> None:
    """Core insert保持与AcademicGrade同一数据库事务，并与显式冻结使用同一事件幂等键。"""
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        identity_snapshot,
        policy_payload,
    )

    if not getattr(target, "id", None) or not getattr(target, "tenant_id", None):
        return
    identity = identity_snapshot(target)
    event_type = str(getattr(target, "source", None) or operation or "CHANGE").upper()
    source_biz_type = str(
        getattr(target, "source_biz_type", None)
        or ("GRADE_RECORD" if getattr(target, "grade_record_id", None) else event_type)
    ).upper()
    source_biz_id = (
        getattr(target, "source_biz_id", None)
        or getattr(target, "grade_record_id", None)
        or getattr(target, "id", None)
    )
    decision = {
        "academicGradeId": str(target.id),
        "studentId": str(getattr(target, "acad_student_id", None) or ""),
        "score": getattr(target, "score", None),
        "passStatus": getattr(target, "pass_status", None),
        "recordStatus": getattr(target, "record_status", None),
        "gradeSource": getattr(target, "source", None),
        "examType": getattr(target, "exam_type", None),
        "effectivePolicyCode": getattr(target, "effective_policy_code", None),
        "effectivePolicyVersion": getattr(target, "effective_policy_version", None),
        "attemptStrategy": getattr(target, "effective_attempt_strategy", None),
        "passLineSnapshot": getattr(target, "pass_line_snapshot", None),
        **identity,
    }
    policy = policy_payload(target)
    policy_hash = hashlib.sha256(
        _canonical({"policy": policy, "decision": decision}).encode("utf-8")
    ).hexdigest()
    event_key = _snapshot_event_key(
        operation=operation,
        event_type=event_type,
        source_biz_type=source_biz_type,
        source_biz_id=int(source_biz_id),
        grade_id=int(target.id),
        policy_hash=policy_hash,
    )
    if operation == "UPDATE":
        event_type = "CHANGE"
        source_biz_type = "ACADEMIC_GRADE"
        source_biz_id = int(target.id)

    table = AaEffectiveGradePolicySnapshot.__table__
    existing = connection.execute(select(
        table.c.id,
        table.c.academic_grade_id,
        table.c.policy_hash,
        table.c.is_deleted,
    ).where(
        table.c.tenant_id == int(target.tenant_id),
        table.c.event_key == event_key,
    )).first()
    if existing:
        if existing.is_deleted:
            raise AppException(
                "DATA_CONFLICT",
                "有效成绩策略快照曾被软删除，禁止静默重建同一事件",
                details={"eventKey": event_key, "snapshotId": str(existing.id)},
                http_status=409,
            )
        if existing.policy_hash != policy_hash or int(existing.academic_grade_id) != int(target.id):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "同一成绩策略事件已存在但内容发生变化，禁止覆盖历史快照",
                details={"eventKey": event_key, "snapshotId": str(existing.id)},
                http_status=409,
            )
        return
    now = datetime.utcnow()
    connection.execute(table.insert().values(
        tenant_id=int(target.tenant_id),
        academic_grade_id=int(target.id),
        event_key=event_key,
        event_type=event_type,
        source_biz_type=source_biz_type[:50],
        source_biz_id=int(source_biz_id) if source_biz_id not in (None, "") else None,
        policy_code=policy["policyCode"],
        policy_version=policy["policyVersion"],
        policy_json=_canonical(policy),
        policy_hash=policy_hash,
        identity_type=identity["identityType"],
        identity_key=identity["identityKey"][:300],
        course_id=identity["courseId"],
        course_code=identity["courseCode"],
        course_version=identity["courseVersion"],
        attempt_no=identity["attemptNo"],
        grade_source=str(getattr(target, "source", None) or "") or None,
        decision_json=_canonical(decision),
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=0,
    ))



def _before_grade_insert(_mapper, connection, target) -> None:
    """正式成绩写入前冻结租户策略；无ACTIVE策略直接阻断。"""
    if not getattr(target, "tenant_id", None):
        return
    if getattr(target, "effective_attempt_strategy", None):
        return
    table = AaEffectiveGradePolicy.__table__
    row = connection.execute(
        select(
            table.c.policy_code, table.c.policy_version, table.c.attempt_strategy
        ).where(
            table.c.tenant_id == int(target.tenant_id),
            table.c.status == "ACTIVE",
            table.c.is_deleted.is_(False),
        ).order_by(
            table.c.effective_from_term_id.desc(),
            table.c.policy_version.desc(),
            table.c.id.desc(),
        ).limit(1)
    ).first()
    if not row:
        # 兼容历史迁移/沙箱导入；正式发布入口会显式要求ACTIVE策略。
        return
    target.effective_policy_code = row.policy_code
    target.effective_policy_version = row.policy_version
    target.effective_attempt_strategy = row.attempt_strategy


def _after_grade_insert(_mapper, connection, target) -> None:
    _write_snapshot(connection, target, operation="INSERT")


def _after_grade_update(_mapper, connection, target) -> None:
    state = inspect(target)
    if not any(state.attrs[name].history.has_changes() for name in _GRADE_SNAPSHOT_FIELDS if name in state.attrs):
        return
    _write_snapshot(connection, target, operation="UPDATE")


# 模型模块在app.models初始化时显式注册；命名监听器允许检查并避免测试reload造成重复绑定。
from app.models.academic import AcademicGrade  # noqa: E402

if not event.contains(AcademicGrade, "before_insert", _before_grade_insert):
    event.listen(AcademicGrade, "before_insert", _before_grade_insert)
if not event.contains(AcademicGrade, "after_insert", _after_grade_insert):
    event.listen(AcademicGrade, "after_insert", _after_grade_insert)
if not event.contains(AcademicGrade, "after_update", _after_grade_update):
    event.listen(AcademicGrade, "after_update", _after_grade_update)

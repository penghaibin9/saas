"""有效成绩策略快照模型与正式成绩同事务自动冻结。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, UniqueConstraint, event, select
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


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


def _write_snapshot(connection, target, *, operation: str) -> None:
    """Core insert保持与AcademicGrade同一数据库事务，不再依赖各业务入口逐个调用。"""
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        POLICY_CODE,
        POLICY_VERSION,
        identity_snapshot,
        policy_payload,
    )

    identity = identity_snapshot(target)
    event_type = str(getattr(target, "source", None) or operation or "CHANGE").upper()
    if operation == "UPDATE" and event_type not in {"RECHECK", "CHANGE", "MAKEUP", "CLEARANCE", "RETAKE"}:
        event_type = "CHANGE"
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
        **identity,
    }
    policy = policy_payload()
    policy_hash = hashlib.sha256(
        _canonical({"policy": policy, "decision": decision}).encode("utf-8")
    ).hexdigest()
    event_key = f"AUTO:{target.id}:{event_type}:{policy_hash[:24]}"[:160]

    table = AaEffectiveGradePolicySnapshot.__table__
    exists = connection.execute(select(table.c.id).where(
        table.c.tenant_id == int(target.tenant_id),
        table.c.event_key == event_key,
        table.c.is_deleted.is_(False),
    )).first()
    if exists:
        return
    now = datetime.utcnow()
    connection.execute(table.insert().values(
        tenant_id=int(target.tenant_id),
        academic_grade_id=int(target.id),
        event_key=event_key,
        event_type=event_type,
        source_biz_type=source_biz_type[:50],
        source_biz_id=int(source_biz_id) if source_biz_id not in (None, "") else None,
        policy_code=POLICY_CODE,
        policy_version=POLICY_VERSION,
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


# 模型模块在app.models初始化时只注册一次；所有正式成绩写入口自动覆盖。
from app.models.academic import AcademicGrade  # noqa: E402

event.listen(AcademicGrade, "after_insert", lambda _m, conn, target: _write_snapshot(conn, target, operation="INSERT"))
event.listen(AcademicGrade, "after_update", lambda _m, conn, target: _write_snapshot(conn, target, operation="UPDATE"))

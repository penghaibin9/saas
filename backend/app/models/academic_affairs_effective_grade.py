"""有效成绩策略快照模型与正式成绩同事务自动冻结。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, UniqueConstraint, event, inspect, select
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
}


def _write_snapshot(connection, target, *, operation: str) -> None:
    """Core insert保持与AcademicGrade同一数据库事务，并与显式冻结使用同一事件幂等键。"""
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import (
        POLICY_CODE,
        POLICY_VERSION,
        identity_snapshot,
        policy_payload,
    )

    if not getattr(target, "id", None) or not getattr(target, "tenant_id", None):
        return
    identity = identity_snapshot(target)
    event_type = str(getattr(target, "source", None) or operation or "CHANGE").upper()
    if operation == "UPDATE" and event_type not in {"RECHECK", "CHANGE", "MAKEUP", "CLEARANCE", "RETAKE", "DEFERRED"}:
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
    event_key = f"{event_type}:{source_biz_type}:{int(source_biz_id)}"[:160]

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


def _after_grade_insert(_mapper, connection, target) -> None:
    _write_snapshot(connection, target, operation="INSERT")


def _after_grade_update(_mapper, connection, target) -> None:
    state = inspect(target)
    if not any(state.attrs[name].history.has_changes() for name in _GRADE_SNAPSHOT_FIELDS if name in state.attrs):
        return
    _write_snapshot(connection, target, operation="UPDATE")


# 模型模块在app.models初始化时显式注册；命名监听器允许检查并避免测试reload造成重复绑定。
from app.models.academic import AcademicGrade  # noqa: E402

if not event.contains(AcademicGrade, "after_insert", _after_grade_insert):
    event.listen(AcademicGrade, "after_insert", _after_grade_insert)
if not event.contains(AcademicGrade, "after_update", _after_grade_update):
    event.listen(AcademicGrade, "after_update", _after_grade_update)

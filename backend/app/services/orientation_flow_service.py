"""迎新流程版本的最小发布底座（O2）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.models import (OrientationBatch, OrientationFlowConfig, OrientationFlowStep,
                        OrientationFlowVersion, OrientationStudentStep)

DEFAULT_ORIENTATION_STEPS = (
    ("ACTIVATE", "账号激活"),
    ("INFO", "信息核对"),
    ("MATERIAL", "材料上传"),
    ("PAYMENT", "缴费/绿色通道"),
    ("DORM", "宿舍确认"),
    ("CHECKIN", "现场报到"),
    ("CONFIRM", "学院确认"),
)

LEGACY_TO_CANONICAL_STATUS = {
    "TODO": "NOT_STARTED",
    "DOING": "IN_PROGRESS",
    "BLOCKED": "BLOCKED",
    "DONE": "DONE",
    "WAIVED": "WAIVED",
    "NOT_REQUIRED": "NOT_REQUIRED",
}
CANONICAL_TO_LEGACY_STATUS = {
    "NOT_STARTED": "TODO",
    "IN_PROGRESS": "DOING",
    "BLOCKED": "BLOCKED",
    "DONE": "DONE",
    "WAIVED": "WAIVED",
    "NOT_REQUIRED": "NOT_REQUIRED",
}


def ensure_published_flow_version(db, tenant_id: int) -> OrientationFlowVersion:
    """Return an equal snapshot, or publish V+1 when the future-batch draft changed."""
    configs = db.scalars(select(OrientationFlowConfig).where(
        OrientationFlowConfig.tenant_id == tenant_id,
        OrientationFlowConfig.is_deleted.is_(False),
    ).order_by(OrientationFlowConfig.sort_order, OrientationFlowConfig.id)).all()
    if configs:
        definitions = [
            (row.step_key, row.step_name, bool(row.enabled), bool(row.required),
             int(row.sort_order or 0), row.remark or None)
            for row in configs
        ]
    else:
        definitions = [
            (key, name, True, True, index, None)
            for index, (key, name) in enumerate(DEFAULT_ORIENTATION_STEPS)
        ]

    existing = db.scalars(select(OrientationFlowVersion).where(
        OrientationFlowVersion.tenant_id == tenant_id,
        OrientationFlowVersion.status == "PUBLISHED",
        OrientationFlowVersion.is_deleted.is_(False),
    ).order_by(OrientationFlowVersion.version_no.desc())).first()
    if existing:
        snapshot = db.scalars(select(OrientationFlowStep).where(
            OrientationFlowStep.tenant_id == tenant_id,
            OrientationFlowStep.flow_version_id == existing.id,
            OrientationFlowStep.is_deleted.is_(False),
        ).order_by(OrientationFlowStep.sort_order, OrientationFlowStep.id)).all()
        frozen = [
            (row.step_key, row.step_name, bool(row.enabled), bool(row.required),
             int(row.sort_order or 0), row.remark or None)
            for row in snapshot
        ]
        if frozen == definitions:
            return existing

    next_no = int(db.scalar(select(func.max(OrientationFlowVersion.version_no)).where(
        OrientationFlowVersion.tenant_id == tenant_id,
    )) or 0) + 1
    now = datetime.utcnow()
    version = OrientationFlowVersion(
        tenant_id=tenant_id,
        version_no=next_no,
        version_name=f"迎新流程 V{next_no}",
        status="PUBLISHED",
        source_type="MANUAL",
        published_at=now,
        remark="由批次首次启用自动发布；后续批次继续绑定该不可变快照",
    )
    db.add(version); db.flush()

    for key, name, enabled, required, sort_order, remark in definitions:
        db.add(OrientationFlowStep(
            tenant_id=tenant_id,
            flow_version_id=version.id,
            step_key=key,
            step_name=name,
            enabled=enabled,
            required=required,
            sort_order=sort_order,
            remark=remark,
        ))
    db.flush()
    return version


def _student_flow(db, student):
    """Resolve and freeze the flow snapshot used by one student process instance."""
    batch = db.get(OrientationBatch, int(student.batch_id))
    if (not batch or batch.is_deleted
            or int(batch.tenant_id) != int(student.tenant_id)):
        raise AppException("DATA_CONFLICT", "迎新学生关联的批次不存在或租户链不一致")
    if not batch.flow_version_id:
        # A draft batch becomes flow-bound when its first student process is created.  Activation
        # then keeps this id, so later draft-config edits cannot silently rewrite live instances.
        batch.flow_version_id = ensure_published_flow_version(db, int(student.tenant_id)).id
        db.flush()
    version = db.get(OrientationFlowVersion, int(batch.flow_version_id))
    if (not version or version.is_deleted
            or int(version.tenant_id) != int(student.tenant_id)
            or version.status != "PUBLISHED"):
        raise AppException("DATA_CONFLICT", "迎新批次绑定的流程版本无效")
    steps = db.scalars(select(OrientationFlowStep).where(
        OrientationFlowStep.tenant_id == student.tenant_id,
        OrientationFlowStep.flow_version_id == version.id,
        OrientationFlowStep.is_deleted.is_(False),
    ).order_by(OrientationFlowStep.sort_order, OrientationFlowStep.id)).all()
    if not steps:
        raise AppException("DATA_CONFLICT", "迎新流程版本没有可执行步骤")
    return version, steps


def ensure_student_steps(db, student, *, status_source: str = "LEGACY_STEPS_JSON"):
    """Create missing canonical step rows once; never re-import JSON over existing authority."""
    version, flow_steps = _student_flow(db, student)
    rows = db.scalars(select(OrientationStudentStep).where(
        OrientationStudentStep.tenant_id == student.tenant_id,
        OrientationStudentStep.orientation_student_id == student.id,
        OrientationStudentStep.is_deleted.is_(False),
    )).all()
    by_key = {row.step_key: row for row in rows}
    projection = dict(student.steps_json or {})
    now = datetime.utcnow()
    for flow_step in flow_steps:
        current = by_key.get(flow_step.step_key)
        if current:
            if (int(current.flow_version_id) != int(version.id)
                    or int(current.flow_step_id) != int(flow_step.id)):
                raise AppException("DATA_CONFLICT", "迎新学生步骤与冻结流程版本不一致")
            continue
        legacy = str(projection.get(flow_step.step_key) or "TODO").upper()
        canonical = LEGACY_TO_CANONICAL_STATUS.get(legacy)
        if canonical is None:
            raise AppException(
                "DATA_CONFLICT", f"步骤 {flow_step.step_key} 存在未知历史状态 {legacy}")
        if not flow_step.enabled and canonical == "NOT_STARTED":
            canonical = "NOT_REQUIRED"
        if canonical == "WAIVED":
            # A projection cannot prove waiver actor/evidence.  The migration rejects this case,
            # and runtime self-healing must follow the same fail-closed rule.
            raise AppException("DATA_CONFLICT", f"步骤 {flow_step.step_key} 的历史豁免缺少证据")
        current = OrientationStudentStep(
            tenant_id=student.tenant_id,
            orientation_student_id=student.id,
            flow_version_id=version.id,
            flow_step_id=flow_step.id,
            step_key=flow_step.step_key,
            status=canonical,
            status_source=status_source,
            blocked_reason=(student.blocked_reason if canonical == "BLOCKED" else None),
            status_changed_at=now,
        )
        db.add(current)
        by_key[flow_step.step_key] = current
    db.flush()
    ordered = [by_key[flow_step.step_key] for flow_step in flow_steps]
    _sync_steps_projection(student, ordered)
    return ordered


def initialize_batch_student_steps(db, batch_id: int, *, status_source: str = "LEGACY_STEPS_JSON") -> int:
    """Bulk initialize post-migration seed/import rows without turning JSON back into runtime truth."""
    from app.models import OrientationStudent

    batch = db.get(OrientationBatch, int(batch_id))
    if not batch or batch.is_deleted:
        raise AppException("DATA_CONFLICT", "迎新批次不存在")
    if not batch.flow_version_id:
        batch.flow_version_id = ensure_published_flow_version(db, int(batch.tenant_id)).id
        db.flush()
    version = db.get(OrientationFlowVersion, int(batch.flow_version_id))
    if (not version or version.is_deleted or version.status != "PUBLISHED"
            or int(version.tenant_id) != int(batch.tenant_id)):
        raise AppException("DATA_CONFLICT", "迎新批次绑定的流程版本无效")
    flow_steps = db.scalars(select(OrientationFlowStep).where(
        OrientationFlowStep.tenant_id == batch.tenant_id,
        OrientationFlowStep.flow_version_id == version.id,
        OrientationFlowStep.is_deleted.is_(False),
    ).order_by(OrientationFlowStep.sort_order, OrientationFlowStep.id)).all()
    students = db.execute(select(
        OrientationStudent.id, OrientationStudent.steps_json, OrientationStudent.blocked_reason,
    ).where(
        OrientationStudent.tenant_id == batch.tenant_id,
        OrientationStudent.batch_id == batch.id,
        OrientationStudent.is_deleted.is_(False),
    )).all()
    existing = set(db.execute(select(
        OrientationStudentStep.orientation_student_id, OrientationStudentStep.step_key,
    ).where(
        OrientationStudentStep.tenant_id == batch.tenant_id,
        OrientationStudentStep.orientation_student_id.in_([row.id for row in students]),
        OrientationStudentStep.is_deleted.is_(False),
    )).all()) if students else set()
    now = datetime.utcnow()
    mappings = []
    for student in students:
        projection = dict(student.steps_json or {})
        for flow_step in flow_steps:
            if (student.id, flow_step.step_key) in existing:
                continue
            legacy = str(projection.get(flow_step.step_key) or "TODO").upper()
            canonical = LEGACY_TO_CANONICAL_STATUS.get(legacy)
            if canonical is None or canonical == "WAIVED":
                raise AppException(
                    "DATA_CONFLICT",
                    f"学生 {student.id} 步骤 {flow_step.step_key} 的历史状态无法无损迁移：{legacy}",
                )
            if not flow_step.enabled and canonical == "NOT_STARTED":
                canonical = "NOT_REQUIRED"
            mappings.append({
                "tenant_id": batch.tenant_id,
                "orientation_student_id": student.id,
                "flow_version_id": version.id,
                "flow_step_id": flow_step.id,
                "step_key": flow_step.step_key,
                "status": canonical,
                "status_source": status_source,
                "blocked_reason": student.blocked_reason if canonical == "BLOCKED" else None,
                "status_changed_at": now,
            })
    table = OrientationStudentStep.__table__
    for start in range(0, len(mappings), 1000):
        db.execute(table.insert(), mappings[start:start + 1000])
    db.flush()
    return len(mappings)


def _sync_steps_projection(student, rows) -> dict:
    projection = {
        row.step_key: CANONICAL_TO_LEGACY_STATUS[row.status]
        for row in rows
    }
    student.steps_json = projection
    return projection


def canonical_student_steps(db, student):
    """Load complete canonical authority; runtime reads must never fall back to JSON."""
    version, flow_steps = _student_flow(db, student)
    rows = db.scalars(select(OrientationStudentStep).where(
        OrientationStudentStep.tenant_id == student.tenant_id,
        OrientationStudentStep.orientation_student_id == student.id,
        OrientationStudentStep.is_deleted.is_(False),
    )).all()
    by_key = {row.step_key: row for row in rows}
    expected_keys = {step.step_key for step in flow_steps}
    if set(by_key) != expected_keys:
        raise AppException("DATA_CONFLICT", "迎新学生权威步骤不完整，禁止回退读取 steps_json")
    ordered = []
    for flow_step in flow_steps:
        row = by_key[flow_step.step_key]
        if (int(row.flow_version_id) != int(version.id)
                or int(row.flow_step_id) != int(flow_step.id)):
            raise AppException("DATA_CONFLICT", "迎新学生步骤与冻结流程版本不一致")
        ordered.append(row)
    return ordered


def student_step_projection(db, student) -> dict:
    """Read exclusively from canonical rows and refresh the compatibility projection."""
    return _sync_steps_projection(student, canonical_student_steps(db, student))


def student_flow_steps(db, student) -> list[dict]:
    """Return the frozen, enabled step definitions for this student's own batch."""
    _, flow_steps = _student_flow(db, student)
    return [
        {"key": step.step_key, "label": step.step_name}
        for step in flow_steps if step.enabled
    ]


def set_student_step_status(
    db,
    student,
    step_key: str,
    status: str,
    *,
    status_source: str,
    source_biz_id: str | None = None,
    blocked_reason: str | None = None,
    waived_by: int | None = None,
    waive_reason: str | None = None,
    waive_evidence_ref: str | None = None,
):
    """Mutate canonical authority, then derive the legacy JSON projection from it."""
    canonical = str(status or "").upper()
    if canonical not in CANONICAL_TO_LEGACY_STATUS:
        raise AppException("VALIDATION_ERROR", f"未知迎新步骤状态：{status}")
    rows = canonical_student_steps(db, student)
    row = next((item for item in rows if item.step_key == step_key), None)
    if not row:
        raise AppException("VALIDATION_ERROR", f"当前冻结流程不包含步骤 {step_key}")
    if canonical == "WAIVED":
        reason = str(waive_reason or "").strip()
        if waived_by is None or len(reason) < 5 or not str(waive_evidence_ref or "").strip():
            raise AppException("VALIDATION_ERROR", "人工豁免必须记录操作人、至少 5 字原因和证据引用")
        row.waived_at = datetime.utcnow()
        row.waived_by = int(waived_by)
        row.waive_reason = reason
        row.waive_evidence_ref = str(waive_evidence_ref).strip()
    else:
        row.waived_at = None
        row.waived_by = None
        row.waive_reason = None
        row.waive_evidence_ref = None
    row.status = canonical
    row.status_source = status_source
    row.source_biz_id = str(source_biz_id) if source_biz_id is not None else None
    row.blocked_reason = str(blocked_reason).strip() if blocked_reason else None
    row.status_changed_at = datetime.utcnow()
    _sync_steps_projection(student, rows)
    return row

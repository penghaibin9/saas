"""Graduation student-record resolver shared by portal and miniapp.

The old mobile resolver selected the largest non-archived row. That can route a
student into a future DRAFT batch merely because it was created later. This
resolver prefers the single RUNNING batch and fails closed when more than one
current record is valid instead of silently guessing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import GraduationBatch, GraduationStudent
from app.services.db_service import _tid


def _active_by_date(batch: GraduationBatch | None, now: datetime) -> bool:
    if not batch or batch.is_deleted or batch.status == "VOIDED":
        return False
    start = batch.start_date
    end = batch.end_date
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return bool((not start or start <= now) and (not end or end >= now))


def _one_or_conflict(rows: list[GraduationStudent], message: str):
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        raise AppException("DATA_CONFLICT", message)
    return None


def resolve_current_gd_student(db, user: dict):
    """Resolve the current student's graduation record using batch truth.

    Priority:
    1. exactly one ACTIVE record whose batch is RUNNING;
    2. exactly one ACTIVE record inside its configured date window;
    3. exactly one non-archived, non-voided record;
    4. latest archived history record for read-only history.
    """
    from app.services.mobile_student_service import resolve_student

    master = resolve_student(db, user)
    if not master:
        return None

    base = [
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    ]
    rows: list[GraduationStudent] = []
    if getattr(master, "id", None) is not None:
        rows = list(db.scalars(select(GraduationStudent).where(
            *base, GraduationStudent.student_id == master.id,
        ).order_by(GraduationStudent.id.desc())).all())
    if not rows and getattr(master, "student_no", None):
        rows = list(db.scalars(select(GraduationStudent).where(
            *base, GraduationStudent.student_no == master.student_no,
        ).order_by(GraduationStudent.id.desc())).all())
    if not rows:
        name = (getattr(master, "real_name", None) or "").strip()
        if not name:
            return None
        named = list(db.scalars(select(GraduationStudent).where(
            *base, GraduationStudent.name == name,
        ).order_by(GraduationStudent.id.desc())).all())
        student_nos = {str(x.student_no or "") for x in named}
        if len(student_nos) > 1:
            raise AppException("DATA_CONFLICT", "存在同名毕业设计档案，无法安全确认当前学生，请联系管理员")
        rows = named
    if not rows:
        return None

    batch_ids = {int(x.batch_id) for x in rows if x.batch_id}
    batches = {}
    if batch_ids:
        batches = {int(x.id): x for x in db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == _tid(),
            GraduationBatch.id.in_(batch_ids),
            GraduationBatch.is_deleted.is_(False),
        )).all()}

    requested_batch_id = user.get("graduationBatchId") or user.get("batchId")
    if requested_batch_id not in (None, ""):
        try:
            requested_batch_id = int(requested_batch_id)
        except Exception:
            requested_batch_id = None
    if requested_batch_id:
        scoped = [x for x in rows if x.batch_id and int(x.batch_id) == requested_batch_id]
        return _one_or_conflict(scoped, "当前批次存在多个毕业设计档案，请联系管理员修正数据")

    running = [x for x in rows if x.batch_id and batches.get(int(x.batch_id))
               and batches[int(x.batch_id)].status == "RUNNING"]
    hit = _one_or_conflict(running, "存在多个进行中的毕业设计批次，请联系管理员保留唯一当前批次")
    if hit:
        return hit

    now = datetime.now(timezone.utc)
    dated = [x for x in rows if x.batch_id and _active_by_date(batches.get(int(x.batch_id)), now)]
    hit = _one_or_conflict(dated, "存在多个日期有效的毕业设计批次，请联系管理员修正批次时间")
    if hit:
        return hit

    current = [x for x in rows if x.stage != "ARCHIVED" and (
        not x.batch_id or not batches.get(int(x.batch_id))
        or batches[int(x.batch_id)].status != "VOIDED"
    )]
    hit = _one_or_conflict(current, "存在多个未归档毕业设计档案，系统已停止猜测，请联系管理员选择当前批次")
    if hit:
        return hit

    return sorted(rows, key=lambda x: int(x.id or 0), reverse=True)[0]


def install_mobile_resolver() -> None:
    """Compatibility bridge until mobile_student_service imports this directly."""
    from app.services import mobile_student_service
    mobile_student_service._resolve_gd_student = resolve_current_gd_student

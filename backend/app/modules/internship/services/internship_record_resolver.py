"""学生本人实习记录唯一解析器。

全仓库学生本人读/写业务必须经本模块解析，禁止按 studentId 查询后直接 `.first()`。
显式参数优先；未显式传入时读取请求级 X-Internship-Batch-Id 上下文。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.context import get_current_internship_batch_id
from app.core.exceptions import AppException, not_found
from app.models import InternshipBatch, InternshipRecord, StudentProfile
from app.modules.internship.services.internship_batch_context import (
    WRITE_FORBIDDEN_STATUSES,
    parse_required_batch_id,
)
from app.services.db_service import _tid

ACTIVE_RECORD_STATUSES = frozenset({"PREPARING", "READY", "ONBOARD", "ASSESSING"})


@dataclass
class StudentInternshipContext:
    student: StudentProfile | None = None
    record: InternshipRecord | None = None
    batch: InternshipBatch | None = None
    mode: str = "empty"
    candidates: list = field(default_factory=list)
    message: str = ""

    @property
    def record_id(self):
        return self.record.id if self.record else None


def _load_student(db, *, student=None, student_id=None, student_no=None) -> StudentProfile | None:
    if student is not None:
        return student
    if student_id is not None:
        stu = db.get(StudentProfile, int(student_id))
        if stu and not stu.is_deleted and stu.tenant_id == _tid():
            return stu
        return None
    sno = (student_no or "").strip()
    if not sno:
        return None
    return db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.student_no == sno,
        StudentProfile.is_deleted.is_(False))).first()


def _records_for_student(db, student_id: int) -> list[InternshipRecord]:
    return list(db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.student_id == student_id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id.desc())).all())


def _is_active_record(rec: InternshipRecord, batch: InternshipBatch | None) -> bool:
    if rec.status == "ARCHIVED" or rec.status not in ACTIVE_RECORD_STATUSES:
        return False
    if batch is None:
        return True
    if batch.is_deleted or batch.tenant_id != _tid():
        return False
    return batch.status == "RUNNING"


def _effective_batch_id(batch_id):
    if batch_id is not None and str(batch_id).strip() != "":
        return batch_id
    return get_current_internship_batch_id()


def resolve_student_internship_context(
    db,
    *,
    student=None,
    student_id=None,
    student_no=None,
    batch_id=None,
    for_write: bool = False,
) -> StudentInternshipContext:
    stu = _load_student(db, student=student, student_id=student_id, student_no=student_no)
    if not stu:
        if for_write:
            raise not_found("未找到当前学生档案")
        return StudentInternshipContext(mode="empty", message="未找到学生档案")

    rows = _records_for_student(db, stu.id)
    if not rows:
        if for_write:
            raise not_found("当前学生尚无实习档案")
        return StudentInternshipContext(student=stu, mode="empty", message="你暂无实习记录")

    batch_map: dict[int, InternshipBatch] = {}
    bids = [r.batch_id for r in rows if r.batch_id]
    if bids:
        for batch in db.scalars(select(InternshipBatch).where(
                InternshipBatch.id.in_(bids))).all():
            batch_map[batch.id] = batch

    selected_batch_id = _effective_batch_id(batch_id)
    if selected_batch_id is not None and str(selected_batch_id).strip() != "":
        bid = parse_required_batch_id(selected_batch_id)
        matched = [row for row in rows if row.batch_id == bid]
        if not matched:
            raise not_found("该批次下无你的实习记录")
        record = matched[0]
        batch = batch_map.get(bid) or db.get(InternshipBatch, bid)
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("实习批次不存在或不在当前数据范围内")
        if for_write:
            if record.status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档实习记录禁止业务写入")
            if batch.status in WRITE_FORBIDDEN_STATUSES:
                raise AppException(
                    "DATA_CONFLICT",
                    f"批次状态为「{batch.status}」，禁止请假/打卡/周报/求助等写操作",
                )
            if record.status not in ACTIVE_RECORD_STATUSES:
                raise AppException(
                    "DATA_CONFLICT", f"当前实习状态「{record.status}」不允许业务写入")
        mode = "active" if _is_active_record(record, batch) else "history"
        if for_write and mode != "active":
            raise AppException("DATA_CONFLICT", "写操作只能针对进行中的实习批次")
        return StudentInternshipContext(
            student=stu, record=record, batch=batch, mode=mode,
            message="" if mode == "active" else "当前为历史实习记录（只读）",
        )

    active = []
    history = []
    for record in rows:
        batch = batch_map.get(record.batch_id) if record.batch_id else None
        if _is_active_record(record, batch):
            active.append((record, batch))
        else:
            history.append((record, batch))

    if len(active) > 1:
        candidates = [
            {
                "recordId": str(record.id),
                "batchId": str(record.batch_id or ""),
                "batchName": (batch.batch_name if batch else "") or "",
                "status": record.status,
            }
            for record, batch in active
        ]
        if for_write:
            raise AppException(
                "NEED_SELECT",
                "你有多条进行中的实习记录，请先选择批次后再操作",
                details={"candidates": candidates},
            )
        return StudentInternshipContext(
            student=stu, mode="need_select", candidates=candidates,
            message="你有多条进行中的实习记录，请选择批次",
        )

    if len(active) == 1:
        record, batch = active[0]
        return StudentInternshipContext(
            student=stu, record=record, batch=batch, mode="active")

    if for_write:
        raise AppException(
            "DATA_CONFLICT",
            "当前没有进行中的实习批次，无法发起请假/打卡/周报/求助等写操作",
        )
    if history:
        record, batch = history[0]
        return StudentInternshipContext(
            student=stu, record=record, batch=batch, mode="history",
            candidates=[
                {
                    "recordId": str(item.id),
                    "batchId": str(item.batch_id or ""),
                    "batchName": (item_batch.batch_name if item_batch else "") or "",
                    "status": item.status,
                }
                for item, item_batch in history
            ],
            message="当前为历史实习记录（只读）",
        )
    return StudentInternshipContext(student=stu, mode="empty", message="你暂无实习记录")


def require_active_student_record(db, user=None, *, batch_id=None, student_no=None,
                                  student_id=None, student=None):
    sno = student_no or (user or {}).get("studentNo")
    ctx = resolve_student_internship_context(
        db, student=student, student_id=student_id, student_no=sno,
        batch_id=batch_id, for_write=True,
    )
    return ctx.record, ctx.student


def resolve_optional_student_record(db, user=None, *, batch_id=None, student_no=None,
                                    student=None, student_id=None):
    sno = student_no or (user or {}).get("studentNo")
    ctx = resolve_student_internship_context(
        db, student=student, student_id=student_id, student_no=sno,
        batch_id=batch_id, for_write=False,
    )
    return ctx.record, ctx.student, ctx

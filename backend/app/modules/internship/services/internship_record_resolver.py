"""学生本人实习记录唯一解析器（P0-1）。

全仓库学生本人读/写业务必须经本模块解析，禁止「按 studentId 查询后直接 .first()」。

规则：
- 显式传入 batchId 时严格校验归属；
- 仅一条进行中记录时可自动选择；
- 多条进行中记录时必须让学生选择（NEED_SELECT）；
- 无进行中记录时仅允许历史只读模式；
- 写操作禁止落到历史批次（CLOSED/ARCHIVED/VOIDED）或已归档学生记录。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipBatch, InternshipRecord, StudentProfile
from app.modules.internship.services.internship_batch_context import (
    WRITE_FORBIDDEN_STATUSES,
    parse_required_batch_id,
)
from app.services.db_service import _tid

# 进行中（非归档）学生实习状态
ACTIVE_RECORD_STATUSES = frozenset({"PREPARING", "READY", "ONBOARD", "ASSESSING"})


@dataclass
class StudentInternshipContext:
    """解析结果。"""
    student: StudentProfile | None = None
    record: InternshipRecord | None = None
    batch: InternshipBatch | None = None
    mode: str = "empty"  # active | history | need_select | empty
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
    if rec.status == "ARCHIVED":
        return False
    if rec.status not in ACTIVE_RECORD_STATUSES:
        return False
    if batch is None:
        # 无批次元数据时，仅按学生记录状态视为进行中（历史脏数据人工映射前）
        return True
    if batch.is_deleted or batch.tenant_id != _tid():
        return False
    # 批次已结束/归档/作废 → 不可作为写操作目标；读时可进 history
    return batch.status == "RUNNING"


def resolve_student_internship_context(
    db,
    *,
    student=None,
    student_id=None,
    student_no=None,
    batch_id=None,
    for_write: bool = False,
) -> StudentInternshipContext:
    """解析学生当前应操作的实习记录。

    for_write=True：必须落到唯一进行中记录，且批次 RUNNING；否则抛错。
    for_write=False：可返回历史只读记录（单条历史时自动选最近一条）。
    """
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
        for b in db.scalars(select(InternshipBatch).where(InternshipBatch.id.in_(bids))).all():
            batch_map[b.id] = b

    # 显式批次：严格校验
    if batch_id is not None and str(batch_id).strip() != "":
        bid = parse_required_batch_id(batch_id)
        matched = [r for r in rows if r.batch_id == bid]
        if not matched:
            raise not_found("该批次下无你的实习记录")
        rec = matched[0]
        batch = batch_map.get(bid) or db.get(InternshipBatch, bid)
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("实习批次不存在或不在当前数据范围内")
        if for_write:
            if rec.status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档实习记录禁止业务写入")
            if batch.status in WRITE_FORBIDDEN_STATUSES:
                raise AppException(
                    "DATA_CONFLICT",
                    f"批次状态为「{batch.status}」，禁止请假/打卡/周报/求助等写操作",
                )
            if rec.status not in ACTIVE_RECORD_STATUSES:
                raise AppException("DATA_CONFLICT", f"当前实习状态「{rec.status}」不允许业务写入")
        mode = "active" if _is_active_record(rec, batch) else "history"
        if for_write and mode != "active":
            raise AppException("DATA_CONFLICT", "写操作只能针对进行中的实习批次")
        return StudentInternshipContext(
            student=stu, record=rec, batch=batch, mode=mode,
            message="" if mode == "active" else "当前为历史实习记录（只读）",
        )

    active = []
    history = []
    for r in rows:
        b = batch_map.get(r.batch_id) if r.batch_id else None
        if _is_active_record(r, b):
            active.append((r, b))
        else:
            history.append((r, b))

    if len(active) > 1:
        cands = [
            {
                "recordId": str(r.id),
                "batchId": str(r.batch_id or ""),
                "batchName": (b.batch_name if b else "") or "",
                "status": r.status,
            }
            for r, b in active
        ]
        if for_write:
            raise AppException(
                "NEED_SELECT",
                "你有多条进行中的实习记录，请先选择批次后再操作",
                details={"candidates": cands},
            )
        return StudentInternshipContext(
            student=stu, mode="need_select", candidates=cands,
            message="你有多条进行中的实习记录，请选择批次",
        )

    if len(active) == 1:
        rec, batch = active[0]
        return StudentInternshipContext(
            student=stu, record=rec, batch=batch, mode="active",
        )

    # 无进行中：历史只读
    if for_write:
        raise AppException(
            "DATA_CONFLICT",
            "当前没有进行中的实习批次，无法发起请假/打卡/周报/求助等写操作",
        )
    if history:
        rec, batch = history[0]  # 已按 id desc
        return StudentInternshipContext(
            student=stu, record=rec, batch=batch, mode="history",
            candidates=[
                {
                    "recordId": str(r.id),
                    "batchId": str(r.batch_id or ""),
                    "batchName": (b.batch_name if b else "") or "",
                    "status": r.status,
                }
                for r, b in history
            ],
            message="当前为历史实习记录（只读）",
        )
    return StudentInternshipContext(student=stu, mode="empty", message="你暂无实习记录")


def require_active_student_record(db, user=None, *, batch_id=None, student_no=None,
                                  student_id=None, student=None):
    """学生写操作便捷入口：返回 (record, student)，失败抛错。"""
    sno = student_no or (user or {}).get("studentNo")
    ctx = resolve_student_internship_context(
        db, student=student, student_id=student_id, student_no=sno,
        batch_id=batch_id, for_write=True,
    )
    return ctx.record, ctx.student


def resolve_optional_student_record(db, user=None, *, batch_id=None, student_no=None,
                                    student=None, student_id=None):
    """学生读操作便捷入口：返回 (record, student, ctx)，不强制抛错。"""
    sno = student_no or (user or {}).get("studentNo")
    ctx = resolve_student_internship_context(
        db, student=student, student_id=student_id, student_no=sno,
        batch_id=batch_id, for_write=False,
    )
    return ctx.record, ctx.student, ctx

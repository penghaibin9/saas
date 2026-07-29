"""选课轮次唯一公开 Service。

原只读 DTO 和列表能力保存在 ``academic_affairs_selection_round_core_service``；本文件显式收口：
- 新建、开启、关闭、摇号均在同一事务校验所属学期未封存；
- 同一批次同时只能开启一个轮次；
- 摇号先原子抢占 CLOSED→DRAWN，再锁定课程和待抽签记录；
- 排序使用 SHA-256(roundId:recordId)，跨进程、跨重试可复核；
- 容量更新保持数据库原子条件，不允许超卖。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_round_core_service as _core
from . import academic_affairs_selection_service as selection_service

MODES = _core.MODES


def __getattr__(name):
    return getattr(_core, name)


def _writable_batch(db, batch_id):
    batch = selection_service._core._get_batch(db, int(batch_id))
    selection_service._guard_batch_writable(db, batch)
    return batch


def _draw_key(round_id: int, record_id: int) -> str:
    return hashlib.sha256(f"{int(round_id)}:{int(record_id)}".encode("utf-8")).hexdigest()


def create_round(user, batch_id, body) -> dict:
    from app.models import AaSelectionRound

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _writable_batch(db, batch_id)
        if batch.status in {"LOCKED", "ARCHIVED"}:
            raise _core._invalid("批次已锁定/归档，不可新增轮次")
        mode = str(getattr(body, "mode", None) or "FCFS").upper()
        if mode not in MODES:
            raise _core._bad("轮次模式仅支持 FCFS(先到先得)/LOTTERY(抽签)")
        name = str(getattr(body, "roundName", None) or "").strip()
        if not name:
            raise _core._bad("轮次名称必填")
        maximum = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.batch_id == batch.id,
            AaSelectionRound.is_deleted.is_(False),
        ).with_for_update().count()
        row = AaSelectionRound(
            tenant_id=_core._tid(),
            batch_id=batch.id,
            round_no=int(maximum or 0) + 1,
            round_name=name,
            mode=mode,
            allow_enroll=bool(getattr(body, "allowEnroll", True)),
            allow_drop=bool(getattr(body, "allowDrop", True)),
            start_at=selection_service._core._parse_dt(getattr(body, "startAt", None)),
            end_at=selection_service._core._parse_dt(getattr(body, "endAt", None)),
            status="DRAFT",
        )
        if row.start_at and row.end_at and row.end_at <= row.start_at:
            raise _core._bad("轮次结束时间必须晚于开始时间")
        db.add(row)
        db.flush()
        _core._audit(db, row.id, "ROUND_CREATE", f"第{row.round_no}轮 {name}({mode})")
        db.commit()
        return _core._round_dto(row)


def open_round(user, round_id) -> dict:
    from app.models import AaSelectionRound

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        row = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == int(round_id),
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("轮次不存在")
        batch = _writable_batch(db, row.batch_id)
        if row.status not in {"DRAFT", "CLOSED"}:
            raise _core._invalid("仅草稿/已关闭轮次可开启")
        if batch.status != "OPEN":
            raise _core._invalid("批次未处于开放选课状态，不可开轮")
        other = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.batch_id == row.batch_id,
            AaSelectionRound.status == "OPEN",
            AaSelectionRound.id != row.id,
            AaSelectionRound.is_deleted.is_(False),
        ).first()
        if other:
            raise _core._invalid(f"第{other.round_no}轮（{other.round_name}）尚未关闭，同批次同时只能开一个轮次")
        now = datetime.utcnow()
        if row.end_at and row.end_at <= now:
            raise _core._invalid("该轮次结束时间已过，不能重新开启")
        row.status = "OPEN"
        row.start_at = row.start_at or now
        _core._audit(db, row.id, "ROUND_OPEN", f"第{row.round_no}轮开启")
        db.commit()
        return _core._round_dto(row)


def close_round(user, round_id) -> dict:
    from app.models import AaSelectionRound

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        row = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == int(round_id),
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("轮次不存在")
        _writable_batch(db, row.batch_id)
        if row.status != "OPEN":
            raise _core._invalid("仅开启中的轮次可关闭")
        row.status = "CLOSED"
        row.end_at = row.end_at or datetime.utcnow()
        _core._audit(db, row.id, "ROUND_CLOSE", f"第{row.round_no}轮关闭")
        db.commit()
        return _core._round_dto(row)


def draw_round(user, round_id) -> dict:
    """确定性摇号：相同轮次和申请记录在任何进程中排序结果完全一致。"""
    from app.models import AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        row = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == int(round_id),
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("轮次不存在")
        _writable_batch(db, row.batch_id)
        if row.mode != "LOTTERY":
            raise _core._invalid("仅抽签轮次可摇号")
        claimed = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == row.id,
            AaSelectionRound.tenant_id == _core._tid(),
            AaSelectionRound.status == "CLOSED",
        ).update({AaSelectionRound.status: "DRAWN"}, synchronize_session=False)
        if not claimed:
            raise _core._invalid("请先关闭轮次再摇号（开启中不可摇号，已摇号不可重摇）")
        row.status = "DRAWN"

        pending = db.scalars(select(AaSelectionRecord).where(
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.round_id == row.id,
            AaSelectionRecord.status == selection_service._REC_PENDING,
            AaSelectionRecord.is_deleted.is_(False),
        ).with_for_update()).all()
        by_course = {}
        for record in pending:
            by_course.setdefault(int(record.selection_course_id), []).append(record)

        results = []
        total_win = total_lose = 0
        for course_id, records in sorted(by_course.items()):
            course = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.id == int(course_id),
                AaSelectionCourse.tenant_id == _core._tid(),
                AaSelectionCourse.is_deleted.is_(False),
            ).with_for_update().first()
            remaining = max(0, int(course.capacity or 0) - int(course.selected_count or 0)) if course else 0
            ordered = sorted(records, key=lambda item: (_draw_key(row.id, item.id), int(item.id)))
            winners, losers = ordered[:remaining], ordered[remaining:]
            if winners and course:
                count = len(winners)
                updated = db.query(AaSelectionCourse).filter(
                    AaSelectionCourse.id == course.id,
                    AaSelectionCourse.tenant_id == _core._tid(),
                    AaSelectionCourse.status == selection_service._COURSE_OPEN,
                    AaSelectionCourse.selected_count + count <= AaSelectionCourse.capacity,
                ).update({
                    AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + count,
                }, synchronize_session=False)
                if not updated:
                    losers, winners = ordered, []
            now = datetime.utcnow()
            for winner in winners:
                winner.status = selection_service._REC_SELECTED
                winner.enrolled_at = now
            for loser in losers:
                loser.status = selection_service._REC_LOST
            total_win += len(winners)
            total_lose += len(losers)
            results.append({
                "selectionCourseId": str(course_id),
                "courseName": course.course_name if course else None,
                "applicants": len(records),
                "winners": len(winners),
                "losers": len(losers),
                "remainingBefore": remaining,
                "algorithm": "SHA256_ROUND_RECORD_V1",
            })

        _core._audit(
            db,
            row.id,
            "ROUND_DRAW",
            f"第{row.round_no}轮摇号：{len(by_course)}门课，中签{total_win}/落签{total_lose};algorithm=SHA256_ROUND_RECORD_V1",
        )
        db.commit()
        return {
            "roundId": str(row.id),
            "roundNo": row.round_no,
            "algorithm": "SHA256_ROUND_RECORD_V1",
            "courses": results,
            "totalWinners": total_win,
            "totalLosers": total_lose,
        }

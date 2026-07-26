"""选课轮次服务学期写保护层。

轮次属于选课批次的子状态机。新建、开轮、关轮、摇号必须在同一写事务内校验所属学期未归档。
除此之外，严格保留原服务的函数名、开放规则、确定性摇号、容量原子更新、DTO和审计口径。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from . import academic_affairs_selection_round_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def _writable_batch(db, batch_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    batch = _legacy._get_batch(db, int(batch_id))
    guard_term_writable(db, batch.term_id)
    return batch


def create_round(user, batch_id, body) -> dict:
    from app.models import AaSelectionRound

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        batch = _writable_batch(db, batch_id)
        if batch.status in ("LOCKED", "ARCHIVED"):
            raise _legacy._invalid("批次已锁定/归档，不可新增轮次")
        mode = (getattr(body, "mode", None) or "FCFS").upper()
        if mode not in _legacy.MODES:
            raise _legacy._bad("轮次模式仅支持 FCFS(先到先得)/LOTTERY(抽签)")
        name = (getattr(body, "roundName", None) or "").strip()
        if not name:
            raise _legacy._bad("轮次名称必填")
        maximum = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _legacy._tid(),
            AaSelectionRound.batch_id == batch.id,
            AaSelectionRound.is_deleted.is_(False),
        ).count()
        row = AaSelectionRound(
            tenant_id=_legacy._tid(),
            batch_id=batch.id,
            round_no=maximum + 1,
            round_name=name,
            mode=mode,
            allow_enroll=bool(getattr(body, "allowEnroll", True)),
            allow_drop=bool(getattr(body, "allowDrop", True)),
            status="DRAFT",
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, row.id, "ROUND_CREATE", f"第{row.round_no}轮 {name}({mode})")
        db.commit()
        return _legacy._round_dto(row)


def open_round(user, round_id) -> dict:
    from app.models import AaSelectionRound

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        row = _legacy._get_round(db, round_id)
        batch = _writable_batch(db, row.batch_id)
        if row.status not in ("DRAFT", "CLOSED"):
            raise _legacy._invalid("仅草稿/已关闭轮次可开启")
        if batch.status != "OPEN":
            raise _legacy._invalid("批次未处于开放选课状态，不可开轮")
        other = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _legacy._tid(),
            AaSelectionRound.batch_id == row.batch_id,
            AaSelectionRound.status == "OPEN",
            AaSelectionRound.id != row.id,
            AaSelectionRound.is_deleted.is_(False),
        ).first()
        if other:
            raise _legacy._invalid(
                f"第{other.round_no}轮（{other.round_name}）尚未关闭，同批次同时只能开一个轮次"
            )
        row.status = "OPEN"
        _legacy._audit(db, row.id, "ROUND_OPEN", f"第{row.round_no}轮开启")
        db.commit()
        return _legacy._round_dto(row)


def close_round(user, round_id) -> dict:
    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        row = _legacy._get_round(db, round_id)
        _writable_batch(db, row.batch_id)
        if row.status != "OPEN":
            raise _legacy._invalid("仅开启中的轮次可关闭")
        row.status = "CLOSED"
        _legacy._audit(db, row.id, "ROUND_CLOSE", f"第{row.round_no}轮关闭")
        db.commit()
        return _legacy._round_dto(row)


def draw_round(user, round_id) -> dict:
    """原确定性抽签算法 + 同事务归档写保护。"""
    from app.models import AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    with _legacy.session() as db:
        _legacy._require_manage_scope(_legacy._ctx(user, db))
        row = _legacy._get_round(db, round_id)
        _writable_batch(db, row.batch_id)
        if row.mode != "LOTTERY":
            raise _legacy._invalid("仅抽签轮次可摇号")
        grabbed = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == row.id,
            AaSelectionRound.tenant_id == _legacy._tid(),
            AaSelectionRound.status == "CLOSED",
        ).update({AaSelectionRound.status: "DRAWN"}, synchronize_session=False)
        if not grabbed:
            raise _legacy._invalid("请先关闭轮次再摇号（开启中不可摇号，已摇号不可重摇）")

        pending = db.scalars(select(AaSelectionRecord).where(
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.round_id == row.id,
            AaSelectionRecord.status == _legacy._REC_PENDING,
            AaSelectionRecord.is_deleted.is_(False),
        )).all()
        by_course = {}
        for record in pending:
            by_course.setdefault(int(record.selection_course_id), []).append(record)

        results = []
        total_win = 0
        total_lose = 0
        for course_id, records in sorted(by_course.items()):
            course = db.get(AaSelectionCourse, course_id)
            remaining = max(
                0,
                int(course.capacity or 0) - int(course.selected_count or 0),
            ) if course else 0
            if len(records) <= remaining:
                winners, losers = records, []
            else:
                ordered = sorted(records, key=lambda item: (hash((item.id, row.id)), item.id))
                winners, losers = ordered[:remaining], ordered[remaining:]
            if winners and course:
                count = len(winners)
                updated = db.query(AaSelectionCourse).filter(
                    AaSelectionCourse.id == course.id,
                    AaSelectionCourse.tenant_id == _legacy._tid(),
                    AaSelectionCourse.selected_count + count <= AaSelectionCourse.capacity,
                ).update({
                    AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + count,
                }, synchronize_session=False)
                if not updated:
                    losers, winners = winners + losers, []
            for winner in winners:
                winner.status = _legacy._REC_SELECTED
                winner.enrolled_at = datetime.utcnow()
            for loser in losers:
                loser.status = _legacy._REC_LOST
            total_win += len(winners)
            total_lose += len(losers)
            results.append({
                "selectionCourseId": str(course_id),
                "courseName": course.course_name if course else None,
                "applicants": len(records),
                "winners": len(winners),
                "losers": len(losers),
                "remainingBefore": remaining,
            })

        _legacy._audit(
            db,
            row.id,
            "ROUND_DRAW",
            f"第{row.round_no}轮摇号：{len(by_course)}门课，中签{total_win}/落签{total_lose}",
        )
        db.commit()
        return {
            "roundId": str(row.id),
            "roundNo": row.round_no,
            "courses": results,
            "totalWinners": total_win,
            "totalLosers": total_lose,
        }


_legacy.create_round = create_round
_legacy.open_round = open_round
_legacy.close_round = close_round
_legacy.draw_round = draw_round

"""选课轮次服务学期写保护层。

轮次属于选课批次的子状态机。新建、开轮、关轮、摇号必须在同一写事务内校验所属学期未归档，
避免主批次入口已只读但轮次服务仍可继续改名单。
"""
from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_selection_round_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def _writable_batch(db, batch_id):
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    batch = _legacy._get_batch(db, int(batch_id))
    guard_term_writable(db, batch.term_id)
    return batch


def create_round(user, batch_id, body):
    from app.models import AaSelectionRound

    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        batch = _writable_batch(db, batch_id)
        if batch.status not in ("DRAFT", "OPEN"):
            raise _legacy._invalid("仅DRAFT/OPEN批次可新增轮次")
        mode = str(getattr(body, "mode", None) or "FCFS").upper()
        if mode not in ("FCFS", "LOTTERY"):
            raise _legacy._bad("mode仅支持FCFS/LOTTERY")
        round_no = getattr(body, "roundNo", None)
        if not round_no:
            maximum = db.scalar(select(__import__("sqlalchemy").func.max(AaSelectionRound.round_no)).where(
                AaSelectionRound.tenant_id == _legacy._tid(),
                AaSelectionRound.batch_id == batch.id,
                AaSelectionRound.is_deleted.is_(False),
            )) or 0
            round_no = int(maximum) + 1
        duplicate = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _legacy._tid(),
            AaSelectionRound.batch_id == batch.id,
            AaSelectionRound.round_no == int(round_no),
            AaSelectionRound.is_deleted.is_(False),
        ).first()
        if duplicate:
            raise _legacy._conflict(f"第{round_no}轮已存在")
        row = AaSelectionRound(
            tenant_id=_legacy._tid(),
            batch_id=batch.id,
            round_no=int(round_no),
            round_name=getattr(body, "roundName", None) or f"第{round_no}轮",
            mode=mode,
            start_at=_legacy._parse_dt(getattr(body, "startAt", None)),
            end_at=_legacy._parse_dt(getattr(body, "endAt", None)),
            max_courses=getattr(body, "maxCourses", None),
            max_credits=getattr(body, "maxCredits", None),
            allow_drop=bool(getattr(body, "allowDrop", True)),
            allow_cross_major=bool(getattr(body, "allowCrossMajor", False)),
            status="DRAFT",
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, row.id, "SELECTION_ROUND_CREATE", f"batch={batch.id};mode={mode}")
        db.commit()
        return _legacy._round_dto(row)


def open_round(user, round_id):
    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        row = _legacy._get_round(db, int(round_id))
        batch = _writable_batch(db, row.batch_id)
        if row.status != "DRAFT":
            raise _legacy._invalid("仅DRAFT轮次可开放")
        if batch.status not in ("DRAFT", "OPEN"):
            raise _legacy._invalid("批次当前状态不可开放轮次")
        row.status = "OPEN"
        if batch.status == "DRAFT":
            batch.status = "OPEN"
        _legacy._audit(db, row.id, "SELECTION_ROUND_OPEN", "开放")
        db.commit()
        return _legacy._round_dto(row)


def close_round(user, round_id):
    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        row = _legacy._get_round(db, int(round_id))
        _writable_batch(db, row.batch_id)
        if row.status != "OPEN":
            raise _legacy._invalid("仅OPEN轮次可关闭")
        row.status = "CLOSED"
        _legacy._audit(db, row.id, "SELECTION_ROUND_CLOSE", "关闭")
        db.commit()
        return _legacy._round_dto(row)


def draw_lottery(user, round_id, seed=None):
    """LOTTERY CLOSED→DRAWN；保留原确定性随机与容量分配口径。"""
    from app.models import AaSelectionCourse, AaSelectionRecord

    with _legacy.session() as db:
        _legacy._require_manage(_legacy._ctx(user, db))
        row = _legacy._get_round(db, int(round_id))
        _writable_batch(db, row.batch_id)
        if row.mode != "LOTTERY":
            raise _legacy._invalid("仅LOTTERY轮次可摇号")
        if row.status == "DRAWN":
            return _legacy._round_dto(row)
        if row.status != "CLOSED":
            raise _legacy._invalid("须先关闭轮次再摇号")
        records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _legacy._tid(),
            AaSelectionRecord.round_id == row.id,
            AaSelectionRecord.status == "PENDING_LOTTERY",
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        by_course = {}
        for record in records:
            by_course.setdefault(int(record.selection_course_id), []).append(record)
        rng = random.Random(str(seed) if seed is not None else f"{row.batch_id}:{row.id}")
        won = lost = 0
        for course_id, candidates in by_course.items():
            course = db.get(AaSelectionCourse, int(course_id))
            if not course or course.is_deleted or course.tenant_id != _legacy._tid() or course.status != "OPEN":
                for record in candidates:
                    record.status = "LOTTERY_LOST"
                    lost += 1
                continue
            remain = max(0, int(course.capacity or 0) - int(course.selected_count or 0))
            ordered = list(candidates)
            rng.shuffle(ordered)
            for index, record in enumerate(ordered):
                if index < remain:
                    record.status = "SELECTED"
                    record.selected_at = datetime.utcnow()
                    course.selected_count = int(course.selected_count or 0) + 1
                    won += 1
                else:
                    record.status = "LOTTERY_LOST"
                    lost += 1
        row.status = "DRAWN"
        _legacy._audit(db, row.id, "SELECTION_ROUND_DRAW", f"won={won};lost={lost}")
        db.commit()
        return {**_legacy._round_dto(row), "won": won, "lost": lost}


_legacy.create_round = create_round
_legacy.open_round = open_round
_legacy.close_round = close_round
_legacy.draw_lottery = draw_lottery

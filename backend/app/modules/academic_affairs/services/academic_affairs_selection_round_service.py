"""选课轮次与抽签服务（SM-09 增强层）。

对标商业教务系统（强智《智慧教学服务平台操作手册》印刷页 224-250）的多轮次选课：
轮次维护（预选/正选/补退选）、抽签摇号、"可选可退/只可选/只可退"三态控制。

设计纪律：
- 无轮次的批次保持既有先到先得行为分毫不动（向后兼容，存量选课测试原样绿）。
- 同批次至多一个 OPEN 轮次（开轮时校验，409 拦截）。
- 摇号为确定性算法：按 (记录id, 轮次id) 派生序取前 N 名，同输入同输出，
  可复核可审计——摇号结果必须经得起学生和家长质询，不能是"黑盒随机"。
  （强智另有"志愿抽签/投积分"两种模式，本波只落"随机抽签"；
    另两种登记在案作为 mode 枚举扩展位，不做假实现。）
- 摇号只在 CLOSED 轮次上执行一次（DRAWN 终态），中签写容量走守护更新不超容。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_selection_service import (
    _REC_LOST, _REC_PENDING, _REC_SELECTED, _ctx, _get_batch, _require_manage_scope)
from app.services.db_service import _iso, _tid, session

MODES = ("FCFS", "LOTTERY")


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_SELECTION_ROUND", biz_id=biz_id,
                             action=action, operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _round_dto(r):
    return {"roundId": str(r.id), "batchId": str(r.batch_id), "roundNo": r.round_no,
            "roundName": r.round_name, "mode": r.mode,
            "startAt": _iso(r.start_at), "endAt": _iso(r.end_at),
            "allowEnroll": bool(r.allow_enroll), "allowDrop": bool(r.allow_drop),
            "status": r.status}


def _get_round(db, round_id):
    from app.models import AaSelectionRound
    r = db.get(AaSelectionRound, int(round_id))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("选课轮次不存在")
    return r


# ══════════ 轮次维护 ══════════

def create_round(user, batch_id, body) -> dict:
    from app.models import AaSelectionRound
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, int(batch_id))
        if b.status in ("LOCKED", "ARCHIVED"):
            raise _invalid("批次已锁定/归档，不可新增轮次")
        mode = (getattr(body, "mode", None) or "FCFS").upper()
        if mode not in MODES:
            raise _bad("轮次模式仅支持 FCFS(先到先得)/LOTTERY(抽签)")
        name = (getattr(body, "roundName", None) or "").strip()
        if not name:
            raise _bad("轮次名称必填")
        max_no = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _tid(), AaSelectionRound.batch_id == b.id,
            AaSelectionRound.is_deleted.is_(False)).count()
        r = AaSelectionRound(
            tenant_id=_tid(), batch_id=b.id, round_no=max_no + 1, round_name=name, mode=mode,
            allow_enroll=bool(getattr(body, "allowEnroll", True)),
            allow_drop=bool(getattr(body, "allowDrop", True)), status="DRAFT")
        db.add(r)
        db.flush()
        _audit(db, r.id, "ROUND_CREATE", f"第{r.round_no}轮 {name}({mode})")
        db.commit()
        return _round_dto(r)


def list_rounds(user, batch_id):
    from app.models import AaSelectionRound
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _tid(), AaSelectionRound.batch_id == int(batch_id),
            AaSelectionRound.is_deleted.is_(False)).order_by(AaSelectionRound.round_no).all()
        return [_round_dto(r) for r in rows]


def open_round(user, round_id) -> dict:
    from app.models import AaSelectionRound
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        r = _get_round(db, round_id)
        if r.status not in ("DRAFT", "CLOSED"):
            raise _invalid("仅草稿/已关闭轮次可开启")
        b = _get_batch(db, r.batch_id)
        if b.status != "OPEN":
            raise _invalid("批次未处于开放选课状态，不可开轮")
        other = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == _tid(), AaSelectionRound.batch_id == r.batch_id,
            AaSelectionRound.status == "OPEN", AaSelectionRound.id != r.id,
            AaSelectionRound.is_deleted.is_(False)).first()
        if other:
            raise _invalid(f"第{other.round_no}轮（{other.round_name}）尚未关闭，同批次同时只能开一个轮次")
        r.status = "OPEN"
        _audit(db, r.id, "ROUND_OPEN", f"第{r.round_no}轮开启")
        db.commit()
        return _round_dto(r)


def close_round(user, round_id) -> dict:
    from app.models import AaSelectionRound  # noqa: F401（保持导入面一致）
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        r = _get_round(db, round_id)
        if r.status != "OPEN":
            raise _invalid("仅开启中的轮次可关闭")
        r.status = "CLOSED"
        _audit(db, r.id, "ROUND_CLOSE", f"第{r.round_no}轮关闭")
        db.commit()
        return _round_dto(r)


# ══════════ 摇号 ══════════

def draw_round(user, round_id) -> dict:
    """抽签摇号：逐课程比对志愿数与剩余容量，超额按确定性派生序取前 N 名。

    中签 → SELECTED 并守护式占容量（绝不超容）；未中签 → LOTTERY_LOST（可进下一轮再选）。
    只允许在 CLOSED 的 LOTTERY 轮次上执行一次；执行后轮次 DRAWN 终态。
    """
    from app.models import AaSelectionCourse, AaSelectionRecord
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        r = _get_round(db, round_id)
        if r.mode != "LOTTERY":
            raise _invalid("仅抽签轮次可摇号")
        if r.status != "CLOSED":
            raise _invalid("请先关闭轮次再摇号（开启中不可摇号，已摇号不可重摇）")

        pend = db.scalars(select(AaSelectionRecord).where(
            AaSelectionRecord.tenant_id == _tid(), AaSelectionRecord.round_id == r.id,
            AaSelectionRecord.status == _REC_PENDING,
            AaSelectionRecord.is_deleted.is_(False))).all()
        by_course = {}
        for rec in pend:
            by_course.setdefault(int(rec.selection_course_id), []).append(rec)

        results, total_win, total_lose = [], 0, 0
        for cid, recs in sorted(by_course.items()):
            c = db.get(AaSelectionCourse, cid)
            remaining = max(0, int(c.capacity or 0) - int(c.selected_count or 0)) if c else 0
            if len(recs) <= remaining:
                winners, losers = recs, []
            else:
                # 确定性摇号：(记录id, 轮次id) 派生序，可复核；不引入不可复现的随机源
                ordered = sorted(recs, key=lambda x: (hash((x.id, r.id)), x.id))
                winners, losers = ordered[:remaining], ordered[remaining:]
            if winners and c:
                n = len(winners)
                upd = db.query(AaSelectionCourse).filter(
                    AaSelectionCourse.id == c.id, AaSelectionCourse.tenant_id == _tid(),
                    AaSelectionCourse.selected_count + n <= AaSelectionCourse.capacity).update(
                    {AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + n},
                    synchronize_session=False)
                if not upd:
                    # 容量在关轮后被外部变更（如教务处调容）→ 本课程全部落败，不硬塞
                    losers, winners = winners + losers, []
            for w in winners:
                w.status, w.enrolled_at = _REC_SELECTED, datetime.utcnow()
            for l in losers:
                l.status = _REC_LOST
            total_win += len(winners)
            total_lose += len(losers)
            results.append({"selectionCourseId": str(cid),
                            "courseName": (c.course_name if c else None),
                            "applicants": len(recs), "winners": len(winners),
                            "losers": len(losers),
                            "remainingBefore": remaining})

        r.status = "DRAWN"
        _audit(db, r.id, "ROUND_DRAW",
               f"第{r.round_no}轮摇号：{len(by_course)}门课，中签{total_win}/落签{total_lose}")
        db.commit()
        return {"roundId": str(r.id), "roundNo": r.round_no, "courses": results,
                "totalWinners": total_win, "totalLosers": total_lose}

"""毕业设计中心 · 答辩评分服务。

每评委对每学生录入一条评分（round_no 区分首次/二次答辩）；缺席留痕；确认后锁定。
达成"需二辩"条件（评委判定/分差异常，本轮由院管人工创建二辩，不做自动阈值判定以避免误伤）。

隔离说明：不引用实习/迎新域文件；与 graduation_service.py 的 GraduationDefenseGroup 关联但不改动其表结构。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationDefenseScore, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

STATUS_LABEL = {"PENDING": "待评分", "SCORED": "已评分", "CONFIRMED": "已确认"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="DEFENSE_SCORE", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.utcnow()))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "defense.score")


def _row(d: GraduationDefenseScore, stu=None) -> dict:
    return {"id": str(d.id), "gdStudentId": str(d.gd_student_id),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "defenseGroupId": str(d.defense_group_id or ""), "judgeName": d.judge_name,
            "score": d.score, "comment": d.comment or "", "absent": d.absent,
            "absentReason": d.absent_reason or "", "roundNo": d.round_no, "status": d.status,
            "statusLabel": STATUS_LABEL.get(d.status, d.status), "confirmedAt": _iso(d.confirmed_at)}


def list_scores(page: int, page_size: int, gd_student_id=None, judge_name=None,
                round_no=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationDefenseScore).where(GraduationDefenseScore.tenant_id == _tid(),
                                                  GraduationDefenseScore.is_deleted.is_(False),
                                                  GraduationDefenseScore.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationDefenseScore.gd_student_id == int(gd_student_id))
        if judge_name:
            q = q.where(GraduationDefenseScore.judge_name == judge_name)
        if round_no:
            q = q.where(GraduationDefenseScore.round_no == int(round_no))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationDefenseScore.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_row(d, db.get(GraduationStudent, d.gd_student_id)) for d in rows]
        return items, total


def enter_score(gd_student_id, judge_name: str, score=None, comment=None, absent=False,
                absent_reason=None, defense_group_id=None) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        if not absent and score is None:
            raise AppException("VALIDATION_ERROR", "未缺席须录入评分")
        if absent and (not absent_reason or len(absent_reason.strip()) < 2):
            raise AppException("VALIDATION_ERROR", "缺席须填写原因")
        latest_round = int(db.scalar(select(func.max(GraduationDefenseScore.round_no)).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == stu.id)) or 1)
        dup = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.judge_name == judge_name, GraduationDefenseScore.round_no == latest_round,
            GraduationDefenseScore.is_deleted.is_(False))).first()
        if dup:
            if dup.status == "CONFIRMED":
                raise AppException("DATA_CONFLICT", "该评委本轮评分已确认，不可修改")
            dup.score = score
            dup.comment = comment
            dup.absent = absent
            dup.absent_reason = absent_reason
            dup.status = "SCORED"
            _audit(db, dup.id, "更新答辩评分")
            db.commit()
            return _row(dup, stu)
        d = GraduationDefenseScore(tenant_id=_tid(), gd_student_id=stu.id,
                                   defense_group_id=int(defense_group_id) if defense_group_id else stu.defense_group_id,
                                   judge_name=judge_name, score=score, comment=comment, absent=absent,
                                   absent_reason=absent_reason, round_no=latest_round, status="SCORED")
        db.add(d)
        db.flush()
        _audit(db, d.id, "录入答辩评分", detail=f"{stu.name}/{judge_name}/{score}")
        db.commit()
        return _row(d, stu)


def confirm_scores(gd_student_id) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        latest_round = int(db.scalar(select(func.max(GraduationDefenseScore.round_no)).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == stu.id)) or 1)
        rows = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.round_no == latest_round, GraduationDefenseScore.is_deleted.is_(False))).all()
        if not rows:
            raise AppException("DATA_CONFLICT", "尚无评分记录")
        pending = [d for d in rows if d.status == "PENDING"]
        if pending:
            raise AppException("DATA_CONFLICT", "仍有评委未完成评分")
        now = datetime.utcnow()
        for d in rows:
            d.status = "CONFIRMED"
            d.confirmed_at = now
        scored = [d.score for d in rows if not d.absent and d.score is not None]
        avg = round(sum(scored) / len(scored), 1) if scored else None
        _audit(db, stu.id, "确认答辩成绩", detail=f"avg={avg}")
        db.commit()
        return {"gdStudentId": str(stu.id), "roundNo": latest_round, "average": avg, "judgeCount": len(rows)}


def create_second_defense(gd_student_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "二次答辩原因必填且不少于 5 字")
    with session() as db:
        stu = _stu(db, gd_student_id)
        latest_round = int(db.scalar(select(func.max(GraduationDefenseScore.round_no)).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == stu.id)) or 0)
        confirmed = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.round_no == latest_round, GraduationDefenseScore.status != "CONFIRMED")).first()
        if latest_round and confirmed:
            raise AppException("DATA_CONFLICT", "本轮评分尚未全部确认，暂不能创建二次答辩")
        _audit(db, stu.id, "创建二次答辩", reason.strip())
        db.commit()
        return {"gdStudentId": str(stu.id), "newRound": latest_round + 1}


def defense_score_stats() -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        base = [GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.is_deleted.is_(False),
                GraduationDefenseScore.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationDefenseScore).where(*base)) or 0)
        confirmed = int(db.scalar(select(func.count()).select_from(GraduationDefenseScore).where(
            *base, GraduationDefenseScore.status == "CONFIRMED")) or 0)
        absent = int(db.scalar(select(func.count()).select_from(GraduationDefenseScore).where(
            *base, GraduationDefenseScore.absent.is_(True))) or 0)
        second_round = int(db.scalar(select(func.count()).select_from(GraduationDefenseScore).where(
            *base, GraduationDefenseScore.round_no > 1)) or 0)
        return {"total": total, "confirmed": confirmed, "absent": absent, "secondRoundCount": second_round}

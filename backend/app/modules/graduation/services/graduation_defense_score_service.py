"""毕业设计中心 · 答辩评分服务。

每评委对每学生录入一条评分（round_no 区分首次/二次答辩）；缺席留痕；确认后锁定。
达成"需二辩"条件（评委判定/分差异常，本轮由院管人工创建二辩，不做自动阈值判定以避免误伤）。

隔离说明：不引用实习/迎新域文件；与 graduation_service.py 的 GraduationDefenseGroup 关联但不改动其表结构。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.models import GraduationAuditTrail, GraduationDefenseGroup, GraduationDefenseScore, GraduationStudent
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


def _panel_judge_names(group: GraduationDefenseGroup | None) -> list[str]:
    """答辩组应评分评委：主席 + 成员（秘书通常不评分，不纳入强制名单）。"""
    if not group:
        return []
    names: list[str] = []
    chair = (group.chair or "").strip()
    if chair:
        names.append(chair)
    for raw in (group.members_json or []):
        if isinstance(raw, str):
            n = raw.strip()
        elif isinstance(raw, dict):
            n = str(raw.get("name") or raw.get("realName") or "").strip()
        else:
            n = ""
        if n and n not in names:
            names.append(n)
    return names


def _active_round_no(db, gd_student_id: int) -> int:
    """当前可录入轮次：若存在更高轮次的非 CONFIRMED 记录则用之，否则 max(round) 或 1。"""
    max_round = int(db.scalar(select(func.max(GraduationDefenseScore.round_no)).where(
        GraduationDefenseScore.tenant_id == _tid(),
        GraduationDefenseScore.gd_student_id == gd_student_id,
        GraduationDefenseScore.is_deleted.is_(False),
    )) or 0)
    if max_round <= 0:
        return 1
    open_row = db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == _tid(),
        GraduationDefenseScore.gd_student_id == gd_student_id,
        GraduationDefenseScore.round_no == max_round,
        GraduationDefenseScore.is_deleted.is_(False),
        GraduationDefenseScore.status != "CONFIRMED",
    ).limit(1)).first()
    if open_row is not None:
        return max_round
    # 全部已确认：仍返回该轮（用于查看）；录入时若全 CONFIRMED 会拦
    return max_round


def _resolve_entry_judge_name(db, stu: GraduationStudent, requested: str | None) -> str:
    """防伪造：评委仅能以本人名义录入；有 manage/score 代录权限时须落在答辩组名单内。"""
    u = get_current_user_ctx() or {}
    real_name = (u.get("realName") or "").strip()
    requested_name = (requested or "").strip()
    role = (u.get("currentRoleCode") or u.get("userType") or "").strip().upper()
    can_proxy = (
        has_permission(u, "graduationDesign.manage")
        or has_permission(u, "graduationDesign.defense.manage")
    )
    group = db.get(GraduationDefenseGroup, stu.defense_group_id) if stu.defense_group_id else None
    panel = _panel_judge_names(group)

    if role == "GD_DEFENSE_EXPERT" or (
        has_permission(u, "graduationDesign.defense.score") and not can_proxy
    ):
        if not real_name:
            raise AppException("VALIDATION_ERROR", "当前账号缺少真实姓名，无法录入评分")
        if requested_name and requested_name != real_name:
            raise no_permission("答辩评委只能以本人名义录入评分")
        if panel and real_name not in panel:
            raise no_permission("你不在该生答辩组评委名单中")
        return real_name

    judge_name = requested_name or real_name
    if not judge_name:
        raise AppException("VALIDATION_ERROR", "评委姓名必填")
    if panel and judge_name not in panel:
        raise AppException("VALIDATION_ERROR", f"评委「{judge_name}」不在该生答辩组名单中")
    return judge_name


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


def judge_pending() -> list[dict]:
    """答辩评委（本人）·待评分学生名单（已发布分组，含本人当前轮次评分状态）。"""
    judge_name, _role = _op()
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        if not scope_ids:
            return []
        stus = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(scope_ids),
            GraduationStudent.defense_group_id.is_not(None),
            GraduationStudent.is_deleted.is_(False))).all()
        out = []
        for stu in stus:
            group = db.get(GraduationDefenseGroup, stu.defense_group_id)
            if not group or group.is_deleted or not group.published:
                continue
            latest_round = _active_round_no(db, stu.id)
            mine = db.scalars(select(GraduationDefenseScore).where(
                GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
                GraduationDefenseScore.judge_name == judge_name,
                GraduationDefenseScore.round_no == latest_round,
                GraduationDefenseScore.is_deleted.is_(False))).first()
            my_status = mine.status if mine else "PENDING"
            out.append({
                "gdStudentId": str(stu.id), "studentName": stu.name, "studentNo": stu.student_no or "",
                "topicTitle": stu.topic_title or "（未选题）", "groupName": group.group_name,
                "defenseDate": group.defense_date or "待定", "location": group.location or "待定",
                "roundNo": latest_round, "myScoreId": str(mine.id) if mine else "",
                "myScore": mine.score if mine else None, "myAbsent": bool(mine.absent) if mine else False,
                "myComment": mine.comment if mine else "", "myStatus": my_status,
                "myStatusLabel": STATUS_LABEL.get(my_status, "待评分"),
            })
        return out


def enter_score(gd_student_id, judge_name: str, score=None, comment=None, absent=False,
                absent_reason=None, defense_group_id=None) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        if not absent and score is None:
            raise AppException("VALIDATION_ERROR", "未缺席须录入评分")
        if absent and (not absent_reason or len(absent_reason.strip()) < 2):
            raise AppException("VALIDATION_ERROR", "缺席须填写原因")
        judge_name = _resolve_entry_judge_name(db, stu, judge_name)
        latest_round = _active_round_no(db, stu.id)
        # 本轮若已全部确认，禁止再往旧轮写入
        open_exists = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.round_no == latest_round,
            GraduationDefenseScore.is_deleted.is_(False),
            GraduationDefenseScore.status != "CONFIRMED",
        ).limit(1)).first()
        any_row = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(),
            GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.round_no == latest_round,
            GraduationDefenseScore.is_deleted.is_(False),
        ).limit(1)).first()
        if any_row and open_exists is None:
            raise AppException("DATA_CONFLICT", "本轮评分已全部确认；如需再辩请先创建二次答辩")
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
        latest_round = _active_round_no(db, stu.id)
        rows = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.round_no == latest_round, GraduationDefenseScore.is_deleted.is_(False))).all()
        if not rows:
            raise AppException("DATA_CONFLICT", "尚无评分记录")
        pending = [d for d in rows if d.status == "PENDING"]
        if pending:
            raise AppException("DATA_CONFLICT", "仍有评委未完成评分")
        group = db.get(GraduationDefenseGroup, stu.defense_group_id) if stu.defense_group_id else None
        expected = _panel_judge_names(group)
        if expected:
            done = {d.judge_name for d in rows if d.status in ("SCORED", "CONFIRMED")}
            missing = [n for n in expected if n not in done]
            if missing:
                raise AppException(
                    "DATA_CONFLICT",
                    f"答辩组评委尚未全部评分：{('、'.join(missing))}",
                )
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
            GraduationDefenseScore.gd_student_id == stu.id,
            GraduationDefenseScore.is_deleted.is_(False))) or 0)
        if latest_round:
            unconfirmed = db.scalars(select(GraduationDefenseScore).where(
                GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == stu.id,
                GraduationDefenseScore.round_no == latest_round,
                GraduationDefenseScore.is_deleted.is_(False),
                GraduationDefenseScore.status != "CONFIRMED")).first()
            if unconfirmed:
                raise AppException("DATA_CONFLICT", "本轮评分尚未全部确认，暂不能创建二次答辩")
        new_round = latest_round + 1
        group = db.get(GraduationDefenseGroup, stu.defense_group_id) if stu.defense_group_id else None
        judges = _panel_judge_names(group)
        if not judges and latest_round:
            # 无组名单时回退上一轮评委名单
            prev = db.scalars(select(GraduationDefenseScore).where(
                GraduationDefenseScore.tenant_id == _tid(),
                GraduationDefenseScore.gd_student_id == stu.id,
                GraduationDefenseScore.round_no == latest_round,
                GraduationDefenseScore.is_deleted.is_(False))).all()
            judges = []
            for d in prev:
                if d.judge_name and d.judge_name not in judges:
                    judges.append(d.judge_name)
        if not judges:
            raise AppException("DATA_CONFLICT", "无法创建二次答辩：缺少答辩组评委名单")
        for name in judges:
            db.add(GraduationDefenseScore(
                tenant_id=_tid(), gd_student_id=stu.id,
                defense_group_id=stu.defense_group_id,
                judge_name=name, round_no=new_round, status="PENDING",
                score=None, absent=False,
            ))
        _audit(db, stu.id, "创建二次答辩", reason.strip(), after=str(new_round))
        db.commit()
        return {"gdStudentId": str(stu.id), "newRound": new_round, "pendingJudges": judges}


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

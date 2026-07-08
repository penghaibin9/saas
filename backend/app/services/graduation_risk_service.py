"""毕业设计中心 · 问题预警服务（GD-R01~R13 对齐 source-design §13 冻结编码，本轮实现可由现有数据判定的 8 项）。

扫描现有业务数据生成/更新风险台账（幂等 upsert，按 risk_code+gd_student_id 唯一），
再走"受理→处理→关闭"闭环。扫描本身是只读推导，不修改业务表。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationAuditTrail, GraduationDefenseScore, GraduationFinal, GraduationGrade,
                        GraduationMidterm, GraduationProposal, GraduationRiskCase, GraduationStudent)
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"OPEN": "待受理", "PROCESSING": "处理中", "CLOSED": "已关闭"}
STATUS_TONE = {"OPEN": "danger", "PROCESSING": "warning", "CLOSED": "success"}
RISK_DEFS = {
    "GD-R01": ("未选题", "MEDIUM"),
    "GD-R02": ("选题未确认", "MEDIUM"),
    "GD-R03": ("任务书未下达", "HIGH"),
    "GD-R04": ("开题逾期未提交或未获通过", "HIGH"),
    "GD-R05": ("开题退回滞留未重交", "MEDIUM"),
    "GD-R06": ("指导记录不足", "MEDIUM"),
    "GD-R07": ("中期未完成", "HIGH"),
    "GD-R08": ("论文未提交", "HIGH"),
    "GD-R09": ("答辩评分缺失", "HIGH"),
    "GD-R10": ("答辩未安排", "HIGH"),
    "GD-R11": ("答辩成绩异常需二辩", "HIGH"),
    "GD-R12": ("材料未归档", "HIGH"),
    "GD-R13": ("毕业资格受影响", "CRITICAL"),
}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="RISK", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.utcnow()))


def _upsert(db, code, sid) -> None:
    exists = db.scalars(select(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == _tid(), GraduationRiskCase.risk_code == code,
        GraduationRiskCase.gd_student_id == sid)).first()
    if exists:
        return
    name, level = RISK_DEFS[code]
    db.add(GraduationRiskCase(tenant_id=_tid(), risk_code=code, risk_name=name, gd_student_id=sid,
                              level=level, status="OPEN", detected_at=datetime.utcnow()))


def scan_risks() -> dict:
    """扫描现有数据，生成新发现的风险项（已存在的同 risk_code+student 不重复生成）。"""
    with session() as db:
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE")).all()
        created = 0
        before_count = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            GraduationRiskCase.tenant_id == _tid())) or 0)
        for s in students:
            if s.stage == "TOPIC_SELECTING" and not s.topic_id:
                _upsert(db, "GD-R01", s.id)
            # R02 选题未确认：已选到题目但阶段仍停在选题中
            if s.stage == "TOPIC_SELECTING" and s.topic_id:
                _upsert(db, "GD-R02", s.id)
            # R03 任务书未下达：已过选题/进入指导阶段但无任务书
            if s.stage in ("TASKBOOK_CONFIRM", "GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE"):
                from app.models import GraduationTaskBook
                tb = db.scalars(select(GraduationTaskBook).where(
                    GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == s.id,
                    GraduationTaskBook.is_deleted.is_(False))).first()
                if not tb:
                    _upsert(db, "GD-R03", s.id)
            # R05 开题退回滞留：最新开题为 REJECTED 且未重交（无更晚的待审/通过）
            props = db.scalars(select(GraduationProposal).where(
                GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == s.id,
                GraduationProposal.is_deleted.is_(False)).order_by(GraduationProposal.id.desc())).all()
            if props and props[0].status == "REJECTED":
                _upsert(db, "GD-R05", s.id)
            # R10 答辩未安排：进入成果检查/答辩阶段但未分到答辩组
            if s.stage in ("FINAL_CHECK", "DEFENSE") and not s.defense_group_id:
                _upsert(db, "GD-R10", s.id)
            # R11 答辩成绩异常需二辩：已有答辩评分但平均分 < 60
            if s.stage in ("DEFENSE",):
                sc = db.scalars(select(GraduationDefenseScore).where(
                    GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == s.id,
                    GraduationDefenseScore.is_deleted.is_(False),
                    GraduationDefenseScore.score.isnot(None))).all()
                if sc:
                    avg = sum(x.score for x in sc) / len(sc)
                    if avg < 60:
                        _upsert(db, "GD-R11", s.id)
            if s.stage not in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
                has_approved = db.scalars(select(GraduationProposal).where(
                    GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == s.id,
                    GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False))).first()
                if not has_approved and s.stage in ("GUIDING", "MIDTERM"):
                    _upsert(db, "GD-R04", s.id)
            if s.stage in ("MIDTERM", "FINAL_CHECK", "DEFENSE"):
                m = db.scalars(select(GraduationMidterm).where(
                    GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == s.id)).first()
                if not m or m.status in ("PENDING", "RECTIFYING", "RECTIFY_SUBMITTED", "CHECKED_FAIL"):
                    _upsert(db, "GD-R07", s.id)
            if s.stage in ("DEFENSE",):
                has_final = db.scalars(select(GraduationFinal).where(
                    GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == s.id,
                    GraduationFinal.is_deleted.is_(False))).first()
                if not has_final:
                    _upsert(db, "GD-R08", s.id)
                scores = db.scalars(select(GraduationDefenseScore).where(
                    GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == s.id,
                    GraduationDefenseScore.is_deleted.is_(False))).first()
                if not scores:
                    _upsert(db, "GD-R09", s.id)
            g = db.scalars(select(GraduationGrade).where(
                GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == s.id)).first()
            if g and g.status == "PUBLISHED":
                if g.total_score is not None and g.total_score < 60:
                    _upsert(db, "GD-R13", s.id)
        db.commit()
        after_count = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            GraduationRiskCase.tenant_id == _tid())) or 0)
        created = after_count - before_count
        return {"scannedStudents": len(students), "newCasesCreated": created, "totalCases": after_count}


def _row(r: GraduationRiskCase, stu=None) -> dict:
    return {"id": str(r.id), "riskCode": r.risk_code, "riskName": r.risk_name,
            "gdStudentId": str(r.gd_student_id), "studentName": stu.name if stu else "",
            "studentNo": stu.student_no if stu else "", "advisorName": stu.advisor_name if stu else "",
            "level": r.level, "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
            "statusTone": STATUS_TONE.get(r.status, "default"), "assignee": r.assignee or "",
            "handleNote": r.handle_note or "", "closeReason": r.close_reason or "",
            "detectedAt": _iso(r.detected_at), "closedAt": _iso(r.closed_at)}


def list_risks(page: int, page_size: int, risk_code=None, level=None, status=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationRiskCase).where(GraduationRiskCase.tenant_id == _tid(),
                                             GraduationRiskCase.is_deleted.is_(False))
        if risk_code:
            q = q.where(GraduationRiskCase.risk_code == risk_code)
        if level:
            q = q.where(GraduationRiskCase.level == level)
        if status:
            q = q.where(GraduationRiskCase.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationRiskCase.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_row(r, db.get(GraduationStudent, r.gd_student_id)) for r in rows]
        return items, total


def accept_risk(rid, assignee: str = None) -> dict:
    with session() as db:
        r = db.get(GraduationRiskCase, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("风险记录不存在")
        if r.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅「待受理」风险可受理")
        n, _ = _op()
        r.status = "PROCESSING"
        r.assignee = assignee or n
        _audit(db, r.id, "受理风险")
        db.commit()
        return _row(r, db.get(GraduationStudent, r.gd_student_id))


def process_risk(rid, note: str) -> dict:
    with session() as db:
        r = db.get(GraduationRiskCase, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("风险记录不存在")
        if r.status != "PROCESSING":
            raise AppException("DATA_CONFLICT", "仅「处理中」风险可记录处理")
        r.handle_note = note
        _audit(db, r.id, "处理风险", note)
        db.commit()
        return _row(r, db.get(GraduationStudent, r.gd_student_id))


def close_risk(rid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭原因必填且不少于 5 字")
    with session() as db:
        r = db.get(GraduationRiskCase, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("风险记录不存在")
        if r.status != "PROCESSING":
            raise AppException("DATA_CONFLICT", "仅「处理中」风险可关闭")
        r.status = "CLOSED"
        r.close_reason = reason.strip()
        r.closed_at = datetime.utcnow()
        _audit(db, r.id, "关闭风险", reason.strip())
        db.commit()
        return _row(r, db.get(GraduationStudent, r.gd_student_id))


def risk_stats() -> dict:
    with session() as db:
        base = [GraduationRiskCase.tenant_id == _tid(), GraduationRiskCase.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(*base)) or 0)
        open_count = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            *base, GraduationRiskCase.status == "OPEN")) or 0)
        by_code = [{"riskCode": c, "riskName": RISK_DEFS[c][0],
                   "count": int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
                       *base, GraduationRiskCase.risk_code == c, GraduationRiskCase.status != "CLOSED")) or 0)}
                  for c in RISK_DEFS]
        critical = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            *base, GraduationRiskCase.level == "CRITICAL", GraduationRiskCase.status != "CLOSED")) or 0)
        return {"total": total, "openCount": open_count, "criticalOpenCount": critical, "byCode": by_code}

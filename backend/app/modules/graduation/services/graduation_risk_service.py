"""毕业设计中心 · 问题预警服务（GD-R01~R13 对齐 source-design §13 冻结编码，全部 13 项均已实现自动判定）。

扫描现有业务数据生成/更新风险台账（幂等 upsert，按 risk_code+gd_student_id 唯一），
再走"受理→处理→关闭"闭环。扫描本身是只读推导，不修改业务表。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationArchiveRecord, GraduationAuditTrail, GraduationDefenseScore, GraduationFinal,
                        GraduationGrade, GraduationGuidance, GraduationMidterm, GraduationProposal,
                        GraduationRiskCase, GraduationStudent)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

GUIDANCE_MIN_COUNT = 3

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
                                occurred_at=datetime.now(timezone.utc)))


def _upsert(db, code, sid) -> str:
    """幂等写入风险；返回 created / exists。"""
    exists = db.scalars(select(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == _tid(), GraduationRiskCase.risk_code == code,
        GraduationRiskCase.gd_student_id == sid)).first()
    if exists:
        return "exists"
    name, level = RISK_DEFS[code]
    db.add(GraduationRiskCase(tenant_id=_tid(), risk_code=code, risk_name=name, gd_student_id=sid,
                              level=level, status="OPEN", detected_at=datetime.now(timezone.utc)))
    return "created"


def _scope_audit_summary() -> dict:
    from app.modules.graduation.services.graduation_scope_service import has_full_scope, org_scope_status
    u = get_current_user_ctx() or {}
    op_name, role = _op()
    org = org_scope_status(u)
    if has_full_scope():
        hint = "全校范围"
    elif org.get("collegeIds"):
        hint = f"学院范围 collegeIds={','.join(org['collegeIds'])}"
    elif org.get("majorIds"):
        hint = f"专业范围 majorIds={','.join(org['majorIds'])}"
    else:
        hint = org.get("scopeHint") or f"角色 {role or '未知'} 限定范围"
    return {
        "operator": op_name,
        "role": role,
        "fullScope": has_full_scope(),
        "collegeIds": org.get("collegeIds") or [],
        "majorIds": org.get("majorIds") or [],
        "scopeSummary": hint,
    }


def _require_batch(db, batch_id):
    """批量/扫描危险操作必须带有效批次，禁止静默全量。"""
    if batch_id is None or batch_id == "":
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次后再执行")
    from app.models import GraduationBatch
    bid = int(batch_id)
    b = db.get(GraduationBatch, bid)
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("毕设批次不存在")
    return b


def _scan_one_student(db, s) -> list[str]:
    """对单个学生判定风险编码（不写库）；返回命中的 risk_code 列表。"""
    hits: list[str] = []
    if s.stage == "TOPIC_SELECTING" and not s.topic_id:
        hits.append("GD-R01")
    if s.stage == "TOPIC_SELECTING" and s.topic_id:
        hits.append("GD-R02")
    if s.stage in ("TASKBOOK_CONFIRM", "GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE"):
        from app.models import GraduationTaskBook
        tb = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == s.id,
            GraduationTaskBook.is_deleted.is_(False))).first()
        if not tb:
            hits.append("GD-R03")
    props = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == s.id,
        GraduationProposal.is_deleted.is_(False)).order_by(GraduationProposal.id.desc())).all()
    if props and props[0].status == "REJECTED":
        hits.append("GD-R05")
    if s.stage in ("GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE"):
        gc = int(db.scalar(select(func.count()).select_from(GraduationGuidance).where(
            GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == s.id,
            GraduationGuidance.is_deleted.is_(False))) or 0)
        if gc < GUIDANCE_MIN_COUNT:
            hits.append("GD-R06")
    if s.stage in ("FINAL_CHECK", "DEFENSE") and not s.defense_group_id:
        hits.append("GD-R10")
    if s.stage in ("DEFENSE",):
        sc = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == s.id,
            GraduationDefenseScore.is_deleted.is_(False),
            GraduationDefenseScore.score.isnot(None))).all()
        if sc:
            avg = sum(x.score for x in sc) / len(sc)
            if avg < 60:
                hits.append("GD-R11")
    if s.stage not in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
        has_approved = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == s.id,
            GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False))).first()
        if not has_approved and s.stage in ("GUIDING", "MIDTERM"):
            hits.append("GD-R04")
    if s.stage in ("MIDTERM", "FINAL_CHECK", "DEFENSE"):
        m = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == s.id)).first()
        if not m or m.status in ("PENDING", "RECTIFYING", "RECTIFY_SUBMITTED", "CHECKED_FAIL"):
            hits.append("GD-R07")
    if s.stage in ("DEFENSE",):
        has_final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == s.id,
            GraduationFinal.is_deleted.is_(False))).first()
        if not has_final:
            hits.append("GD-R08")
        scores = db.scalars(select(GraduationDefenseScore).where(
            GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == s.id,
            GraduationDefenseScore.is_deleted.is_(False))).first()
        if not scores:
            hits.append("GD-R09")
    g = db.scalars(select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == s.id)).first()
    if g and g.status == "PUBLISHED":
        if g.total_score is not None and g.total_score < 60:
            hits.append("GD-R13")
        ar = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == s.id)).first()
        if not ar or ar.status != "FILED":
            hits.append("GD-R12")
    return hits


def scan_risks(batch_id=None) -> dict:
    """扫描指定批次 + 当前数据范围内 ACTIVE 学生，生成新发现风险（幂等）。"""
    from app.modules.graduation.services.graduation_scope_service import can_access_student
    with session() as db:
        batch = _require_batch(db, batch_id)
        bid = int(batch.id)
        # 批次内全部 ACTIVE，再按数据范围过滤；范围外计为 skipped（审计可核验未误扫）
        batch_students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.batch_id == bid)).all()
        skipped_students = 0
        students = []
        for s in batch_students:
            if can_access_student(db, s):
                students.append(s)
            else:
                skipped_students += 1

        created = 0
        existed = 0
        for s in students:
            for code in _scan_one_student(db, s):
                result = _upsert(db, code, s.id)
                if result == "created":
                    created += 1
                else:
                    existed += 1

        scope = _scope_audit_summary()
        detail = (
            f"batchId={bid} batchName={batch.batch_name} "
            f"scanned={len(students)} new={created} existed={existed} skipped={skipped_students} "
            f"operator={scope['operator']} scope={scope['scopeSummary']}"
        )
        _audit(db, f"scan-{bid}", "扫描毕设风险", detail)
        db.commit()
        total_cases = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            GraduationRiskCase.tenant_id == _tid(),
            GraduationRiskCase.gd_student_id.in_([s.id for s in students] or [-1]),
            GraduationRiskCase.is_deleted.is_(False))) or 0)
        return {
            "batchId": str(bid),
            "batchName": batch.batch_name,
            "scannedStudents": len(students),
            "newCasesCreated": created,
            "existingCases": existed,
            "skippedStudents": skipped_students,
            "totalCases": total_cases,
            "operator": scope["operator"],
            "scopeSummary": scope["scopeSummary"],
        }


def _row(r: GraduationRiskCase, stu=None) -> dict:
    return {"id": str(r.id), "riskCode": r.risk_code, "riskName": r.risk_name,
            "gdStudentId": str(r.gd_student_id), "studentName": stu.name if stu else "",
            "studentNo": stu.student_no if stu else "", "advisorName": stu.advisor_name if stu else "",
            "level": r.level, "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
            "statusTone": STATUS_TONE.get(r.status, "default"), "assignee": r.assignee or "",
            "handleNote": r.handle_note or "", "closeReason": r.close_reason or "",
            "detectedAt": _iso(r.detected_at), "closedAt": _iso(r.closed_at)}


def list_risks(page: int, page_size: int, risk_code=None, level=None, status=None,
               gd_student_id=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        q = select(GraduationRiskCase).where(GraduationRiskCase.tenant_id == _tid(),
                                             GraduationRiskCase.is_deleted.is_(False),
                                             GraduationRiskCase.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationRiskCase.gd_student_id == int(gd_student_id))
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
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "risk.accept")
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
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "risk.process")
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
        assert_student_access(db, db.get(GraduationStudent, r.gd_student_id), "risk.close")
        if r.status != "PROCESSING":
            raise AppException("DATA_CONFLICT", "仅「处理中」风险可关闭")
        r.status = "CLOSED"
        r.close_reason = reason.strip()
        r.closed_at = datetime.now(timezone.utc)
        _audit(db, r.id, "关闭风险", reason.strip())
        db.commit()
        return _row(r, db.get(GraduationStudent, r.gd_student_id))


def risk_stats(batch_id=None) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [GraduationRiskCase.tenant_id == _tid(), GraduationRiskCase.is_deleted.is_(False),
                GraduationRiskCase.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(*base)) or 0)
        open_count = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            *base, GraduationRiskCase.status == "OPEN")) or 0)
        by_code = [{"riskCode": c, "riskName": RISK_DEFS[c][0],
                   "count": int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
                       *base, GraduationRiskCase.risk_code == c, GraduationRiskCase.status != "CLOSED")) or 0)}
                  for c in RISK_DEFS]
        critical = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
            *base, GraduationRiskCase.level == "CRITICAL", GraduationRiskCase.status != "CLOSED")) or 0)
        return {"total": total, "openCount": open_count, "criticalOpenCount": critical, "byCode": by_code,
                "batchId": str(batch_id) if batch_id else None}

"""毕业设计中心 · 问题预警服务（GD-R01~R13）。

- 同生同码保留唯一行（uk_gd_risk_case）：创建 / 触碰 / 重开，不插重复开放案。
- 扫描按批次聚合查询，禁止对学生逐条 N+1。
- 业务钩子可对单生轻量重扫（同会话 flush，不强制另起事务）。
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GraduationArchiveRecord, GraduationAuditTrail, GraduationDefenseScore, GraduationFinal,
                        GraduationGrade, GraduationGuidance, GraduationMidterm, GraduationProposal,
                        GraduationRiskCase, GraduationStudent, GraduationTaskBook)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access

log = logging.getLogger("graduation.risk")

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


def _audit(db, bid, action, detail="", before="", after="", batch_id=None):
    n, r = _op()
    db.add(GraduationAuditTrail(
        tenant_id=_tid(), batch_id=int(batch_id) if batch_id else None,
        biz_type="RISK", biz_id=str(bid), action=action,
        operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
        occurred_at=datetime.now(timezone.utc),
    ))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _condition_meta(code: str, summary: str = "") -> tuple[str, str]:
    name = RISK_DEFS[code][0]
    text = (summary or name).strip()[:500]
    digest = hashlib.sha256(f"{code}|{text}".encode("utf-8")).hexdigest()[:32]
    return text, digest


def _next_action_hint(r: GraduationRiskCase) -> str:
    if r.status == "OPEN":
        if getattr(r, "condition_active", True) is False:
            return "扫描显示触发条件已消失，可关闭本条风险"
        return "下一步：受理并安排处置"
    if r.status == "PROCESSING":
        if getattr(r, "condition_active", True) is False:
            return "条件已消失，可填写原因后关闭"
        return "下一步：记录处理过程，条件消除后关闭"
    if r.status == "CLOSED":
        return "已关闭；若条件再次出现，扫描会自动重开"
    return ""


def _upsert_hit(db, code: str, sid: int, *, summary: str = "") -> str:
    """命中风险：created / touched / reopened。不插第二条同生同码行。"""
    now = _now()
    summary_text, chash = _condition_meta(code, summary)
    exists = db.scalars(select(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == _tid(), GraduationRiskCase.risk_code == code,
        GraduationRiskCase.gd_student_id == sid,
        GraduationRiskCase.is_deleted.is_(False),
    ).with_for_update()).first()
    name, level = RISK_DEFS[code]
    if not exists:
        db.add(GraduationRiskCase(
            tenant_id=_tid(), risk_code=code, risk_name=name, gd_student_id=sid,
            level=level, status="OPEN", detected_at=now, first_detected_at=now,
            last_detected_at=now, reopen_count=0, condition_active=True,
            condition_summary=summary_text, condition_hash=chash,
        ))
        return "created"

    exists.last_detected_at = now
    exists.condition_active = True
    exists.condition_summary = summary_text
    exists.condition_hash = chash
    if not exists.first_detected_at:
        exists.first_detected_at = exists.detected_at or now
    if not exists.detected_at:
        exists.detected_at = exists.first_detected_at or now

    if exists.status == "CLOSED":
        exists.status = "OPEN"
        exists.reopen_count = int(exists.reopen_count or 0) + 1
        exists.last_reopened_at = now
        exists.closed_at = None
        exists.close_reason = None
        exists.assignee = None
        return "reopened"
    return "touched"


def _mark_inactive(db, sid: int, active_codes: set[str]) -> int:
    """开放/处理中但本次未命中：标记条件已消失，不自动关闭。"""
    rows = db.scalars(select(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == _tid(),
        GraduationRiskCase.gd_student_id == sid,
        GraduationRiskCase.is_deleted.is_(False),
        GraduationRiskCase.status.in_(("OPEN", "PROCESSING")),
    )).all()
    n = 0
    for r in rows:
        if r.risk_code not in active_codes and getattr(r, "condition_active", True):
            r.condition_active = False
            n += 1
    return n


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
    if batch_id is None or batch_id == "":
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次后再执行")
    from app.models import GraduationBatch
    bid = int(batch_id)
    b = db.get(GraduationBatch, bid)
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("毕设批次不存在")
    return b


def _load_scan_context(db, student_ids: list[int]) -> dict:
    """一次拉取批次内判定所需附属数据（按 gd_student_id 聚合）。"""
    ids = [int(x) for x in student_ids]
    empty = {
        "has_taskbook": set(),
        "latest_proposal_status": {},
        "has_approved_proposal": set(),
        "guidance_count": defaultdict(int),
        "midterm_by_sid": {},
        "has_final": set(),
        "defense_scores": defaultdict(list),
        "grade_by_sid": {},
        "archive_by_sid": {},
    }
    if not ids:
        return empty

    for tid in db.scalars(select(GraduationTaskBook.gd_student_id).where(
        GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.is_deleted.is_(False),
        GraduationTaskBook.gd_student_id.in_(ids),
    )).all():
        empty["has_taskbook"].add(int(tid))

    props = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.is_deleted.is_(False),
        GraduationProposal.gd_student_id.in_(ids),
    ).order_by(GraduationProposal.id.desc())).all()
    for p in props:
        sid = int(p.gd_student_id)
        if sid not in empty["latest_proposal_status"]:
            empty["latest_proposal_status"][sid] = p.status
        if p.status == "APPROVED":
            empty["has_approved_proposal"].add(sid)

    for sid, cnt in db.execute(select(
        GraduationGuidance.gd_student_id, func.count()
    ).where(
        GraduationGuidance.tenant_id == _tid(), GraduationGuidance.is_deleted.is_(False),
        GraduationGuidance.gd_student_id.in_(ids),
    ).group_by(GraduationGuidance.gd_student_id)).all():
        empty["guidance_count"][int(sid)] = int(cnt)

    for m in db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id.in_(ids),
    )).all():
        empty["midterm_by_sid"][int(m.gd_student_id)] = m

    for fid in db.scalars(select(GraduationFinal.gd_student_id).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.is_deleted.is_(False),
        GraduationFinal.gd_student_id.in_(ids),
    )).all():
        empty["has_final"].add(int(fid))

    for d in db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.is_deleted.is_(False),
        GraduationDefenseScore.gd_student_id.in_(ids),
    )).all():
        empty["defense_scores"][int(d.gd_student_id)].append(d)

    for g in db.scalars(select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id.in_(ids),
    )).all():
        empty["grade_by_sid"][int(g.gd_student_id)] = g

    for a in db.scalars(select(GraduationArchiveRecord).where(
        GraduationArchiveRecord.tenant_id == _tid(),
        GraduationArchiveRecord.gd_student_id.in_(ids),
    )).all():
        empty["archive_by_sid"][int(a.gd_student_id)] = a

    return empty


def _eval_hits(s: GraduationStudent, ctx: dict) -> list[str]:
    """纯内存判定 13 类风险（不查库）。"""
    hits: list[str] = []
    sid = int(s.id)
    stage = s.stage or ""

    if stage == "TOPIC_SELECTING" and not s.topic_id:
        hits.append("GD-R01")
    if stage == "TOPIC_SELECTING" and s.topic_id:
        hits.append("GD-R02")
    if stage in ("TASKBOOK_CONFIRM", "GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE"):
        if sid not in ctx["has_taskbook"]:
            hits.append("GD-R03")
    if ctx["latest_proposal_status"].get(sid) == "REJECTED":
        hits.append("GD-R05")
    if stage in ("GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE"):
        if ctx["guidance_count"].get(sid, 0) < GUIDANCE_MIN_COUNT:
            hits.append("GD-R06")
    if stage in ("FINAL_CHECK", "DEFENSE") and not s.defense_group_id:
        hits.append("GD-R10")
    if stage == "DEFENSE":
        scored = [x for x in ctx["defense_scores"].get(sid, []) if x.score is not None]
        if scored:
            avg = sum(x.score for x in scored) / len(scored)
            if avg < 60:
                hits.append("GD-R11")
    if stage not in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
        if sid not in ctx["has_approved_proposal"] and stage in ("GUIDING", "MIDTERM"):
            hits.append("GD-R04")
    if stage in ("MIDTERM", "FINAL_CHECK", "DEFENSE"):
        m = ctx["midterm_by_sid"].get(sid)
        if not m or m.status in ("PENDING", "RECTIFYING", "RECTIFY_SUBMITTED", "CHECKED_FAIL"):
            hits.append("GD-R07")
    if stage == "DEFENSE":
        if sid not in ctx["has_final"]:
            hits.append("GD-R08")
        if not ctx["defense_scores"].get(sid):
            hits.append("GD-R09")
    g = ctx["grade_by_sid"].get(sid)
    if g and g.status == "PUBLISHED":
        if g.total_score is not None and g.total_score < 60:
            hits.append("GD-R13")
        ar = ctx["archive_by_sid"].get(sid)
        if not ar or ar.status != "FILED":
            hits.append("GD-R12")
    return hits


def _scan_one_student(db, s) -> list[str]:
    """单生兼容入口（钩子用）：仍走聚合上下文，避免回归 N+1。"""
    ctx = _load_scan_context(db, [s.id])
    return _eval_hits(s, ctx)


def apply_hits_for_student(db, s: GraduationStudent, hits: list[str] | None = None) -> dict:
    """在已有会话内对一名学生 upsert；供批次扫描与事件钩子复用。"""
    if hits is None:
        hits = _scan_one_student(db, s)
    created = touched = reopened = 0
    for code in hits:
        result = _upsert_hit(db, code, s.id)
        if result == "created":
            created += 1
        elif result == "reopened":
            reopened += 1
        else:
            touched += 1
    inactive = _mark_inactive(db, s.id, set(hits))
    return {"created": created, "touched": touched, "reopened": reopened, "inactiveMarked": inactive, "hits": hits}


def scan_student_risks_in_session(db, gd_student_id: int) -> dict:
    """事件钩子：单生轻量重扫（调用方负责 commit）。"""
    s = db.get(GraduationStudent, int(gd_student_id))
    if not s or s.is_deleted or s.tenant_id != _tid() or s.record_status != "ACTIVE":
        return {"skipped": True}
    return apply_hits_for_student(db, s)


def notify_risk_rescan(db, gd_student_id: int) -> None:
    """业务写路径后的尽力重扫；失败只打日志，不阻断主流程。"""
    try:
        scan_student_risks_in_session(db, gd_student_id)
    except Exception:  # noqa: BLE001
        log.exception("risk rescan hook failed student=%s", gd_student_id)


def scan_risks(batch_id=None) -> dict:
    """扫描指定批次 + 当前数据范围内 ACTIVE 学生（聚合查询 + 内存判定）。"""
    from app.modules.graduation.services.graduation_scope_service import can_access_student
    t0 = time.perf_counter()
    with session() as db:
        batch = _require_batch(db, batch_id)
        bid = int(batch.id)
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

        ctx = _load_scan_context(db, [s.id for s in students])
        created = touched = reopened = inactive = 0
        for s in students:
            hits = _eval_hits(s, ctx)
            stats = apply_hits_for_student(db, s, hits)
            created += stats["created"]
            touched += stats["touched"]
            reopened += stats["reopened"]
            inactive += stats["inactiveMarked"]

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        scope = _scope_audit_summary()
        summary = {
            "scannedStudents": len(students),
            "newCasesCreated": created,
            "existingTouched": touched,
            "reopenedCases": reopened,
            "inactiveMarked": inactive,
            "skippedStudents": skipped_students,
            "elapsedMs": elapsed_ms,
        }
        batch.last_risk_scan_at = _now()
        batch.last_risk_scan_stats_json = summary
        detail = (
            f"batchId={bid} batchName={batch.batch_name} "
            f"scanned={len(students)} new={created} touched={touched} reopened={reopened} "
            f"skipped={skipped_students} elapsedMs={elapsed_ms} "
            f"operator={scope['operator']} scope={scope['scopeSummary']}"
        )
        _audit(db, f"scan-{bid}", "扫描毕设风险", detail, batch_id=bid)
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
            "existingCases": touched,  # 兼容旧前端字段名
            "existingTouched": touched,
            "reopenedCases": reopened,
            "inactiveMarked": inactive,
            "skippedStudents": skipped_students,
            "totalCases": total_cases,
            "elapsedMs": elapsed_ms,
            "lastScanAt": _iso(batch.last_risk_scan_at),
            "operator": scope["operator"],
            "scopeSummary": scope["scopeSummary"],
        }


def last_scan_info(batch_id=None) -> dict:
    with session() as db:
        batch = _require_batch(db, batch_id)
        stats = batch.last_risk_scan_stats_json or {}
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "lastScanAt": _iso(batch.last_risk_scan_at),
            "stats": stats,
        }


def _row(r: GraduationRiskCase, stu=None) -> dict:
    first_at = getattr(r, "first_detected_at", None) or r.detected_at
    return {
        "id": str(r.id), "riskCode": r.risk_code, "riskName": r.risk_name,
        "gdStudentId": str(r.gd_student_id), "studentName": stu.name if stu else "",
        "studentNo": stu.student_no if stu else "", "advisorName": stu.advisor_name if stu else "",
        "level": r.level, "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "statusTone": STATUS_TONE.get(r.status, "default"), "assignee": r.assignee or "",
        "handleNote": r.handle_note or "", "closeReason": r.close_reason or "",
        "detectedAt": _iso(r.detected_at), "firstDetectedAt": _iso(first_at),
        "lastDetectedAt": _iso(getattr(r, "last_detected_at", None)),
        "createdAt": _iso(first_at),
        "reopenCount": int(getattr(r, "reopen_count", 0) or 0),
        "lastReopenedAt": _iso(getattr(r, "last_reopened_at", None)),
        "conditionActive": bool(getattr(r, "condition_active", True)),
        "conditionSummary": getattr(r, "condition_summary", None) or "",
        "nextActionHint": _next_action_hint(r),
        "closedAt": _iso(r.closed_at),
    }


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
        # 处理中可关；待受理且条件已消失也可直接关闭（避免空转受理）
        allow_open_inactive = (
            r.status == "OPEN" and getattr(r, "condition_active", True) is False
        )
        if r.status != "PROCESSING" and not allow_open_inactive:
            raise AppException("DATA_CONFLICT", "仅「处理中」风险可关闭（条件已消失的待受理除外）")
        r.status = "CLOSED"
        r.close_reason = reason.strip()
        r.closed_at = _now()
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
        last_scan = None
        if batch_id:
            from app.models import GraduationBatch
            b = db.get(GraduationBatch, int(batch_id))
            if b and b.tenant_id == _tid():
                last_scan = {
                    "lastScanAt": _iso(b.last_risk_scan_at),
                    "stats": b.last_risk_scan_stats_json or {},
                }
        return {"total": total, "openCount": open_count, "criticalOpenCount": critical, "byCode": by_code,
                "batchId": str(batch_id) if batch_id else None, "lastScan": last_scan}


from app.modules.graduation.services.graduation_risk_consistency import (
    accept_risk,
    close_risk,
    process_risk,
)

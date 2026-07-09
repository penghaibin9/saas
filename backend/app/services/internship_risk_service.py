"""岗位实习 · 风险处置闭环（P1-Stage3）。

风险单 t_risk_record 来源：系统预警 / 打卡异常转风险 / 指导转风险 / 人工创建。
状态机：PENDING_HANDLE 待处理 →(受理) PROCESSING 处理中 →(化解) RESOLVED 已化解 →(归档) CLOSED 已关闭。
升级 escalate 调整 risk_level（LOW→MEDIUM→HIGH），不改状态。
owner + 数据范围复用 internship_service：指导教师只能处置本人指导学生的风险，管理员全租户。
审计 target_type=RISK。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipRecord, RiskRecord, StudentProfile
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"PENDING_HANDLE": "待处理", "PROCESSING": "处理中",
                "RESOLVED": "已化解", "CLOSED": "已关闭"}
LEVEL_LABEL = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}
LEVEL_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, rid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=rid, target_type="RISK",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, rid) -> RiskRecord:
    r = db.get(RiskRecord, int(rid))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("风险单不存在")
    return r


def _ctx(db, r):
    rec = db.get(InternshipRecord, r.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return rec, stu


def _row(r, rec, stu):
    return {
        "id": str(r.id), "internId": str(r.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "enterpriseName": rec.enterprise_name if rec else "",
        "riskCode": r.risk_code, "riskTitle": r.risk_title,
        "riskLevel": r.risk_level, "riskLevelLabel": LEVEL_LABEL.get(r.risk_level, r.risk_level),
        "sourceModule": r.source_module, "ownerName": r.owner_name or "",
        "deadlineAt": _iso(r.deadline_at) or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "lastFollowAt": _iso(r.last_follow_at) or "", "lastFollowNote": r.last_follow_note or "",
        "createdAt": _iso(r.created_at) or "",
    }


def _scope_ctx(user):
    from app.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _owner_or_403(db, r, user, msg):
    scope, in_scope = _scope_ctx(user)
    rec, stu = _ctx(db, r)
    if not in_scope(scope, db, rec, stu):
        raise no_permission(msg)
    return rec, stu


def handle(user, risk_id, owner_name=None, deadline=None, comment="") -> dict:
    """受理：PENDING_HANDLE → PROCESSING，指定跟进责任人 + 截止 + 处理意见。"""
    if not (comment or "").strip() or len(comment.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "受理意见必填且不少于 5 字")
    with session() as db:
        r = _get(db, risk_id)
        _owner_or_403(db, r, user, "只能处置本人指导学生的风险")
        if r.status not in ("PENDING_HANDLE",):
            raise AppException("DATA_CONFLICT", "该风险单已受理，请刷新")
        r.status = "PROCESSING"
        r.owner_name = (owner_name or "").strip() or _op_name(user)
        if deadline:
            try:
                r.deadline_at = datetime.fromisoformat(str(deadline)[:19])
            except ValueError:
                r.deadline_at = None
        r.last_follow_at = datetime.utcnow()
        r.last_follow_note = comment.strip()
        r.version += 1
        _trail(db, r.id, "HANDLE", {"owner": r.owner_name, "comment": comment.strip()},
               operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "status": r.status, "statusLabel": STATUS_LABEL[r.status]}


def follow(user, risk_id, note="") -> dict:
    """跟进：追加一条跟进记录（不改状态，必须处理中）。"""
    if not (note or "").strip() or len(note.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "跟进说明必填")
    with session() as db:
        r = _get(db, risk_id)
        _owner_or_403(db, r, user, "只能跟进本人指导学生的风险")
        if r.status not in ("PROCESSING",):
            raise AppException("DATA_CONFLICT", "仅处理中的风险可跟进")
        r.last_follow_at = datetime.utcnow()
        r.last_follow_note = note.strip()
        r.version += 1
        _trail(db, r.id, "FOLLOW", {"note": note.strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "lastFollowAt": _iso(r.last_follow_at)}


def escalate(user, risk_id, level, note="") -> dict:
    """升级：调整风险等级（只能升不能降），写审计。"""
    if level not in ("MEDIUM", "HIGH"):
        raise AppException("VALIDATION_ERROR", "升级目标等级必须是 MEDIUM/HIGH")
    if not (note or "").strip() or len(note.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "升级原因必填")
    with session() as db:
        r = _get(db, risk_id)
        _owner_or_403(db, r, user, "只能升级本人指导学生的风险")
        if r.status == "CLOSED":
            raise AppException("DATA_CONFLICT", "已关闭的风险不可升级")
        if LEVEL_ORDER.get(level, 0) <= LEVEL_ORDER.get(r.risk_level, 0):
            raise AppException("DATA_CONFLICT", f"当前等级已为{LEVEL_LABEL.get(r.risk_level)}，不可降级/平级升级")
        old = r.risk_level
        r.risk_level = level
        r.last_follow_at = datetime.utcnow()
        r.last_follow_note = note.strip()
        r.version += 1
        _trail(db, r.id, "ESCALATE", {"from": old, "to": level, "note": note.strip()},
               operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "riskLevel": r.risk_level, "riskLevelLabel": LEVEL_LABEL[r.risk_level]}


def close(user, risk_id, result="RESOLVED", comment="") -> dict:
    """关闭：PROCESSING → RESOLVED/CLOSED。result=RESOLVED 记为已化解后关闭，UNRESOLVED 记为直接关闭。"""
    if result not in ("RESOLVED", "UNRESOLVED"):
        raise AppException("VALIDATION_ERROR", "关闭结论必须是 RESOLVED/UNRESOLVED")
    if not (comment or "").strip() or len(comment.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭说明必填且不少于 5 字")
    with session() as db:
        r = _get(db, risk_id)
        _owner_or_403(db, r, user, "只能关闭本人指导学生的风险")
        if r.status not in ("PROCESSING", "RESOLVED"):
            raise AppException("DATA_CONFLICT", "仅处理中/已化解的风险可关闭")
        r.status = "RESOLVED" if result == "RESOLVED" else "CLOSED"
        if result == "RESOLVED":
            r.status = "CLOSED"  # 化解后直接归档关闭；留痕区分 result
        r.last_follow_at = datetime.utcnow()
        r.last_follow_note = comment.strip()
        r.version += 1
        _trail(db, r.id, "CLOSE", {"result": result, "comment": comment.strip()},
               operator=_op_name(user))
        db.commit()
        return {"id": str(r.id), "status": r.status, "statusLabel": STATUS_LABEL[r.status]}


def list_risks(page, page_size, level=None, status=None, keyword=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        q = select(RiskRecord).where(RiskRecord.tenant_id == _tid(),
                                     RiskRecord.is_deleted.is_(False))
        if level:
            q = q.where(RiskRecord.risk_level == level)
        if status:
            q = q.where(RiskRecord.status == status)
        rows = db.scalars(q.order_by(RiskRecord.id.desc())).all()
        items = []
        for r in rows:
            rec, stu = _ctx(db, r)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(r, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_risk(rid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        r = _get(db, rid)
        rec, stu = _ctx(db, r)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该风险单不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "RISK",
            InternshipAuditTrail.target_id == r.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(r, rec, stu),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def export_risks(keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_risks(1, 100000, keyword=keyword, user=user)
    headers = ["学号", "姓名", "指导教师", "企业", "风险编码", "风险标题", "等级", "来源",
               "责任人", "状态", "最近跟进", "最近跟进说明"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["riskCode"], it["riskTitle"], it["riskLevelLabel"], it["sourceModule"],
             it["ownerName"], it["statusLabel"], it["lastFollowAt"], it["lastFollowNote"]]
            for it in items]
    wm = f"岗位实习中心·风险处置台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("风险处置台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "风险处置台账.xlsx", len(items))

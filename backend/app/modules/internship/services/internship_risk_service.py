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
from app.services.db_service import _as_id, _iso, _tid, session

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
    r = db.get(RiskRecord, _as_id(rid))
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
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
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


def student_help_report(user, body=None) -> dict:
    """学生轻量求助/风险上报：写入实习风险单（INT-R-HELP），由指导教师受理。

    不替代企业投诉台（complaint）；就业/监管政策不在此伪造闭环。
    """
    from app.modules.internship.services.internship_leave_service import _student_record

    b = body or {}
    title = (b.get("title") or b.get("riskTitle") or "").strip() or "学生实习求助"
    content = (b.get("content") or b.get("note") or b.get("reason") or "").strip()
    level = (b.get("riskLevel") or "MEDIUM").upper()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "求助说明不少于 5 字")
    if level not in ("LOW", "MEDIUM", "HIGH"):
        raise AppException("VALIDATION_ERROR", "riskLevel 须为 LOW/MEDIUM/HIGH")
    with session() as db:
        rec, stu = _student_record(db, user, for_write=True)
        open_help = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == rec.id,
            RiskRecord.risk_code == "INT-R-HELP",
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
            RiskRecord.is_deleted.is_(False))).first()
        if open_help:
            raise AppException("DATA_CONFLICT", "你已有未办结的求助单，请等待指导教师处理后再提交")
        r = RiskRecord(
            tenant_id=_tid(), internship_id=rec.id, risk_code="INT-R-HELP",
            risk_title=title[:200], risk_level=level, source_module="student_help",
            status="PENDING_HANDLE", last_follow_note=content[:500],
            owner_name=rec.advisor_name or None)
        db.add(r)
        db.flush()
        _trail(db, r.id, "STUDENT_HELP", {"title": title, "content": content[:200]},
               operator=(stu.real_name if stu else "学生"))
        if (rec.risk_level or "NONE") in ("NONE", "", "LOW") and level in ("MEDIUM", "HIGH"):
            rec.risk_level = level
        # 通知指导教师（outbox）
        try:
            from app.models import User
            from app.services.message_event_outbox_service import emit_message_event
            advisor = None
            if getattr(rec, "advisor_user_id", None):
                advisor = db.get(User, rec.advisor_user_id)
            if not advisor and (rec.advisor_name or "").strip():
                advisor = db.scalars(select(User).where(
                    User.tenant_id == _tid(), User.real_name == rec.advisor_name.strip(),
                    User.user_type == "TEACHER", User.is_deleted.is_(False),
                    User.status == "ACTIVE")).first()
            if advisor:
                emit_message_event(
                    db,
                    event_code="INTERNSHIP.RISK_CREATED",
                    source_module="internship",
                    source_biz_type="risk_record",
                    source_biz_id=int(r.id),
                    recipient_refs=[{"userId": int(advisor.id)}],
                    title=f"学生求助风险：{title[:40]}",
                    content=content[:500],
                    dedup_key=f"INTERNSHIP.RISK_CREATED:{r.id}:user:{advisor.id}",
                )
        except Exception:  # noqa: BLE001
            pass
        db.commit()
        try:
            from app.services.message_event_outbox_service import process_pending_outbox
            process_pending_outbox(limit=10, worker_id="internship-risk-inline")
        except Exception:  # noqa: BLE001
            pass
        return {"id": str(r.id), "status": r.status, "statusLabel": STATUS_LABEL[r.status],
                "riskTitle": r.risk_title, "riskLevel": r.risk_level,
                "message": "求助已提交，指导教师将跟进"}


def list_risks(page, page_size, level=None, status=None, keyword=None, user=None, batch_id=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        rec_ids = list(db.scalars(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id,
        )).all()) or [0]
        q = select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.is_deleted.is_(False),
            RiskRecord.internship_id.in_(rec_ids),
        )
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


def remind(user, risk_id, channel="站内消息") -> dict:
    """向风险责任人发送站内催办；无账号映射时明确失败，不伪造成功。"""
    from datetime import timedelta

    from app.models import User
    from app.services.message_event_outbox_service import emit_message_event, process_pending_outbox
    with session() as db:
        r = _get(db, risk_id)
        rec, stu = _owner_or_403(db, r, user, "只能催办本人数据范围内的风险")
        if r.status in ("RESOLVED", "CLOSED"):
            raise AppException("DATA_CONFLICT", "风险已结案，无需催办")
        recent = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == r.id,
            InternshipAuditTrail.target_type == "RISK", InternshipAuditTrail.action == "REMIND",
            InternshipAuditTrail.occurred_at >= datetime.utcnow() - timedelta(minutes=5))).first()
        if recent:
            raise AppException("DATA_CONFLICT", "5 分钟内已催办，请勿重复操作")
        owner_name = (r.owner_name or "").strip() or (rec.advisor_name if rec else "") or ""
        account = None
        if owner_name:
            account = db.scalars(select(User).where(
                User.tenant_id == _tid(), User.real_name == owner_name,
                User.user_type == "TEACHER", User.is_deleted.is_(False),
                User.status == "ACTIVE")).first()
        if not account and rec and getattr(rec, "advisor_user_id", None):
            account = db.get(User, rec.advisor_user_id)
        if not account:
            raise AppException("DATA_NOT_FOUND", "责任人账号未建立，无法发送催办")
        title = f"实习风险催办：{(r.risk_title or r.risk_code or '')[:40]}"
        content = (f"请及时跟进风险单 {r.risk_code or r.id}（学生 "
                   f"{stu.real_name if stu else '-'}）。催办渠道：{channel or '站内消息'}。")
        emit_message_event(
            db,
            event_code="INTERNSHIP.RISK_REMINDED",
            source_module="internship",
            source_biz_type="risk_record",
            source_biz_id=int(r.id),
            recipient_refs=[{"userId": int(account.id)}],
            content=content,
            title=title,
            dedup_key=f"INTERNSHIP.RISK_REMINDED:{r.id}:user:{account.id}",
        )
        _trail(db, r.id, "REMIND", {"channel": channel or "站内消息",
                                    "receiverId": str(account.id), "ownerName": owner_name},
               operator=_op_name(user))
        db.commit()
        try:
            process_pending_outbox(limit=20, worker_id="internship-inline")
        except Exception:  # noqa: BLE001
            pass
        return {"id": str(r.id), "reminded": True, "channel": channel or "站内消息",
                "receiverName": account.real_name or owner_name}


def export_risks(keyword=None, user=None, batch_id=None, level=None, status=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_risks(1, 100000, keyword=keyword, user=user, batch_id=batch_id,
                          level=level, status=status)
    headers = ["学号", "姓名", "指导教师", "企业", "风险编码", "风险标题", "等级", "来源",
               "责任人", "状态", "最近跟进", "最近跟进说明"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["riskCode"], it["riskTitle"], it["riskLevelLabel"], it["sourceModule"],
             it["ownerName"], it["statusLabel"], it["lastFollowAt"], it["lastFollowNote"]]
            for it in items]
    wm = f"岗位实习中心·风险处置台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("风险处置台账", headers, rows, watermark=wm)
    packed = xlsx_util.pack_xlsx_result(content, "风险处置台账.xlsx", len(items))
    if batch_id is not None:
        packed["batchId"] = str(batch_id)
    return packed

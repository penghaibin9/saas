"""SM14 intelligent FAQ support with deterministic three-unresolved human handoff."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models.internship import InternshipSupportSession
from app.modules.internship.services import internship_risk_service as risks
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services.db_service import _tid, session


FAQS = (
    ("CHECKIN", ("打卡", "签到", "定位", "位置"), "请先进入“实习打卡”查看当日状态。定位只在你主动点击打卡时采集；定位异常会在页面明确提示，可按学校规则申请补卡或免签。"),
    ("REPORT", ("周报", "日报", "月报", "总结", "报告"), "请进入岗位实习首页的“日报/周报/月报/实习总结”。已提交内容会保留审核状态，退回后按教师意见修改再提交。"),
    ("LEAVE", ("请假", "销假", "病假", "事假"), "请进入“实习请假”提交起止日期、类型和原因。病假或连续3天及以上请假需上传证明；返岗后按页面提示办理销假。"),
    ("AGREEMENT", ("协议", "三方", "签字", "签章"), "请进入“三方协议”查看当前版本和签署进度。只有当前正式版本完成学生、企业和学校确认后才会进入有效状态。"),
    ("INSURANCE", ("保险", "保单"), "请进入“实习保险”上传保单信息和凭证。材料提交后需等待学校核验，过期或被驳回的保单不会按有效保险计算。"),
    ("EXEMPTION", ("免实习", "免除实习", "升学", "参军"), "符合升学、参军、健康或学校认可情形时，可进入“免实习申请”填写原因、后续去向并上传佐证。只有学校审核通过后才正式生效。"),
    ("POSITION", ("岗位", "企业", "选岗", "自主实习"), "请先查看“企业岗位库/正式申请”。学校岗位和自主实习都必须走正式申请与审核流程，不能只靠口头确认改变实习去向。"),
    ("SCORE", ("成绩", "评分", "鉴定", "申诉"), "请进入“鉴定与成绩”查看当前评分事实。成绩发布后如对事实有异议，可按页面入口提交成绩申诉并等待学校复核。"),
)


def _faq_answer(message: str) -> tuple[str, str, bool]:
    text = str(message or "").strip()
    best = None
    best_score = 0
    for code, keywords, answer in FAQS:
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best = (code, answer)
            best_score = score
    if best:
        return best[0], best[1], True
    return (
        "GENERAL",
        "我暂时无法从岗位实习 FAQ 中准确定位这个问题。你可以补充“哪一步、页面提示什么、希望学校怎么处理”。如果连续三次仍未解决，系统会自动携带对话上下文转给指导教师。",
        False,
    )


def _context(db, user: dict, payload: dict, *, for_write: bool):
    record, student, batch_id = require_explicit_context(
        db, user, payload or {}, for_write=for_write)
    return record, student, int(batch_id)


def _owned_session(db, session_id, record, student, *, lock: bool = False):
    try:
        sid = int(session_id)
    except (TypeError, ValueError):
        raise not_found("客服会话不存在") from None
    query = select(InternshipSupportSession).where(
        InternshipSupportSession.id == sid,
        InternshipSupportSession.tenant_id == _tid(),
        InternshipSupportSession.internship_id == record.id,
        InternshipSupportSession.student_id == student.id,
        InternshipSupportSession.is_deleted.is_(False),
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise no_permission("无权访问该客服会话")
    return row


def _view(row: InternshipSupportSession) -> dict:
    history = list(row.context_json or [])
    return {
        "sessionId": str(row.id),
        "status": row.status,
        "unresolvedCount": int(row.unresolved_count or 0),
        "remainingBeforeHuman": max(0, 3 - int(row.unresolved_count or 0)),
        "history": history,
        "lastQuestion": row.last_question or "",
        "lastAnswer": row.last_answer or "",
        "transferredRiskId": str(row.transferred_risk_id or ""),
        "transferredAt": row.transferred_at.isoformat() + "Z" if row.transferred_at else "",
    }


def current(user: dict, *, batch_id, internship_id) -> dict:
    payload = {"batchId": batch_id, "internshipId": internship_id}
    with session() as db:
        record, student, _batch_id = _context(db, user, payload, for_write=False)
        row = db.scalars(select(InternshipSupportSession).where(
            InternshipSupportSession.tenant_id == _tid(),
            InternshipSupportSession.internship_id == record.id,
            InternshipSupportSession.student_id == student.id,
            InternshipSupportSession.is_deleted.is_(False),
        ).order_by(InternshipSupportSession.id.desc()).limit(1)).first()
        return _view(row) if row else {
            "sessionId": "", "status": "NEW", "unresolvedCount": 0,
            "remainingBeforeHuman": 3, "history": [], "transferredRiskId": "",
            "transferredAt": "",
        }


def ask(user: dict, body: dict) -> dict:
    payload = body or {}
    question = str(payload.get("message") or "").strip()
    if len(question) < 2:
        raise AppException("VALIDATION_ERROR", "请至少输入2个字的问题")
    if len(question) > 500:
        raise AppException("VALIDATION_ERROR", "单次问题不能超过500个字")
    faq_code, answer, matched = _faq_answer(question)

    with session() as db:
        record, student, batch_id = _context(db, user, payload, for_write=True)
        row = db.scalars(select(InternshipSupportSession).where(
            InternshipSupportSession.tenant_id == _tid(),
            InternshipSupportSession.internship_id == record.id,
            InternshipSupportSession.student_id == student.id,
            InternshipSupportSession.status == "ACTIVE",
            InternshipSupportSession.is_deleted.is_(False),
        ).order_by(InternshipSupportSession.id.desc()).limit(1).with_for_update()).first()
        if not row:
            row = InternshipSupportSession(
                tenant_id=_tid(), internship_id=record.id, batch_id=batch_id,
                student_id=student.id, status="ACTIVE", unresolved_count=0,
                context_json=[],
            )
            db.add(row)
            db.flush()

        history = list(row.context_json or [])
        history.append({
            "question": question,
            "answer": answer,
            "faqCode": faq_code,
            "matched": bool(matched),
            "askedAt": datetime.utcnow().isoformat() + "Z",
        })
        row.context_json = history[-12:]
        row.last_question = question
        row.last_answer = answer
        row.version = int(row.version or 0) + 1
        add_audit(
            db,
            target_type="SUPPORT_SESSION",
            target_id=row.id,
            action="SUPPORT_FAQ_ASK",
            user=user,
            batch_id=batch_id,
            detail={"faqCode": faq_code, "matched": bool(matched)},
        )
        db.commit()
        result = _view(row)
        result.update({"answer": answer, "faqCode": faq_code, "matched": bool(matched)})
        return result


def solved(user: dict, session_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student, batch_id = _context(db, user, payload, for_write=True)
        row = _owned_session(db, session_id, record, student, lock=True)
        if row.status == "TRANSFERRED":
            return _view(row)
        row.status = "SOLVED"
        row.version = int(row.version or 0) + 1
        add_audit(
            db, target_type="SUPPORT_SESSION", target_id=row.id,
            action="SUPPORT_SOLVED", user=user, batch_id=batch_id,
            detail={"unresolvedCount": int(row.unresolved_count or 0)},
        )
        db.commit()
        return _view(row)


def unresolved(user: dict, session_id, body: dict) -> dict:
    payload = body or {}
    transfer_payload = None
    with session() as db:
        record, student, batch_id = _context(db, user, payload, for_write=True)
        row = _owned_session(db, session_id, record, student, lock=True)
        if row.status == "TRANSFERRED":
            result = _view(row)
            result["transferred"] = True
            return result
        if row.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "当前客服会话已结束，请重新提问")
        next_count = int(row.unresolved_count or 0) + 1
        if next_count < 3:
            row.unresolved_count = next_count
            row.version = int(row.version or 0) + 1
            add_audit(
                db, target_type="SUPPORT_SESSION", target_id=row.id,
                action="SUPPORT_UNRESOLVED", user=user, batch_id=batch_id,
                detail={"unresolvedCount": next_count},
            )
            db.commit()
            result = _view(row)
            result["transferred"] = False
            return result

        history = list(row.context_json or [])[-6:]
        context_lines = []
        for item in history:
            context_lines.append(f"学生：{item.get('question', '')}")
            context_lines.append(f"客服：{item.get('answer', '')}")
        transfer_payload = {
            "batchId": str(batch_id),
            "internshipId": str(record.id),
            "riskLevel": "MEDIUM",
            "title": "智能客服三次未解决转人工",
            "content": ("智能客服连续三次未解决，自动转人工。\n" + "\n".join(context_lines))[:1800],
            "_sessionId": int(row.id),
            "_studentId": int(student.id),
            "_batchId": int(batch_id),
            "_recordId": int(record.id),
        }

    try:
        ticket = risks.student_help_report(user, transfer_payload)
    except AppException as exc:
        if "已有未办结的求助单" not in str(getattr(exc, "message", "") or ""):
            raise
        existing = risks.my_student_help(
            user,
            batch_id=transfer_payload["batchId"],
            internship_id=transfer_payload["internshipId"],
        )
        open_items = [
            item for item in (existing.get("items") or [])
            if item.get("status") in ("PENDING_HANDLE", "PROCESSING")
        ]
        if not open_items:
            raise
        ticket = open_items[0]

    with session() as db:
        record, student, batch_id = _context(db, user, payload, for_write=True)
        row = _owned_session(
            db, transfer_payload["_sessionId"], record, student, lock=True)
        row.unresolved_count = max(3, int(row.unresolved_count or 0))
        row.status = "TRANSFERRED"
        row.transferred_risk_id = int(ticket["id"])
        row.transferred_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        add_audit(
            db, target_type="SUPPORT_SESSION", target_id=row.id,
            action="SUPPORT_TRANSFER_TO_HUMAN", user=user, batch_id=batch_id,
            detail={
                "unresolvedCount": int(row.unresolved_count or 0),
                "riskId": str(ticket["id"]),
            },
        )
        db.commit()
        result = _view(row)
        result.update({
            "transferred": True,
            "message": "已自动携带最近对话转给指导教师，无需重复描述。",
        })
        return result

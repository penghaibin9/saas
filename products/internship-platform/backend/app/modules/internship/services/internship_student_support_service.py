"""SM14 intelligent FAQ support with deterministic three-unresolved human handoff."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models.internship import InternshipAuditTrail, InternshipSupportSession
from app.modules.internship.services import internship_risk_service as risks
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services.db_service import _tid, session


TRANSFER_AFTER_UNRESOLVED = 3

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
        "我暂时无法从岗位实习常见问题中准确定位这个问题。你可以补充“哪一步、页面提示什么、希望学校怎么处理”。如果连续三次仍未解决，系统会登记人工求助并附上最近对话。",
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


def _answer_state(db, row) -> dict:
    history = list(row.context_json or [])
    last = history[-1] if history else {}
    version = last.get("answerVersion")
    feedback = last.get("feedback")
    if type(version) is int and version > 0 and feedback in (None, "UNRESOLVED", "SOLVED"):
        return {"answerVersion": version, "feedback": feedback, "known": True}
    # 旧会话用原审计确认末轮事实，不能用累计次数猜测是否已评价。
    trail = db.scalar(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "SUPPORT_SESSION",
        InternshipAuditTrail.target_id == row.id,
    ).order_by(InternshipAuditTrail.id.desc()).limit(1))
    try:
        asked_at = datetime.fromisoformat(str(last.get("askedAt") or "").replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        asked_at = None
    actions = {"SUPPORT_FAQ_ASK": None, "SUPPORT_UNRESOLVED": "UNRESOLVED",
               "SUPPORT_SOLVED": "SOLVED", "SUPPORT_TRANSFER_TO_HUMAN": "UNRESOLVED"}
    if (last.get("question") and last.get("answer") and asked_at and trail
            and trail.action in actions and trail.occurred_at >= asked_at.replace(microsecond=0)):
        return {"answerVersion": int(row.version or 0), "feedback": actions[trail.action], "known": True}
    return {"answerVersion": None, "feedback": None, "known": False}


def _view(row: InternshipSupportSession, answer: dict) -> dict:
    history = list(row.context_json or [])
    return {
        "sessionId": str(row.id),
        "status": row.status,
        "unresolvedCount": int(row.unresolved_count or 0),
        "remainingBeforeHuman": max(0, TRANSFER_AFTER_UNRESOLVED - int(row.unresolved_count or 0)),
        "history": history,
        "awaitingFeedback": row.status == "ACTIVE" and answer["known"] and answer["feedback"] is None,
        "answerVersion": answer["answerVersion"],
        "feedbackNotice": "" if answer["known"] or row.status != "ACTIVE" else "这段历史回答的评价状态未能确认，请重新提问；原记录会保留。",
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
        return _view(row, _answer_state(db, row)) if row else {
            "sessionId": "", "status": "NEW", "unresolvedCount": 0,
            "remainingBeforeHuman": 3, "history": [], "transferredRiskId": "",
            "transferredAt": "",
            "awaitingFeedback": False, "answerVersion": None, "feedbackNotice": "",
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
        elif _view(row, _answer_state(db, row))["awaitingFeedback"]:
            raise AppException("DATA_CONFLICT", "请先评价当前回答，再继续提问", http_status=409)

        history = list(row.context_json or [])
        answer_version = int(row.version or 0) + 1
        history.append({
            "question": question,
            "answer": answer,
            "faqCode": faq_code,
            "matched": bool(matched),
            "askedAt": datetime.utcnow().isoformat() + "Z",
            "answerVersion": answer_version,
        })
        row.context_json = history[-12:]
        row.last_question = question
        row.last_answer = answer
        row.version = answer_version
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
        result = _view(row, _answer_state(db, row))
        result.update({"answer": answer, "faqCode": faq_code, "matched": bool(matched)})
        return result


def _feedback(user: dict, session_id, payload: dict, action: str) -> dict:
    expected = payload.get("answerVersion")
    if type(expected) is not int or expected < 1:
        raise AppException("DATA_CONFLICT", "缺少有效回答版本，请重新读取当前回答后评价", http_status=409)
    outbox_ids = []
    with session() as db:
        record, student, batch_id = _context(db, user, payload, for_write=True)
        row = _owned_session(db, session_id, record, student, lock=True)
        answer = _answer_state(db, row)
        if not answer["known"] or answer["answerVersion"] != expected:
            raise AppException("DATA_CONFLICT", "回答已变化，请重新读取后评价；本次未修改结果", http_status=409)
        if answer["feedback"]:
            if answer["feedback"] != action:
                raise AppException("DATA_CONFLICT", "这个回答已登记其他评价，不能重复修改", http_status=409)
            result = _view(row, answer)
            result["transferred"] = row.status == "TRANSFERRED"
            return result
        if row.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "当前客服会话已结束，请重新提问", http_status=409)
        history = [dict(item) for item in (row.context_json or [])]
        history[-1].update(answerVersion=expected, feedback=action,
                           feedbackAt=datetime.utcnow().isoformat() + "Z")
        row.context_json = history
        row.version = int(row.version or 0) + 1
        if action == "SOLVED":
            row.status = "SOLVED"
            audit_action = "SUPPORT_SOLVED"
        else:
            row.unresolved_count = int(row.unresolved_count or 0) + 1
            audit_action = "SUPPORT_UNRESOLVED"
            if row.unresolved_count >= TRANSFER_AFTER_UNRESOLVED:
                context_lines = []
                for item in history[-6:]:
                    context_lines.extend([f"学生：{item.get('question', '')}", f"客服：{item.get('answer', '')}"])
                ticket, outbox_ids = risks.student_help_in_session(db, user, {
                    "batchId": str(batch_id), "internshipId": str(record.id),
                    "riskLevel": "MEDIUM", "title": "智能客服三次未解决转人工",
                    "content": "智能客服连续三次未解决，自动转人工。\n" + "\n".join(context_lines),
                }, support_session_id=row.id)
                row.status = "TRANSFERRED"
                row.transferred_risk_id = int(ticket["id"])
                row.transferred_at = datetime.utcnow()
                audit_action = "SUPPORT_TRANSFER_TO_HUMAN"
        add_audit(db, target_type="SUPPORT_SESSION", target_id=row.id,
                  action=audit_action, user=user, batch_id=batch_id,
                  expected_version=expected, new_version=row.version,
                  detail={"answerVersion": expected, "feedback": action,
                          "unresolvedCount": int(row.unresolved_count or 0),
                          "riskId": str(row.transferred_risk_id or "")})
        db.commit()
        result = _view(row, _answer_state(db, row))
        result["transferred"] = row.status == "TRANSFERRED"
        if result["transferred"]:
            result["message"] = "最近对话已附到人工求助记录，可查看后续处理进度。"
    risks.deliver_student_help_events(outbox_ids)
    return result


def solved(user: dict, session_id, body: dict) -> dict:
    return _feedback(user, session_id, body or {}, "SOLVED")


def unresolved(user: dict, session_id, body: dict) -> dict:
    return _feedback(user, session_id, body or {}, "UNRESOLVED")

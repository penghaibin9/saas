"""帮助与反馈工单服务（历史欠账收口：t_feedback 表早已建好，此前无 API/前端）。

- 提交侧：学生/教师本人提交问题/建议/咨询/投诉；user_key=当前登录 userId（服务端解析，
  不取客户端传参），只读自己历史。
- 处理侧：学工/管理角色按租户查看、回复、流转状态（SUBMITTED→HANDLING→CLOSED）。
纯新增读写，不改动任何现有结构；租户隔离 + 提交人本人隔离。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

CATEGORIES = ("BUG", "SUGGESTION", "CONSULT", "COMPLAINT", "OTHER")
STATUSES = ("SUBMITTED", "HANDLING", "CLOSED")
L_STATUS = {"SUBMITTED": "待受理", "HANDLING": "处理中", "CLOSED": "已办结"}
L_CATEGORY = {"BUG": "问题反馈", "SUGGESTION": "建议", "CONSULT": "咨询",
              "COMPLAINT": "投诉", "OTHER": "其他"}


def _cur():
    """当前登录人：(userId 字符串, userType)。提交人身份一律服务端解析，不接受客户端指定。"""
    u = get_current_user_ctx() or {}
    return str(u.get("userId") or ""), (u.get("userType") or "STUDENT")


def _row(x) -> dict:
    return {
        "id": str(x.id), "userKey": x.user_key, "userType": x.user_type,
        "category": x.category, "categoryLabel": L_CATEGORY.get(x.category, x.category),
        "title": x.title or "", "content": x.content, "contact": x.contact or "",
        "status": x.status, "statusLabel": L_STATUS.get(x.status, x.status),
        "reply": x.reply or "", "handledBy": str(x.handled_by) if x.handled_by else "",
        "createdAt": _iso(x.created_at), "updatedAt": _iso(x.updated_at),
    }


# ═══════════ 提交侧（本人） ═══════════

def submit(body) -> dict:
    """本人提交反馈。user_key/user_type 由服务端按登录身份解析，忽略客户端传参。"""
    from app.models import Feedback
    uid, utype = _cur()
    if not uid:
        raise AppException("UNAUTHORIZED", "请先登录")
    content = (getattr(body, "content", None) or (body.get("content") if isinstance(body, dict) else "") or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "反馈内容不少于 5 字")
    if len(content) > 2000:
        content = content[:2000]
    category = (getattr(body, "category", None) or (body.get("category") if isinstance(body, dict) else "") or "OTHER").upper()
    if category not in CATEGORIES:
        category = "OTHER"
    title = (getattr(body, "title", None) or (body.get("title") if isinstance(body, dict) else "") or "").strip()[:120] or None
    contact = (getattr(body, "contact", None) or (body.get("contact") if isinstance(body, dict) else "") or "").strip()[:100] or None
    with session() as db:
        x = Feedback(tenant_id=_tid(), user_key=uid, user_type=utype, category=category,
                     title=title, content=content, contact=contact, status="SUBMITTED")
        db.add(x)
        db.commit()
        db.refresh(x)
        return _row(x)


def my_list(page=1, page_size=20) -> tuple[list[dict], int]:
    """本人反馈历史（严格按当前 userId 过滤，看不到他人）。"""
    from app.models import Feedback
    uid, _ = _cur()
    if not uid:
        raise AppException("UNAUTHORIZED", "请先登录")
    with session() as db:
        conds = [Feedback.tenant_id == _tid(), Feedback.user_key == uid,
                 Feedback.is_deleted.is_(False)]
        total = db.scalar(select(func.count()).select_from(Feedback).where(*conds)) or 0
        start = (max(1, page) - 1) * page_size
        rows = db.scalars(select(Feedback).where(*conds).order_by(
            Feedback.id.desc()).offset(start).limit(page_size)).all()
        return [_row(x) for x in rows], total


# ═══════════ 处理侧（学工/管理角色，按租户） ═══════════

def _load(db, feedback_id):
    from app.models import Feedback
    x = db.get(Feedback, int(feedback_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("反馈工单不存在")
    return x


def list_all(status=None, category=None, keyword=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """处理侧列表：本租户全部反馈，按状态/类型/关键词筛选，DB 分页。"""
    from app.models import Feedback
    with session() as db:
        conds = [Feedback.tenant_id == _tid(), Feedback.is_deleted.is_(False)]
        if status:
            conds.append(Feedback.status == status)
        if category:
            conds.append(Feedback.category == category)
        if keyword:
            like = f"%{keyword.strip()}%"
            conds.append((Feedback.title.like(like)) | (Feedback.content.like(like)))
        total = db.scalar(select(func.count()).select_from(Feedback).where(*conds)) or 0
        start = (max(1, page) - 1) * page_size
        rows = db.scalars(select(Feedback).where(*conds).order_by(
            Feedback.id.desc()).offset(start).limit(page_size)).all()
        return [_row(x) for x in rows], total


def get_one(feedback_id) -> dict:
    with session() as db:
        return _row(_load(db, feedback_id))


def handle(feedback_id, action, reply="") -> dict:
    """处理侧受理/回复/办结。action：ACCEPT(→HANDLING)/REPLY(填回复,→HANDLING)/CLOSE(→CLOSED)。
    受理人 handled_by=当前 userId。已办结不可再改。"""
    action = (action or "").upper()
    reply = (reply or "").strip()
    uid, _ = _cur()
    with session() as db:
        x = _load(db, feedback_id)
        if x.status == "CLOSED":
            raise AppException("DATA_CONFLICT", "工单已办结，不可再处理")
        if action == "ACCEPT":
            x.status = "HANDLING"
        elif action == "REPLY":
            if len(reply) < 1:
                raise AppException("VALIDATION_ERROR", "回复内容必填")
            x.reply, x.status = reply[:2000], "HANDLING"
        elif action == "CLOSE":
            if reply:
                x.reply = reply[:2000]
            x.status = "CLOSED"
        else:
            raise AppException("VALIDATION_ERROR", "无效操作（ACCEPT/REPLY/CLOSE）")
        x.handled_by = int(uid) if uid.isdigit() else x.handled_by
        x.version += 1
        db.commit()
        db.refresh(x)
        return _row(x)


def stats() -> dict:
    """处理侧汇总：按状态计数（供工作台角标）。"""
    from app.models import Feedback
    with session() as db:
        rows = db.execute(select(Feedback.status, func.count()).where(
            Feedback.tenant_id == _tid(), Feedback.is_deleted.is_(False)).group_by(Feedback.status)).all()
        by = {k: v for k, v in rows}
        return {"total": sum(by.values()), "submitted": by.get("SUBMITTED", 0),
                "handling": by.get("HANDLING", 0), "closed": by.get("CLOSED", 0)}

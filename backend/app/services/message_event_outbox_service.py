"""业务事件 Outbox：同事务写入、异步消费生成个人消息。

设计约束：
- 业务 service 只调用 emit_message_event(db, ...)，不直接构造 UnifiedMessage。
- 消费失败不得回滚已成功业务；重试后幂等（dedup_key + campaign 幂等）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

log = logging.getLogger("app.message_outbox")

# 首批登记的事件模板（请假样板）
_EVENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "LEAVE.APPROVED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "请假已通过",
        "require_ack": False,
    },
    "LEAVE.REJECTED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "RETURNED_NOTICE",
        "title": "请假被驳回",
        "require_ack": False,
    },
    "LEAVE.RETURNED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "RETURNED_NOTICE",
        "title": "请假被退回",
        "require_ack": False,
    },
    "LEAVE.OVERDUE": {
        "source_module": "student-affairs",
        "category": "REMINDER",
        "priority": "IMPORTANT",
        "message_type": "DEADLINE_REMINDER",
        "title": "请假已逾期",
        "require_ack": False,
    },
    "LEAVE.CLOSED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "STATUS_CHANGED",
        "title": "请假已关闭",
        "require_ack": False,
    },
    "LEAVE.RETURN_DONE": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "STATUS_CHANGED",
        "title": "销假完成",
        "require_ack": False,
    },
    "LEAVE.EXTEND_APPROVED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "续假已通过",
        "require_ack": False,
    },
    "LEAVE.EXTEND_REJECTED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "WORKFLOW_RESULT",
        "title": "续假被驳回",
        "require_ack": False,
    },
    "LEAVE.RETURN_REJECTED": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "RETURNED_NOTICE",
        "title": "销假被退回",
        "require_ack": False,
    },
    "INTERNSHIP.RISK_CREATED": {
        "source_module": "internship",
        "category": "WARNING",
        "priority": "IMPORTANT",
        "message_type": "INTERNSHIP_RISK",
        "title": "实习风险提醒",
        "require_ack": False,
    },
    "INTERNSHIP.RISK_REMINDED": {
        "source_module": "internship",
        "category": "REMINDER",
        "priority": "IMPORTANT",
        "message_type": "INTERNSHIP_RISK_REMIND",
        "title": "实习风险催办",
        "require_ack": False,
    },
    "WARNING.CREATED": {
        "source_module": "academic-affairs",
        "category": "WARNING",
        "priority": "IMPORTANT",
        "message_type": "ACAD_WARNING_NEW",
        "title": "学业预警通知",
        "require_ack": False,
    },
    "EXAM.ARRANGED": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "EXAM_NOTICE",
        "title": "考试安排通知",
        "require_ack": False,
    },
    "GRADUATION_DESIGN.DEFENSE_ARRANGED": {
        "source_module": "graduation",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "GRADUATION_DEFENSE_NOTIFY",
        "title": "答辩安排通知",
        "require_ack": False,
    },
    "GRADUATION_DESIGN.PLAGIARISM_DISPUTE_REVIEWED": {
        "source_module": "graduation",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "GRADUATION_PLAGIARISM_DISPUTE_REVIEWED",
        "title": "查重复查审核结果",
        "require_ack": False,
    },
    "COURSE.SCHEDULE_CHANGED": {
        "source_module": "academic-affairs",
        "category": "REMINDER",
        "priority": "NORMAL",
        "message_type": "SCHEDULE_CHANGE",
        "title": "课表变更通知",
        "require_ack": False,
    },
    "MESSAGE.ACK_NUDGE": {
        "source_module": "workbench-message",
        "category": "REMINDER",
        "priority": "IMPORTANT",
        "message_type": "ACK_NUDGE",
        "title": "请确认已读紧急消息",
        "require_ack": False,
    },
    "DISCIPLINE.NOTICE": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "处分通知",
        "require_ack": False,
    },
    "FUNDING.NOTICE": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "资助通知",
        "require_ack": False,
    },
    "AID.NOTICE": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "困难认定通知",
        "require_ack": False,
    },
    "RISK.ALERT": {
        "source_module": "student-affairs",
        "category": "WARNING",
        "priority": "IMPORTANT",
        "message_type": "RISK_ALERT",
        "title": "风险提醒",
        "require_ack": False,
    },
    "RISK.STATUS": {
        "source_module": "student-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "STATUS_CHANGED",
        "title": "风险状态变更",
        "require_ack": False,
    },
    "GRADE.CORRECTED": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "成绩已更正",
        "require_ack": False,
    },
    "GRADE.RECHECK_RESULT": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "成绩复查结果",
        "require_ack": False,
    },
    "STATUS_CHANGE.RESULT": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "学籍变更结果",
        "require_ack": False,
    },
    "STATUS_CHANGE.RETURNED": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "RETURNED_NOTICE",
        "title": "学籍变更退回",
        "require_ack": False,
    },
    "SCHEDULE_CHANGE.RESULT": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "调停课结果",
        "require_ack": False,
    },
    "SCHEDULE_CHANGE.RETURNED": {
        "source_module": "academic-affairs",
        "category": "BUSINESS",
        "priority": "IMPORTANT",
        "message_type": "RETURNED_NOTICE",
        "title": "调停课退回",
        "require_ack": False,
    },
    "COURSE.SCHEDULE_PUBLISHED": {
        "source_module": "academic-affairs",
        "category": "REMINDER",
        "priority": "NORMAL",
        "message_type": "PUBLISHED_NOTICE",
        "title": "课表已发布",
        "require_ack": False,
    },
    "INTERNSHIP.COUNSELOR_NOTICE": {
        "source_module": "internship",
        "category": "BUSINESS",
        "priority": "NORMAL",
        "message_type": "WORKFLOW_RESULT",
        "title": "实习辅导员通知",
        "require_ack": False,
    },
    "INTERNSHIP.WEEKLY_REMIND": {
        "source_module": "internship",
        "category": "REMINDER",
        "priority": "IMPORTANT",
        "message_type": "INTERNSHIP_WEEKLY_REMIND",
        "title": "实习周报提醒",
        "require_ack": False,
    },
}

_MAX_ATTEMPTS = 8
_LEASE_SECONDS = 120


def _utc_now() -> datetime:
    return datetime.utcnow()


def _backoff_seconds(attempt: int) -> int:
    return min(3600, 30 * (2 ** max(0, attempt - 1)))


def emit_message_event(    db,
    *,
    event_code: str,
    source_module: str,
    source_biz_type: str,
    source_biz_id: int,
    recipient_refs: list[dict],
    variables: Optional[dict] = None,
    action_key: Optional[str] = None,
    action_params: Optional[dict] = None,
    dedup_key: Optional[str] = None,
    content: Optional[str] = None,
    title: Optional[str] = None,
) -> Any:
    """同事务写入 outbox。调用方负责 commit。重复 dedup_key 返回已有行。"""
    from app.models import MessageEventOutbox

    code = str(event_code or "").strip().upper()
    if code not in _EVENT_TEMPLATES:
        raise AppException("VALIDATION_ERROR", f"未登记的消息事件码：{code}", http_status=422)
    if not recipient_refs:
        raise AppException("VALIDATION_ERROR", "recipient_refs 不能为空", http_status=422)

    key = dedup_key or f"{code}:{source_biz_type}:{int(source_biz_id)}"
    existed = db.scalar(select(MessageEventOutbox).where(
        MessageEventOutbox.tenant_id == _tid(),
        MessageEventOutbox.dedup_key == key,
        MessageEventOutbox.is_deleted.is_(False),
    ))
    if existed:
        return existed

    tpl = _EVENT_TEMPLATES[code]
    payload = {
        "title": title or tpl["title"],
        "content": content or "",
        "variables": variables or {},
        "actionKey": action_key,
        "actionParams": action_params or {},
        "template": code,
    }
    row = MessageEventOutbox(
        tenant_id=_tid(),
        event_code=code,
        source_module=source_module or tpl["source_module"],
        source_biz_type=source_biz_type,
        source_biz_id=int(source_biz_id),
        payload_json=payload,
        recipient_refs_json=list(recipient_refs),
        dedup_key=key[:120],
        status="PENDING",
        attempt_count=0,
        occurred_at=_utc_now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existed = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.dedup_key == key,
            MessageEventOutbox.is_deleted.is_(False),
        ))
        if existed:
            return existed
        raise
    return row


def emit_receiver_notice(
    db,
    *,
    event_code: str,
    source_module: str,
    source_biz_type: str,
    source_biz_id: int,
    receiver_id: int,
    title: str,
    content: str,
    receiver_as: str = "student",  # student | user
    action_key: str | None = None,
    action_params: dict | None = None,
    dedup_extra: str = "",
):
    rid = int(receiver_id or 0)
    if rid <= 0:
        return None
    refs = [{"userId": rid}] if receiver_as == "user" else [{"studentId": rid}]
    key = f"{event_code}:{source_biz_type}:{int(source_biz_id)}:{receiver_as}:{rid}:{dedup_extra}"[:120]
    return emit_message_event(
        db,
        event_code=event_code,
        source_module=source_module,
        source_biz_type=source_biz_type,
        source_biz_id=int(source_biz_id),
        recipient_refs=refs,
        title=title,
        content=content,
        action_key=action_key,
        action_params=action_params,
        dedup_key=key,
    )


def try_process_pending_outbox(limit: int = 30, worker_id: str = "biz-inline") -> None:
    """业务 commit 后尽力同步消费 outbox；失败由调度重试，绝不回滚业务。"""
    try:
        process_pending_outbox(limit=limit, worker_id=worker_id)
    except Exception:  # noqa: BLE001
        log.exception("inline outbox drain failed worker=%s", worker_id)


def _deliver_outbox_row(db, row) -> None:
    from app.models import MessageCampaign, UnifiedMessage

    tpl = _EVENT_TEMPLATES.get(row.event_code) or {}
    payload = row.payload_json or {}
    title = (payload.get("title") or tpl.get("title") or row.event_code)[:200]
    content = (payload.get("content") or "")[:2000]
    refs = row.recipient_refs_json or []

    # 解析：优先 userId；studentId → login_name 映射；无法映射时用学籍 id 作 receiver_id 兼容
    from app.models import StudentProfile, User
    targets: list[tuple[int | None, int | None]] = []  # (user_id, legacy_receiver_id)
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        uid = ref.get("userId") or ref.get("user_id")
        sid = ref.get("studentId") or ref.get("student_id")
        try:
            uid_i = int(uid) if uid else None
        except (TypeError, ValueError):
            uid_i = None
        try:
            sid_i = int(sid) if sid else None
        except (TypeError, ValueError):
            sid_i = None
        if uid_i:
            targets.append((uid_i, sid_i or uid_i))
            continue
        if sid_i:
            prof = db.scalar(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == sid_i,
                StudentProfile.is_deleted.is_(False),
            ))
            mapped = None
            if prof is not None:
                # 经账号绑定解析（阶段 C）：学号更正不影响历史消息的收件人映射
                from app.services import student_account_link_service as link_svc
                mapped = link_svc.resolve_user_id_for_student(
                    db, tenant_id=_tid(), student_id=prof.id,
                    student_no=prof.student_no, require_active_account=False)
            targets.append((int(mapped) if mapped else None, sid_i))

    if not targets:
        raise AppException("VALIDATION_ERROR", "无有效接收人")

    # SYSTEM campaign（一事件一单，幂等用 dedup）
    camp = None
    if row.campaign_id:
        camp = db.get(MessageCampaign, row.campaign_id)
    if not camp:
        camp = MessageCampaign(
            tenant_id=_tid(),
            title=title,
            content_plain=content or title,
            summary=(content or title)[:120],
            category=tpl.get("category") or "BUSINESS",
            priority=tpl.get("priority") or "NORMAL",
            status="PUBLISHED",
            source_kind="BUSINESS_EVENT",
            source_module=row.source_module,
            source_biz_type=row.source_biz_type,
            source_biz_id=row.source_biz_id,
            content_mode="SHARED",
            sender_user_id=0,
            sender_name_snapshot="系统",
            sender_role_snapshot="SYSTEM",
            publish_mode="IMMEDIATE",
            require_ack=bool(tpl.get("require_ack")),
            emergency=False,
            action_key=payload.get("actionKey"),
            action_params_json=payload.get("actionParams"),
            channels_json=["IN_APP"],
            idempotency_key=f"evt:{row.dedup_key}"[:80],
            recipient_count=len(targets),
            delivered_count=0,
            published_at=_utc_now(),
            created_by=0,
        )
        db.add(camp)
        db.flush()
        row.campaign_id = camp.id

    now = _utc_now()
    written = 0
    for user_id, legacy_rid in targets:
        rid = int(legacy_rid or user_id or 0)
        if rid <= 0 and not user_id:
            continue
        # 幂等：同 campaign + receiver_user_id（或 legacy receiver_id）
        exists_q = [
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.campaign_id == camp.id,
            UnifiedMessage.is_deleted.is_(False),
        ]
        if user_id:
            exists_q.append(UnifiedMessage.receiver_user_id == int(user_id))
        else:
            exists_q.append(UnifiedMessage.receiver_id == rid)
            exists_q.append(UnifiedMessage.receiver_user_id.is_(None))
        if db.scalar(select(UnifiedMessage.id).where(*exists_q)):
            continue
        db.add(UnifiedMessage(
            tenant_id=_tid(),
            receiver_id=rid,
            receiver_user_id=int(user_id) if user_id else None,
            receiver_type="STUDENT" if legacy_rid else "UNKNOWN",
            receiver_context_key="GLOBAL",
            campaign_id=camp.id,
            title=title,
            content=content,
            message_type=tpl.get("message_type") or "BUSINESS",
            category=tpl.get("category") or "BUSINESS",
            priority=tpl.get("priority") or "NORMAL",
            status="UNREAD",
            require_ack=bool(tpl.get("require_ack")),
            source_module=row.source_module,
            source_biz_id=row.source_biz_id,
            action_key=payload.get("actionKey"),
            action_params_json=payload.get("actionParams"),
            delivery_status="DELIVERED",
            delivered_at=now,
            rendered_content_plain=content,
        ))
        written += 1
    camp.delivered_count = int(camp.delivered_count or 0) + written
    camp.recipient_count = max(int(camp.recipient_count or 0), len(targets))
    camp.status = "PUBLISHED"
    row.status = "SUCCEEDED"
    row.processed_at = now
    row.last_error_code = None
    row.locked_by = None
    row.locked_at = None
    row.lease_expires_at = None


def process_pending_outbox(*, limit: int = 20, worker_id: str = "scheduler") -> int:
    """领取并处理 PENDING/RETRY_WAIT 事件；返回成功条数。"""
    from app.models import MessageEventOutbox

    done = 0
    now = _utc_now()
    with session() as db:
        rows = db.scalars(
            select(MessageEventOutbox).where(
                MessageEventOutbox.tenant_id == _tid(),
                MessageEventOutbox.is_deleted.is_(False),
                MessageEventOutbox.status.in_(("PENDING", "RETRY_WAIT")),
                or_(
                    MessageEventOutbox.next_retry_at.is_(None),
                    MessageEventOutbox.next_retry_at <= now,
                ),
            ).order_by(MessageEventOutbox.id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).all()
        claimed = []
        for row in rows:
            # 简单租约：跳过未过期锁
            if row.lease_expires_at and row.lease_expires_at > now and row.locked_by != worker_id:
                continue
            row.status = "PROCESSING"
            row.locked_by = worker_id
            row.locked_at = now
            row.lease_expires_at = now + timedelta(seconds=_LEASE_SECONDS)
            row.attempt_count = int(row.attempt_count or 0) + 1
            claimed.append(row)
        if claimed:
            db.commit()

    for row_id in [r.id for r in claimed]:
        with session() as db:
            row = db.get(MessageEventOutbox, row_id)
            now = _utc_now()
            if (
                not row
                or row.status != "PROCESSING"
                or row.locked_by != worker_id
                or not row.lease_expires_at
                or row.lease_expires_at <= now
            ):
                continue
            try:
                _deliver_outbox_row(db, row)
                db.commit()
                done += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                with session() as db2:
                    row2 = db2.get(MessageEventOutbox, row_id)
                    if not row2 or row2.locked_by != worker_id:
                        continue
                    attempt = int(row2.attempt_count or 1)
                    row2.last_error_code = (type(exc).__name__)[:80]
                    row2.locked_by = None
                    row2.locked_at = None
                    row2.lease_expires_at = None
                    if attempt >= _MAX_ATTEMPTS:
                        row2.status = "DEAD"
                    else:
                        row2.status = "RETRY_WAIT"
                        row2.next_retry_at = _utc_now() + timedelta(seconds=_backoff_seconds(attempt))
                    db2.commit()
                log.exception("outbox process failed id=%s", row_id)
    return done


def list_dead_outbox(*, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """死信 outbox 台账（status=DEAD）。"""
    from app.models import MessageEventOutbox
    from app.services.db_service import _iso

    with session() as db:
        conds = [
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.is_deleted.is_(False),
            MessageEventOutbox.status == "DEAD",
        ]
        from sqlalchemy import func

        total = db.scalar(select(func.count()).select_from(MessageEventOutbox).where(*conds)) or 0
        rows = db.scalars(
            select(MessageEventOutbox).where(*conds)
            .order_by(MessageEventOutbox.id.desc())
            .offset(max(0, (page - 1) * page_size)).limit(page_size)
        ).all()
        items = [{
            "outboxId": str(r.id),
            "kind": "EVENT_OUTBOX",
            "eventCode": r.event_code,
            "sourceModule": r.source_module,
            "sourceBizType": r.source_biz_type,
            "sourceBizId": str(r.source_biz_id),
            "status": r.status,
            "attemptCount": r.attempt_count,
            "lastError": r.last_error_code,
            "dedupKey": r.dedup_key,
            "updatedAt": _iso(r.updated_at) if r.updated_at else None,
        } for r in rows]
        return items, int(total)


def retry_dead_outbox(outbox_id: int) -> dict:
    """将 DEAD outbox 重置为 PENDING 以便调度重试。"""
    from app.models import MessageEventOutbox

    with session() as db:
        row = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.id == int(outbox_id),
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.is_deleted.is_(False),
        ))
        if not row:
            raise AppException("DATA_NOT_FOUND", "Outbox 记录不存在", http_status=404)
        if row.status != "DEAD":
            raise AppException("DATA_CONFLICT", "仅死信可重试", http_status=409)
        row.status = "PENDING"
        row.next_retry_at = None
        row.last_error_code = None
        row.attempt_count = 0
        row.locked_by = None
        row.locked_at = None
        row.lease_expires_at = None
        row.version = int(row.version or 0) + 1
        db.commit()
        return {"outboxId": str(row.id), "status": "PENDING"}


def process_all_tenants(limit_per_tenant: int = 20) -> int:
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    total = 0
    db = get_sessionmaker()()
    try:
        tids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
    finally:
        db.close()
    for tid in tids:
        set_tenant({"tenantId": str(tid)})
        try:
            total += process_pending_outbox(limit=limit_per_tenant)
        except Exception:  # noqa: BLE001
            log.exception("outbox tenant failed tid=%s", tid)
        finally:
            set_tenant(None)
    return total

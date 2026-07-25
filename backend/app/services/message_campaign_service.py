"""消息发布单服务：草稿 / 预览绑定 / 受理发布 / 撤回。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, not_found, no_permission
from app.core.permissions import has_permission
from app.services import message_audience_service as audience_svc
from app.services import message_delivery_service as delivery_svc
from app.services.db_service import _iso, _tid, session

# 进程内待投递队列（开发/测试）；生产应写入调度表由 run_scheduled_jobs 领取。
_PENDING_DELIVERIES: list[dict] = []


def _uid(user: dict | None) -> int:
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user)


def _utc_now() -> datetime:
    from app.core.timeutil import utc_now_naive
    return utc_now_naive()


def _parse_dt(raw) -> Optional[datetime]:
    from app.core.timeutil import parse_api_datetime
    return parse_api_datetime(raw)


def _can_publish(user: dict) -> bool:
    return any(has_permission(user, c) for c in (
        "workbench.message.publish",
        "workbench.message.class.publish",
        "workbench.message.college.publish",
        "workbench.message.schoolStudent.publish",
        "workbench.message.schoolStaff.publish",
        "workbench.message.schoolAll.publish",
    ))


def _campaign_dict(row, *, attachments: list | None = None) -> dict:
    return {
        "campaignId": str(row.id),
        "title": row.title,
        "summary": row.summary,
        "category": row.category,
        "priority": row.priority,
        "status": row.status,
        "requireAck": bool(row.require_ack),
        "pinned": bool(row.pinned),
        "emergency": bool(row.emergency),
        "publishMode": row.publish_mode,
        "scheduledAt": _iso(row.scheduled_at) if row.scheduled_at else None,
        "publishedAt": _iso(row.published_at) if row.published_at else None,
        "expireAt": _iso(row.expire_at) if row.expire_at else None,
        "ackDeadlineAt": _iso(row.ack_deadline_at) if getattr(row, "ack_deadline_at", None) else None,
        "deliveryMode": getattr(row, "delivery_mode", None) or "ASYNC",
        "workflowInstanceId": str(row.workflow_instance_id) if row.workflow_instance_id else None,
        "recipientCount": int(row.recipient_count or 0),
        "deliveredCount": int(row.delivered_count or 0),
        "readCount": int(row.read_count or 0),
        "ackCount": int(row.ack_count or 0),
        "failureCount": int(row.failure_count or 0),
        "audienceFingerprint": row.audience_fingerprint,
        "orgName": row.org_name_snapshot,
        "senderName": row.sender_name_snapshot,
        "version": int(row.version or 0),
        "createdAt": _iso(row.created_at) if row.created_at else None,
        "withdrawnAt": _iso(row.withdrawn_at) if row.withdrawn_at else None,
        "withdrawReason": row.withdraw_reason,
        "attachments": attachments or [],
    }


def _open_review_workflow(db, camp, applicant_id: int) -> int | None:
    """紧急/全校审核接入审批中心 WorkflowInstance。"""
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled

    wf_code = "MESSAGE_CAMPAIGN_REVIEW"
    try:
        ensure_workflow_enabled(db, _tid(), wf_code)
    except Exception:  # noqa: BLE001
        pass
    node = "SCHOOL_REVIEW" if bool(camp.emergency) else "STUDENT_AFFAIRS_REVIEW"
    inst = WorkflowInstance(
        tenant_id=_tid(),
        workflow_code=wf_code,
        source_module="workbench-message",
        source_biz_type="MESSAGE_CAMPAIGN",
        source_biz_id=int(camp.id),
        applicant_id=int(applicant_id or 0),
        title=f"消息审核：{(camp.title or '')[:80]}",
        status="RUNNING",
        current_node=node,
        remark=camp.sender_name_snapshot or "",
    )
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(
        tenant_id=_tid(),
        instance_id=inst.id,
        node_code=node,
        assignee_id=0,
        status="PENDING",
        remark="紧急/全校消息审核",
    ))
    db.add(UnifiedTodo(
        tenant_id=_tid(),
        source_module="workbench-message",
        source_biz_type="MESSAGE_CAMPAIGN",
        source_biz_id=int(camp.id),
        todo_type="MESSAGE_CAMPAIGN_REVIEW",
        assignee_id=0,
        title=f"待审消息：{(camp.title or '')[:80]}",
        status="PENDING",
    ))
    camp.workflow_instance_id = inst.id
    return inst.id


def _sanitize_plain_and_html(content_plain: str, content_html: str | None) -> tuple[str, str | None]:
    from app.services.message_html_sanitize import sanitize_message_html, strip_to_plain
    plain = strip_to_plain(content_plain or "")
    html = sanitize_message_html(content_html) if content_html else None
    return plain, html


def create_draft(user: dict, body: dict) -> dict:
    if not _can_publish(user):
        raise no_permission("无消息发布权限")
    from app.models import MessageAudience, MessageCampaign

    title = (body.get("title") or "").strip()
    raw_content = (body.get("contentPlain") or body.get("content_plain") or "").strip()
    raw_html = body.get("contentHtml") or body.get("content_html")
    content, content_html = _sanitize_plain_and_html(raw_content, raw_html)
    if len(title) < 4 or len(title) > 100:
        raise AppException("VALIDATION_ERROR", "标题需 4–100 字", http_status=422)
    if not content:
        raise AppException("VALIDATION_ERROR", "正文不能为空", http_status=422)

    category = str(body.get("category") or "ANNOUNCEMENT").upper()
    priority = str(body.get("priority") or "NORMAL").upper()
    emergency = bool(body.get("emergency")) or priority == "EMERGENCY" or category == "EMERGENCY"
    if emergency:
        priority = "EMERGENCY"
        category = "EMERGENCY"
        if not (
            has_permission(user, "workbench.message.emergency.submit")
            or has_permission(user, "workbench.message.schoolAll.publish")
            or has_permission(user, "*")
        ):
            # 辅导员本班紧急：允许提交但标记 emergency；全校紧急另需审核
            if not has_permission(user, "workbench.message.class.publish"):
                raise no_permission("无紧急消息提交权限")

    require_ack = bool(body.get("requireAck"))
    if emergency and body.get("requireAck") is None:
        require_ack = True

    summary = (body.get("summary") or "").strip() or content[:120]
    idem = body.get("idempotencyKey") or body.get("requestId")
    expire_at = _parse_dt(body.get("expireAt") or body.get("expire_at"))
    ack_deadline = _parse_dt(body.get("ackDeadlineAt") or body.get("ack_deadline_at"))

    from app.services.message_action_registry import validate_action
    action_key, action_params = validate_action(body.get("actionKey"), body.get("actionParams"))

    with session() as db:
        if idem:
            existed = db.scalar(select(MessageCampaign).where(
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.idempotency_key == str(idem),
                MessageCampaign.is_deleted.is_(False),
            ))
            if existed:
                return _campaign_dict(existed)

        camp = MessageCampaign(
            tenant_id=_tid(),
            title=title,
            content_plain=content,
            content_html=content_html,
            summary=summary,
            category=category,
            priority=priority,
            status="DRAFT",
            source_kind="HUMAN",
            content_mode="SHARED",
            sender_user_id=_uid(user),
            sender_context_id=str(user.get("activeContextId") or "") or None,
            sender_name_snapshot=str(user.get("realName") or ""),
            sender_role_snapshot=str(user.get("currentRoleCode") or ""),
            org_name_snapshot=None,
            publish_mode=str(body.get("publishMode") or "IMMEDIATE").upper(),
            scheduled_at=_parse_dt(body.get("scheduledAt")),
            expire_at=expire_at,
            ack_deadline_at=ack_deadline,
            require_ack=require_ack,
            pinned=bool(body.get("pinned")),
            emergency=emergency,
            action_key=action_key,
            action_params_json=action_params,
            channels_json=body.get("channels") or ["IN_APP"],
            idempotency_key=str(idem) if idem else None,
            created_by=_uid(user),
        )
        db.add(camp)
        db.flush()

        for a in body.get("audiences") or []:
            target_ids = a.get("targetIds") or []
            db.add(MessageAudience(
                tenant_id=_tid(),
                campaign_id=camp.id,
                audience_type=str(a.get("type") or "").upper(),
                include_or_exclude=str(a.get("includeOrExclude") or "INCLUDE").upper(),
                target_id=int(target_ids[0]) if target_ids else None,
                rule_json=a,
                created_by=_uid(user),
            ))
        db.commit()
        db.refresh(camp)
        return _campaign_dict(camp)


def list_campaigns(user: dict, *, status: str | None = None,
                   page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    if not (_can_publish(user) or has_permission(user, "workbench.message.emergency.approve")):
        raise no_permission("无消息发布/审核权限")
    from app.models import MessageCampaign
    with session() as db:
        conds = [
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ]
        can_review = has_permission(user, "workbench.message.emergency.approve")
        school_view = (
            has_permission(user, "workbench.message.schoolAll.publish")
            or has_permission(user, "workbench.message.statistics.view")
        )
        # 非校级：本人发布；审核员额外可见待审单
        # sender_user_id=0 的历史演示单：用 sender_context_id 兜底认领，避免修复 _uid 后列表“失踪”
        if not school_view:
            uid = _uid(user)
            ctx = str(user.get("activeContextId") or "").strip()
            own = MessageCampaign.sender_user_id == uid
            if ctx:
                own = or_(
                    own,
                    and_(
                        MessageCampaign.sender_user_id == 0,
                        MessageCampaign.sender_context_id == ctx,
                    ),
                )
            if can_review:
                conds.append(or_(own, MessageCampaign.status == "PENDING_REVIEW"))
            else:
                conds.append(own)
        if status:
            conds.append(MessageCampaign.status == status.upper())
        total = db.scalar(select(func.count()).select_from(MessageCampaign).where(*conds)) or 0
        rows = db.scalars(
            select(MessageCampaign).where(*conds)
            .order_by(MessageCampaign.created_at.desc(), MessageCampaign.id.desc())
            .offset(max(0, (page - 1) * page_size)).limit(page_size)
        ).all()
        return [_campaign_dict(r) for r in rows], int(total)


def get_campaign(user: dict, campaign_id: str) -> dict:
    if not (_can_publish(user) or has_permission(user, "workbench.message.emergency.approve")):
        raise no_permission("无消息发布/审核权限")
    from app.models import MessageCampaign
    with session() as db:
        try:
            cid = int(campaign_id)
        except (TypeError, ValueError):
            raise not_found("发布单不存在")
        row = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not row:
            raise not_found("发布单不存在")
        is_owner = row.sender_user_id == _uid(user)
        can_review = has_permission(user, "workbench.message.emergency.approve")
        school_view = (
            has_permission(user, "workbench.message.schoolAll.publish")
            or has_permission(user, "workbench.message.statistics.view")
        )
        if not is_owner and not school_view:
            if not (can_review and row.status == "PENDING_REVIEW"):
                raise not_found("发布单不存在")
        d = _campaign_dict(row, attachments=_list_attachments(db, row.id))
        d["contentPlain"] = row.content_plain
        d["contentHtml"] = row.content_html
        return d


def _list_attachments(db, campaign_id: int) -> list[dict]:
    from app.models import MessageAttachment
    rows = db.scalars(
        select(MessageAttachment).where(
            MessageAttachment.tenant_id == _tid(),
            MessageAttachment.campaign_id == int(campaign_id),
            MessageAttachment.is_deleted.is_(False),
        ).order_by(MessageAttachment.sort_no.asc(), MessageAttachment.id.asc())
    ).all()
    return [{
        "attachmentId": str(r.id),
        "fileId": str(r.file_id),
        "fileName": r.file_name_snapshot,
        "sortNo": r.sort_no,
    } for r in rows]


def add_campaign_attachment(user: dict, campaign_id: str, *, file_id: int,
                            file_name: str | None = None) -> dict:
    if not _can_publish(user):
        raise no_permission("无消息发布权限")
    from app.models import MessageAttachment, MessageCampaign
    with session() as db:
        try:
            cid = int(campaign_id)
            fid = int(file_id)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "附件参数无效", http_status=422)
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        if camp.sender_user_id != _uid(user) and not has_permission(user, "*"):
            raise no_permission("只能为自己的发布单添加附件")
        if camp.status not in ("DRAFT", "RETURNED", "PENDING_REVIEW", "APPROVED", "SCHEDULED"):
            raise AppException("DATA_CONFLICT", "当前状态不可添加附件")
        att = MessageAttachment(
            tenant_id=_tid(),
            campaign_id=cid,
            file_id=fid,
            file_name_snapshot=(file_name or "")[:200] or None,
            sort_no=0,
            created_by=_uid(user),
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        return {
            "attachmentId": str(att.id),
            "fileId": str(att.file_id),
            "fileName": att.file_name_snapshot,
        }


def _needs_review(user: dict, camp, audience_rules: list[dict]) -> bool:
    """全校范围、紧急、重要全校公告进入审核；发布人与终审人不得为同一人。"""
    types = {str(a.get("type") or "").upper() for a in (audience_rules or [])}
    school_scope = bool(types & {"ALL_STUDENT", "ALL_STAFF", "ALL_USERS"})
    if camp.emergency:
        return True
    if school_scope and str(camp.priority or "").upper() in ("IMPORTANT", "EMERGENCY"):
        return True
    if school_scope and str(camp.category or "").upper() == "EMERGENCY":
        return True
    return False


def publish_campaign(user: dict, campaign_id: str, *,
                     preview_token: str, audience_fingerprint: str,
                     version: int) -> dict:
    if not _can_publish(user):
        raise no_permission("无消息发布权限")
    from app.models import MessageCampaign
    from app.services import message_governance_service as gov

    gov.assert_publish_rate(_uid(user))

    with session() as db:
        try:
            cid = int(campaign_id)
        except (TypeError, ValueError):
            raise not_found("发布单不存在")
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        if camp.sender_user_id != _uid(user):
            raise no_permission("只能发布本人的草稿")
        if int(camp.version or 0) != int(version):
            raise AppException("DATA_CONFLICT", "发布单已被修改，请刷新后重试",
                               details={"reason": "VERSION_CONFLICT"})
        if camp.status not in ("DRAFT", "APPROVED", "RETURNED"):
            raise AppException("DATA_CONFLICT", f"当前状态不可发布：{camp.status}",
                               details={"reason": "INVALID_STATUS"})

        rules = audience_svc.audiences_from_campaign_rules(db, camp.id)

    # 预览令牌在进程外：允许按草稿规则重算（指纹须一致），避免重启后「有预览人数却发不出去、发布记录像空的」
    user_ids = audience_svc.resolve_for_publish(
        user,
        preview_token=preview_token,
        audience_fingerprint=audience_fingerprint,
        audiences=rules,
    )
    if not user_ids:
        raise AppException(
            "VALIDATION_ERROR",
            "接收人为 0：所选范围内没有已开通账号的学生/教职工，无法发布。"
            "请先确认学籍已开账号，或改选有账号的班级后再预览。"
            "（本地草稿不会出现在发布记录；已创建的草稿可在发布记录中继续处理）",
            details={"reason": "AUDIENCE_EMPTY_RECIPIENTS"},
            http_status=422,
        )

    with session() as db:
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        if int(camp.version or 0) != int(version):
            raise AppException("DATA_CONFLICT", "发布单已被修改，请刷新后重试",
                               details={"reason": "VERSION_CONFLICT"})
        if camp.status not in ("DRAFT", "APPROVED", "RETURNED"):
            raise AppException("DATA_CONFLICT", f"当前状态不可发布：{camp.status}",
                               details={"reason": "INVALID_STATUS"})
        rules = audience_svc.audiences_from_campaign_rules(db, camp.id)
        if camp.status != "APPROVED" and _needs_review(user, camp, rules):
            camp.status = "PENDING_REVIEW"
            camp.audience_fingerprint = audience_fingerprint
            camp.recipient_count = len(user_ids)
            camp.version = int(camp.version or 0) + 1
            _open_review_workflow(db, camp, _uid(user))
            db.commit()
            return {
                "campaignId": str(camp.id),
                "status": camp.status,
                "acceptedAt": _iso(_utc_now()),
                "recipientCount": camp.recipient_count,
                "workflowInstanceId": str(camp.workflow_instance_id) if camp.workflow_instance_id else None,
                "message": "已提交审核，通过后将开始投递",
            }

        quiet = gov.apply_quiet_hours_policy(
            emergency=bool(camp.emergency),
            publish_mode=str(camp.publish_mode or "IMMEDIATE"),
            scheduled_at=camp.scheduled_at,
        )
        if quiet.get("note"):
            camp.remark = ((camp.remark or "") + "\n" + str(quiet["note"]))[:500]
        if quiet.get("quietBypassed"):
            camp.remark = ((camp.remark or "") + "\n紧急消息绕过静默时段")[:500]
        if quiet.get("publishMode") == "SCHEDULED" and quiet.get("scheduledAt"):
            camp.publish_mode = "SCHEDULED"
            camp.scheduled_at = quiet["scheduledAt"]

        # 定时发布：受理为 SCHEDULED，到点由调度器投递
        mode = str(camp.publish_mode or "IMMEDIATE").upper()
        sched = camp.scheduled_at
        if mode == "SCHEDULED" and sched and sched > _utc_now():
            if not has_permission(user, "workbench.message.schedule"):
                # 有发布权时允许定时本班；无 schedule 权限则拒绝全校级定时
                if not has_permission(user, "workbench.message.class.publish") and not has_permission(user, "*"):
                    raise no_permission("无定时发布权限")
            camp.status = "SCHEDULED"
            camp.audience_fingerprint = audience_fingerprint
            camp.recipient_count = len(user_ids)
            camp.version = int(camp.version or 0) + 1
            db.commit()
            return {
                "campaignId": str(camp.id),
                "status": "SCHEDULED",
                "acceptedAt": _iso(_utc_now()),
                "scheduledAt": _iso(sched),
                "recipientCount": len(user_ids),
                "message": quiet.get("note") or "已预约定时发布",
                "quietNote": quiet.get("note"),
            }

        camp.status = "PUBLISHING"
        camp.audience_fingerprint = audience_fingerprint
        camp.recipient_count = len(user_ids)
        camp.published_at = _utc_now()
        camp.version = int(camp.version or 0) + 1
        school_scope = bool(
            {str(a.get("type") or "").upper() for a in rules}
            & {"ALL_STUDENT", "ALL_STAFF", "ALL_USERS"}
        )
        # 同事务：状态迁移 + 投递作业（同步/异步一律落作业，禁止 commit-then-deliver）
        _ = school_scope
        enq = delivery_svc.enqueue_campaign_delivery_in_db(db, camp, user_ids)
        db.commit()

    result = delivery_svc.accept_and_deliver(
        int(campaign_id), user_ids, force_async=True, already_enqueued=True)
    return {
        "campaignId": str(campaign_id),
        "status": result.get("status") or "PUBLISHING",
        "acceptedAt": _iso(_utc_now()),
        "recipientCount": len(user_ids),
        "deliveredCount": result.get("deliveredCount") or 0,
        "async": True,
        "jobCount": result.get("jobCount") if result.get("jobCount") is not None else enq.get("jobCount"),
    }


def approve_campaign_in_db(db, user: dict, campaign_id: str, *, version: int,
                           comment: str | None = None, from_workflow: bool = False,
                           skip_workflow_close: bool = False, commit: bool = False) -> dict:
    """审核通过：状态 + 投递作业同会话。commit=False 时由调用方统一提交。"""
    if not from_workflow and not has_permission(user, "workbench.message.emergency.approve"):
        raise no_permission("无紧急/全校消息审核权限")
    from app.models import MessageCampaign

    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        raise not_found("发布单不存在")
    camp = db.scalar(select(MessageCampaign).where(
        MessageCampaign.id == cid,
        MessageCampaign.tenant_id == _tid(),
        MessageCampaign.is_deleted.is_(False),
    ))
    if not camp:
        raise not_found("发布单不存在")
    if camp.status != "PENDING_REVIEW":
        raise AppException("DATA_CONFLICT", "当前状态不可审核通过",
                           details={"reason": "INVALID_STATUS"})
    if int(camp.version or 0) != int(version):
        raise AppException("DATA_CONFLICT", "版本冲突", details={"reason": "VERSION_CONFLICT"})
    if int(camp.sender_user_id or 0) == _uid(user):
        raise AppException("NO_PERMISSION", "发布人与审核人不得为同一人",
                           details={"reason": "REVIEWER_SAME_AS_SENDER"})

    rules = audience_svc.audiences_from_campaign_rules(db, camp.id)
    resolve_user = user
    if from_workflow:
        resolve_user = {
            **user,
            "currentRoleCode": "SCHOOL_ADMIN",
            "userType": "TEACHER",
        }
    resolved = audience_svc.resolve_audience(resolve_user, rules)
    if camp.audience_fingerprint and resolved["audienceFingerprint"] != camp.audience_fingerprint:
        raise AppException("DATA_CONFLICT", "受众已变化，请退回后由发布人重新预览提交",
                           details={"reason": "MESSAGE_AUDIENCE_CHANGED",
                                    "recipientCount": resolved["recipientCount"]})

    user_ids = resolved["userIds"]
    camp.status = "PUBLISHING"
    camp.recipient_count = len(user_ids)
    camp.published_at = _utc_now()
    camp.remark = ((camp.remark or "") + f"\n审核通过：{comment or ''}")[:500]
    camp.version = int(camp.version or 0) + 1
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    if not skip_workflow_close:
        if camp.workflow_instance_id:
            inst = db.get(WorkflowInstance, int(camp.workflow_instance_id))
            if inst:
                inst.status = "APPROVED"
            for t in db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.instance_id == camp.workflow_instance_id,
                WorkflowTask.status == "PENDING",
            )).all():
                t.status = "APPROVED"
                t.acted_at = _utc_now()
                t.action_reason = comment
        for todo in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "workbench-message",
            UnifiedTodo.source_biz_id == camp.id,
            UnifiedTodo.todo_type == "MESSAGE_CAMPAIGN_REVIEW",
            UnifiedTodo.is_deleted.is_(False),
        )).all():
            todo.status = "DONE"
            todo.version = int(todo.version or 0) + 1
    enq = delivery_svc.enqueue_campaign_delivery_in_db(db, camp, user_ids)
    if commit:
        db.commit()
    return {
        "campaignId": str(camp.id),
        "userIds": user_ids,
        "jobCount": enq.get("jobCount"),
        "recipientCount": len(user_ids),
        "alreadyEnqueued": True,
    }


def approve_campaign(user: dict, campaign_id: str, *, version: int,
                     comment: str | None = None, from_workflow: bool = False) -> dict:
    """紧急/全校审核通过后进入投递。审核人不得与发布人为同一人。"""
    with session() as db:
        hint = approve_campaign_in_db(
            db, user, campaign_id, version=version, comment=comment,
            from_workflow=from_workflow, skip_workflow_close=False, commit=True)
    result = delivery_svc.accept_and_deliver(
        int(campaign_id), hint["userIds"], force_async=True, already_enqueued=True)
    return {
        "campaignId": str(campaign_id),
        "status": result.get("status") or "PUBLISHED",
        "recipientCount": len(hint["userIds"]),
        "deliveredCount": result.get("deliveredCount") or 0,
        "async": True,
        "jobCount": result.get("jobCount") if result.get("jobCount") is not None else hint.get("jobCount"),
    }


def return_campaign_in_db(db, user: dict, campaign_id: str, *, version: int, reason: str,
                          from_workflow: bool = False, skip_workflow_close: bool = False,
                          commit: bool = False) -> dict:
    """审核退回：与调用方同会话。"""
    if not from_workflow and not has_permission(user, "workbench.message.emergency.approve"):
        raise no_permission("无审核权限")
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "退回原因必填", http_status=422)
    from app.models import MessageCampaign
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        raise not_found("发布单不存在")
    camp = db.scalar(select(MessageCampaign).where(
        MessageCampaign.id == cid,
        MessageCampaign.tenant_id == _tid(),
        MessageCampaign.is_deleted.is_(False),
    ))
    if not camp:
        raise not_found("发布单不存在")
    if camp.status != "PENDING_REVIEW":
        raise AppException("DATA_CONFLICT", "当前状态不可退回",
                           details={"reason": "INVALID_STATUS"})
    if int(camp.version or 0) != int(version):
        raise AppException("DATA_CONFLICT", "版本冲突", details={"reason": "VERSION_CONFLICT"})
    if int(camp.sender_user_id or 0) == _uid(user):
        raise AppException("NO_PERMISSION", "发布人与审核人不得为同一人",
                           details={"reason": "REVIEWER_SAME_AS_SENDER"})
    camp.status = "RETURNED"
    camp.remark = reason[:500]
    camp.version = int(camp.version or 0) + 1
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    if not skip_workflow_close:
        if camp.workflow_instance_id:
            inst = db.get(WorkflowInstance, int(camp.workflow_instance_id))
            if inst:
                inst.status = "RETURNED"
            for t in db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.instance_id == camp.workflow_instance_id,
                WorkflowTask.status == "PENDING",
            )).all():
                t.status = "REJECTED"
                t.acted_at = _utc_now()
                t.action_reason = reason[:500]
        for todo in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "workbench-message",
            UnifiedTodo.source_biz_id == camp.id,
            UnifiedTodo.todo_type == "MESSAGE_CAMPAIGN_REVIEW",
            UnifiedTodo.is_deleted.is_(False),
        )).all():
            todo.status = "DONE"
            todo.version = int(todo.version or 0) + 1
    if commit:
        db.commit()
    return _campaign_dict(camp)


def return_campaign(user: dict, campaign_id: str, *, version: int, reason: str,
                    from_workflow: bool = False) -> dict:
    with session() as db:
        return return_campaign_in_db(
            db, user, campaign_id, version=version, reason=reason,
            from_workflow=from_workflow, skip_workflow_close=False, commit=True)


def withdraw_campaign(user: dict, campaign_id: str, *, reason: str, version: int) -> dict:
    if not has_permission(user, "workbench.message.withdraw"):
        raise no_permission("无撤回权限")
    from app.models import MessageCampaign, UnifiedMessage
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "撤回原因必填", http_status=422)
    with session() as db:
        try:
            cid = int(campaign_id)
        except (TypeError, ValueError):
            raise not_found("发布单不存在")
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        if int(camp.version or 0) != int(version):
            raise AppException("DATA_CONFLICT", "版本冲突", details={"reason": "VERSION_CONFLICT"})
        if camp.status not in ("PUBLISHED", "PUBLISHING", "PARTIAL_FAILED", "SCHEDULED"):
            raise AppException("DATA_CONFLICT", "当前状态不可撤回",
                               details={"reason": "INVALID_STATUS"})
        now = _utc_now()
        camp.status = "WITHDRAWN"
        camp.withdrawn_at = now
        camp.withdrawn_by = _uid(user)
        camp.withdraw_reason = reason[:500]
        camp.version = int(camp.version or 0) + 1
        rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.campaign_id == camp.id,
            UnifiedMessage.is_deleted.is_(False),
        )).all()
        for r in rows:
            r.withdrawn_at = now
            r.withdraw_reason = reason[:500]
            r.version = int(r.version or 0) + 1
        db.commit()
        return _campaign_dict(camp)


def process_pending_deliveries(limit: int = 5) -> int:
    """兼容旧钩子：领取投递作业。"""
    return delivery_svc.claim_and_process_delivery_jobs(limit=limit, worker_id="compat-hook")


def process_scheduled_campaigns(limit: int = 20) -> int:
    """到点定时发布：重算受众指纹，一致则投递。"""
    from app.models import MessageCampaign

    now = _utc_now()
    done = 0
    with session() as db:
        rows = db.scalars(
            select(MessageCampaign).where(
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.is_deleted.is_(False),
                MessageCampaign.status == "SCHEDULED",
                MessageCampaign.scheduled_at.is_not(None),
                MessageCampaign.scheduled_at <= now,
            ).order_by(MessageCampaign.scheduled_at.asc(), MessageCampaign.id.asc()).limit(limit)
        ).all()
        ids = [int(r.id) for r in rows]

    for cid in ids:
        with session() as db:
            camp = db.scalar(select(MessageCampaign).where(
                MessageCampaign.id == cid,
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.is_deleted.is_(False),
                MessageCampaign.status == "SCHEDULED",
            ))
            if not camp:
                continue
            rules = audience_svc.audiences_from_campaign_rules(db, camp.id)
            system_user = {
                "userId": f"u_{camp.sender_user_id}",
                "currentRoleCode": camp.sender_role_snapshot or "SYSTEM",
                "userType": "TEACHER",
            }
            try:
                resolved = audience_svc.resolve_audience(system_user, rules)
            except Exception:  # noqa: BLE001
                system_user["currentRoleCode"] = "SCHOOL_ADMIN"
                resolved = audience_svc.resolve_audience(system_user, rules)

            if camp.audience_fingerprint and resolved.get("audienceFingerprint") != camp.audience_fingerprint:
                camp.status = "PARTIAL_FAILED"
                camp.remark = ((camp.remark or "") + "\n定时投递时受众已变化，已中止")[:500]
                camp.version = int(camp.version or 0) + 1
                db.commit()
                continue
            user_ids = resolved.get("userIds") or []
            camp.status = "PUBLISHING"
            camp.recipient_count = len(user_ids)
            camp.published_at = now
            camp.version = int(camp.version or 0) + 1
            # 同事务落作业；禁止 commit-then-deliver
            delivery_svc.enqueue_campaign_delivery_in_db(db, camp, user_ids)
            db.commit()
        delivery_svc.accept_and_deliver(cid, user_ids, force_async=True, already_enqueued=True)
        done += 1
    return done


def repair_publishing_without_jobs(limit: int = 20) -> int:
    """修复 PUBLISHING 但无投递作业的断点状态：回退为 DRAFT 或重建空作业标记。

    有 recipient_count>0 时尝试用受众规则重算并补建作业；否则标 PARTIAL_FAILED 允许运营介入。
    """
    from app.models import MessageCampaign, MessageDeliveryJob

    repaired = 0
    with session() as db:
        rows = db.scalars(
            select(MessageCampaign).where(
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.is_deleted.is_(False),
                MessageCampaign.status == "PUBLISHING",
            ).order_by(MessageCampaign.id.asc()).limit(limit)
        ).all()
        for camp in rows:
            job_n = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
                MessageDeliveryJob.tenant_id == _tid(),
                MessageDeliveryJob.campaign_id == camp.id,
                MessageDeliveryJob.is_deleted.is_(False),
            )) or 0
            if job_n > 0:
                continue
            # 同步投递可能已完成但状态未收口
            if int(camp.delivered_count or 0) >= int(camp.recipient_count or 0) > 0:
                camp.status = "PUBLISHED"
                camp.version = int(camp.version or 0) + 1
                repaired += 1
                continue
            rules = audience_svc.audiences_from_campaign_rules(db, camp.id)
            system_user = {
                "userId": f"u_{camp.sender_user_id}",
                "currentRoleCode": "SCHOOL_ADMIN",
                "userType": "TEACHER",
            }
            try:
                resolved = audience_svc.resolve_audience(system_user, rules)
                user_ids = resolved.get("userIds") or []
            except Exception:  # noqa: BLE001
                user_ids = []
            if user_ids:
                delivery_svc.enqueue_campaign_delivery_in_db(db, camp, user_ids)
                repaired += 1
            else:
                camp.status = "PARTIAL_FAILED"
                camp.remark = ((camp.remark or "") + "\n自动修复：PUBLISHING 无作业且受众为空")[:500]
                camp.version = int(camp.version or 0) + 1
                repaired += 1
        if repaired:
            db.commit()
    return repaired


def process_expired_campaigns(limit: int = 50) -> int:
    from app.models import MessageCampaign, UnifiedMessage
    now = _utc_now()
    done = 0
    with session() as db:
        rows = db.scalars(
            select(MessageCampaign).where(
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.is_deleted.is_(False),
                MessageCampaign.expire_at.is_not(None),
                MessageCampaign.expire_at <= now,
                MessageCampaign.status.in_(("PUBLISHED", "PUBLISHING", "PARTIAL_FAILED", "SCHEDULED")),
            ).limit(limit)
        ).all()
        for camp in rows:
            camp.status = "EXPIRED"
            camp.version = int(camp.version or 0) + 1
            for m in db.scalars(select(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(),
                UnifiedMessage.campaign_id == camp.id,
                UnifiedMessage.is_deleted.is_(False),
            )).all():
                if not m.expire_at:
                    m.expire_at = camp.expire_at
            done += 1
        if done:
            db.commit()
    return done


def nudge_unacked_emergency(limit: int = 50) -> int:
    from app.models import MessageCampaign, UnifiedMessage
    from app.services.message_event_outbox_service import emit_message_event

    now = _utc_now()
    day_key = now.strftime("%Y%m%d")
    nudged = 0
    with session() as db:
        camps = db.scalars(
            select(MessageCampaign).where(
                MessageCampaign.tenant_id == _tid(),
                MessageCampaign.is_deleted.is_(False),
                MessageCampaign.require_ack.is_(True),
                MessageCampaign.emergency.is_(True),
                MessageCampaign.status.in_(("PUBLISHED", "PARTIAL_FAILED")),
                MessageCampaign.ack_deadline_at.is_not(None),
                MessageCampaign.ack_deadline_at <= now,
            ).limit(limit)
        ).all()
        for camp in camps:
            msgs = db.scalars(
                select(UnifiedMessage).where(
                    UnifiedMessage.tenant_id == _tid(),
                    UnifiedMessage.campaign_id == camp.id,
                    UnifiedMessage.require_ack.is_(True),
                    UnifiedMessage.ack_at.is_(None),
                    UnifiedMessage.withdrawn_at.is_(None),
                    UnifiedMessage.is_deleted.is_(False),
                ).limit(200)
            ).all()
            for m in msgs:
                uid = m.receiver_user_id or m.receiver_id
                if not uid:
                    continue
                try:
                    emit_message_event(
                        db,
                        event_code="MESSAGE.ACK_NUDGE",
                        source_module="workbench-message",
                        source_biz_type="MESSAGE_CAMPAIGN",
                        source_biz_id=int(camp.id),
                        recipient_refs=[{"userId": int(uid)}],
                        title=f"请确认：{camp.title}"[:200],
                        content=f"紧急消息确认截止已过，请尽快确认回执。原文：{(camp.summary or '')[:200]}",
                        dedup_key=f"ACK_NUDGE:{camp.id}:{uid}:{day_key}",
                        action_key="message.detail",
                        action_params={"messageId": int(m.id), "campaignId": int(camp.id)},
                    )
                    nudged += 1
                except Exception:  # noqa: BLE001
                    continue
        if nudged:
            db.commit()
    return nudged


def list_campaign_recipients(user: dict, campaign_id: str, *,
                             filter_mode: str | None = None,
                             page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    if not (_can_publish(user) or has_permission(user, "workbench.message.statistics.view")):
        raise no_permission("无查看收件名单权限")
    from app.models import MessageCampaign, UnifiedMessage, User
    with session() as db:
        try:
            cid = int(campaign_id)
        except (TypeError, ValueError):
            raise not_found("发布单不存在")
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == cid,
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        conds = [
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.campaign_id == cid,
            UnifiedMessage.is_deleted.is_(False),
        ]
        mode = (filter_mode or "").upper()
        if mode == "UNREAD":
            conds.append(UnifiedMessage.status == "UNREAD")
        elif mode == "UNACKED":
            conds.append(UnifiedMessage.require_ack.is_(True))
            conds.append(UnifiedMessage.ack_at.is_(None))
        total = db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conds)) or 0
        rows = db.scalars(
            select(UnifiedMessage).where(*conds)
            .order_by(UnifiedMessage.id.asc())
            .offset(max(0, (page - 1) * page_size)).limit(page_size)
        ).all()
        uids = [r.receiver_user_id or r.receiver_id for r in rows if (r.receiver_user_id or r.receiver_id)]
        users = {}
        if uids:
            for u in db.scalars(select(User).where(User.id.in_(uids))).all():
                users[u.id] = u
        items = []
        for r in rows:
            uid = r.receiver_user_id or r.receiver_id
            u = users.get(uid)
            items.append({
                "messageId": str(r.id),
                "userId": str(uid) if uid else None,
                "realName": getattr(u, "real_name", None) if u else None,
                "loginName": getattr(u, "login_name", None) if u else None,
                "status": r.status,
                "readAt": _iso(r.read_at) if r.read_at else None,
                "ackAt": _iso(r.ack_at) if r.ack_at else None,
                "requireAck": bool(r.require_ack),
            })
        return items, int(total)


def export_campaign_recipients(user: dict, campaign_id: str, *,
                               filter_mode: str | None = None,
                               purpose: str = "消息收件名单导出") -> dict:
    items, _ = list_campaign_recipients(
        user, campaign_id, filter_mode=filter_mode, page=1, page_size=5000)
    from app.services.excel.pipeline import build_export
    from app.services.excel.spec import ColumnSpec, ExportSpec

    spec = ExportSpec(
        module_key="workbench-message",
        biz_type="message_recipients",
        sheet_title="收件名单",
        columns=[
            ColumnSpec(key="messageId", title="消息ID"),
            ColumnSpec(key="userId", title="用户ID"),
            ColumnSpec(key="realName", title="姓名"),
            ColumnSpec(key="loginName", title="账号"),
            ColumnSpec(key="status", title="已读状态"),
            ColumnSpec(key="readAt", title="已读时间"),
            ColumnSpec(key="ackAt", title="确认时间"),
            ColumnSpec(key="requireAck", title="需确认"),
        ],
    )
    try:
        from app.models import AffairsAuditTrail
        with session() as db:
            db.add(AffairsAuditTrail(
                tenant_id=_tid(),
                biz_type="MESSAGE_EXPORT",
                biz_id=int(campaign_id),
                action="EXPORT_RECIPIENTS",
                operator=str(user.get("realName") or user.get("userId") or ""),
                detail=f"purpose={purpose};filter={filter_mode};count={len(items)}",
            ))
            db.commit()
    except Exception:  # noqa: BLE001
        pass
    return build_export(spec, items, operator_name=str(user.get("realName") or ""))


def apply_workflow_decision_in_db(db, user: dict, *, campaign_id: int, approved: bool,
                                  comment: str | None = None,
                                  skip_workflow_close: bool = True) -> dict:
    """审批副作用：与调用方同会话；失败由调用方 rollback，禁止假成功。"""
    from app.models import MessageCampaign
    camp = db.scalar(select(MessageCampaign).where(
        MessageCampaign.id == int(campaign_id),
        MessageCampaign.tenant_id == _tid(),
        MessageCampaign.is_deleted.is_(False),
    ))
    if not camp:
        raise not_found("发布单不存在")
    version = int(camp.version or 0)
    if approved:
        return approve_campaign_in_db(
            db, user, str(campaign_id), version=version, comment=comment,
            from_workflow=True, skip_workflow_close=skip_workflow_close, commit=False)
    return return_campaign_in_db(
        db, user, str(campaign_id), version=version,
        reason=comment or "审批中心退回", from_workflow=True,
        skip_workflow_close=skip_workflow_close, commit=False)


def apply_workflow_decision(user: dict, *, campaign_id: int, approved: bool,
                            comment: str | None = None) -> dict:
    """独立入口（非审批同事务场景）；通过后尽力内联消费作业。"""
    with session() as db:
        hint = apply_workflow_decision_in_db(
            db, user, campaign_id=campaign_id, approved=approved,
            comment=comment, skip_workflow_close=False)
        db.commit()
    if approved and isinstance(hint, dict) and hint.get("alreadyEnqueued"):
        delivery_svc.accept_and_deliver(
            int(campaign_id), hint.get("userIds") or [],
            force_async=True, already_enqueued=True)
    return hint if isinstance(hint, dict) else {"campaignId": str(campaign_id)}


def list_dead_letters(user: dict, *, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    if not (
        has_permission(user, "workbench.message.schoolAll.publish")
        or has_permission(user, "workbench.message.statistics.view")
        or has_permission(user, "*")
    ):
        raise no_permission("无运维死信查看权限")
    from app.services import message_event_outbox_service as outbox_svc

    d_items, d_total = delivery_svc.list_dead_delivery_jobs(page=1, page_size=500)
    o_raw, o_total = outbox_svc.list_dead_outbox(page=1, page_size=500)
    o_items = []
    for r in o_raw:
        o_items.append({
            "jobId": r.get("outboxId") or r.get("jobId"),
            "kind": "OUTBOX",
            "campaignId": None,
            "eventCode": r.get("eventCode"),
            "status": r.get("status"),
            "attemptCount": r.get("attemptCount"),
            "lastError": r.get("lastError"),
            "updatedAt": r.get("updatedAt"),
        })
    merged = list(d_items) + o_items
    merged.sort(key=lambda x: int(x.get("jobId") or 0), reverse=True)
    total = int(d_total) + int(o_total)
    start = max(0, (page - 1) * page_size)
    return merged[start:start + page_size], total


def retry_dead_letter(user: dict, letter_id: str, kind: str | None = None) -> dict:
    if not (
        has_permission(user, "workbench.message.schoolAll.publish")
        or has_permission(user, "workbench.message.statistics.view")
        or has_permission(user, "*")
    ):
        raise no_permission("无死信重试权限")
    from app.services import message_event_outbox_service as outbox_svc

    try:
        lid = int(letter_id)
    except (TypeError, ValueError):
        raise not_found("死信不存在")
    k = (kind or "").upper()
    if k in ("EVENT_OUTBOX", "OUTBOX"):
        return {**outbox_svc.retry_dead_outbox(lid), "kind": "OUTBOX"}
    if k in ("DELIVERY_JOB", "DELIVERY"):
        return {**delivery_svc.retry_dead_delivery_job(lid), "kind": "DELIVERY_JOB"}
    try:
        return {**delivery_svc.retry_dead_delivery_job(lid), "kind": "DELIVERY_JOB"}
    except Exception:  # noqa: BLE001
        return {**outbox_svc.retry_dead_outbox(lid), "kind": "OUTBOX"}


process_delivery_jobs = process_pending_deliveries

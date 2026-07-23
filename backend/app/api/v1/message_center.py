"""消息中心发布端 API：/api/v1/admin/message-campaigns*"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import require_staff
from app.schemas.message_center import (
    AudiencePreviewBody,
    CampaignAttachmentBody,
    CampaignDraftBody,
    CampaignPublishBody,
    CampaignReviewBody,
    CampaignWithdrawBody,
)
from app.services import message_audience_service as audience_svc
from app.services import message_campaign_service as campaign_svc
from app.services import message_meta_service as meta_svc

router = APIRouter(prefix="/admin/message-campaigns", tags=["工作台·消息中心·发布"])


@router.get("/statistics", summary="发送统计汇总")
def campaign_statistics(
    days: int = Query(default=30, ge=1, le=365),
    user=Depends(require_staff),
):
    return success(meta_svc.statistics_summary(user, days=days))


@router.get("/templates", summary="消息模板列表（复用通知模板表）")
def campaign_templates(
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    user=Depends(require_staff),
):
    items, total = meta_svc.list_message_templates(user, keyword=keyword, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/templates", summary="新建消息模板")
def create_template(body: dict = Body(...), user=Depends(require_staff)):
    from app.services import message_ops_service as ops_svc
    return success(ops_svc.create_message_template(user, body))


@router.patch("/templates/{template_id}", summary="更新/启停消息模板")
def patch_template(template_id: str, body: dict = Body(...), user=Depends(require_staff)):
    from app.services import message_ops_service as ops_svc
    return success(ops_svc.update_message_template(user, template_id, body))


@router.get("/settings", summary="消息渠道与偏好设置")
def campaign_settings(user=Depends(require_staff)):
    return success(meta_svc.channel_settings(user))


@router.post("/settings/preference", summary="更新分类偏好")
def campaign_settings_pref(body: dict = Body(...), user=Depends(require_staff)):
    return success(meta_svc.set_channel_preference(
        user, str(body.get("key") or ""), bool(body.get("enabled"))))


@router.get("/audience-options", summary="受众选项（按权限与数据范围）")
def audience_options(
    type: str = Query(..., description="CLASS / COLLEGE"),
    keyword: Optional[str] = Query(default=None),
    pageSize: int = Query(default=100, ge=1, le=500),
    user=Depends(require_staff),
):
    return success(audience_svc.list_audience_options(user, type, keyword, pageSize))


@router.get("/action-keys", summary="深链 actionKey 注册表")
def action_keys(user=Depends(require_staff)):
    from app.services.message_action_registry import list_action_keys
    return success({"items": list_action_keys()})


@router.get("/ops/dead-letters", summary="投递/Outbox 死信台账")
def dead_letters(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    user=Depends(require_staff),
):
    items, total = campaign_svc.list_dead_letters(user, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/ops/dead-letters/{letter_id}/retry", summary="死信重试")
def retry_dead_letter(
    letter_id: str,
    body: dict = Body(default=None),
    user=Depends(require_staff),
):
    body = body or {}
    # 兼容前端传 kind；服务层按 id 前缀/查询分辨
    return success(campaign_svc.retry_dead_letter(user, letter_id, kind=body.get("kind")))


@router.get("/ops/reconcile", summary="统计对账与积压告警")
def ops_reconcile(user=Depends(require_staff)):
    from app.services import message_ops_service as ops_svc
    return success(ops_svc.reconcile_message_stats(user))


@router.post("", summary="新建发布草稿")
def create_campaign(body: CampaignDraftBody, user=Depends(require_staff)):
    return success(campaign_svc.create_draft(user, body.model_dump()))


@router.get("", summary="发布记录列表")
def list_campaigns(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(require_staff),
):
    items, total = campaign_svc.list_campaigns(user, status=status, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/audience-preview", summary="受众预览")
def audience_preview(body: AudiencePreviewBody, user=Depends(require_staff)):
    data = audience_svc.preview_audience(
        user,
        [a.model_dump() for a in body.audiences],
        body.recipientTypes,
    )
    return success(data)


@router.get("/{campaign_id}", summary="发布详情")
def campaign_detail(campaign_id: str, user=Depends(require_staff)):
    return success(campaign_svc.get_campaign(user, campaign_id))


@router.post("/{campaign_id}/attachments", summary="关联附件")
def add_attachment(campaign_id: str, body: CampaignAttachmentBody, user=Depends(require_staff)):
    return success(campaign_svc.add_campaign_attachment(
        user, campaign_id, file_id=body.fileId, file_name=body.fileName))


@router.get("/{campaign_id}/recipients", summary="收件名单（可筛未读/未确认）")
def campaign_recipients(
    campaign_id: str,
    filter: Optional[str] = Query(default=None, description="UNREAD / UNACKED"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    user=Depends(require_staff),
):
    items, total = campaign_svc.list_campaign_recipients(
        user, campaign_id, filter_mode=filter, page=page, page_size=pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/{campaign_id}/export-recipients", summary="导出收件名单 Excel")
def export_recipients(
    campaign_id: str,
    body: dict = Body(default=None),
    user=Depends(require_staff),
):
    body = body or {}
    return success(campaign_svc.export_campaign_recipients(
        user, campaign_id,
        filter_mode=body.get("filter") or body.get("filterMode"),
        purpose=str(body.get("purpose") or "消息收件名单导出"),
    ))


@router.post("/{campaign_id}/channels/{channel}/send", summary="外部渠道发送")
def send_channel(campaign_id: str, channel: str, user=Depends(require_staff)):
    from app.services import message_ops_service as ops_svc
    return success(ops_svc.enqueue_channel_delivery(user, campaign_id, channel=channel))


@router.post("/{campaign_id}/publish", summary="受理发布（异步投递）")
def publish_campaign(campaign_id: str, body: CampaignPublishBody, user=Depends(require_staff)):
    return success(campaign_svc.publish_campaign(
        user, campaign_id,
        preview_token=body.previewToken,
        audience_fingerprint=body.audienceFingerprint,
        version=body.version,
    ))


@router.post("/{campaign_id}/approve", summary="审核通过并投递")
def approve_campaign(campaign_id: str, body: CampaignReviewBody, user=Depends(require_staff)):
    return success(campaign_svc.approve_campaign(
        user, campaign_id, version=body.version, comment=body.comment))


@router.post("/{campaign_id}/return", summary="审核退回")
def return_campaign(campaign_id: str, body: CampaignReviewBody, user=Depends(require_staff)):
    return success(campaign_svc.return_campaign(
        user, campaign_id, version=body.version, reason=body.reason or body.comment or ""))


@router.post("/{campaign_id}/withdraw", summary="撤回发布")
def withdraw_campaign(campaign_id: str, body: CampaignWithdrawBody, user=Depends(require_staff)):
    return success(campaign_svc.withdraw_campaign(
        user, campaign_id, reason=body.reason, version=body.version))

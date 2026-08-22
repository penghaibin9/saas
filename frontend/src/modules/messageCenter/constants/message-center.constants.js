import { safeEnumLabel } from '../../../utils/presentationSafety.js'

export const MESSAGE_CAMPAIGN_STATUS_LABELS = Object.freeze({
  DRAFT: '草稿',
  PENDING_REVIEW: '待审核',
  APPROVED: '审核通过',
  RETURNED: '已退回',
  SCHEDULED: '定时发布',
  PUBLISHING: '投递中',
  PUBLISHED: '已发布',
  PARTIAL_FAILED: '部分失败',
  WITHDRAWN: '已撤回',
  EXPIRED: '已过期'
})

export const MESSAGE_CATEGORY_LABELS = Object.freeze({
  ANNOUNCEMENT: '公告',
  BUSINESS: '业务通知',
  REMINDER: '提醒',
  EMERGENCY: '紧急消息',
  SYSTEM: '系统消息'
})

export const MESSAGE_DELIVERY_STATUS_LABELS = Object.freeze({
  CREATED: '待投递',
  PENDING: '待投递',
  SENDING: '投递中',
  SENT: '已发送',
  DELIVERED: '已送达',
  UNREAD: '未读',
  READ: '已读',
  ACKED: '已确认',
  FAILED: '投递失败',
  WITHDRAWN: '已撤回',
  EXPIRED: '已过期'
})

export const MESSAGE_CHANNEL_STATUS_LABELS = Object.freeze({
  READY: '已就绪',
  NOT_CONFIGURED: '未配置',
  DEGRADED: '服务降级',
  UNAVAILABLE: '暂不可用',
  DISABLED: '已停用'
})

function label(value, dictionary, unknownLabel) {
  const raw = String(value ?? '').trim()
  if (/[一-鿿]/.test(raw)) return raw
  return safeEnumLabel({ value, dictionary, unknownLabel })
}

export const messageCampaignStatusLabel = (value) => label(value, MESSAGE_CAMPAIGN_STATUS_LABELS, '发布状态待确认')
export const messageCategoryLabel = (value) => label(value, MESSAGE_CATEGORY_LABELS, '消息类型待确认')
export const messageDeliveryStatusLabel = (value) => label(value, MESSAGE_DELIVERY_STATUS_LABELS, '投递状态待确认')
export const messageChannelStatusLabel = (value) => label(value, MESSAGE_CHANNEL_STATUS_LABELS, '渠道状态待确认')

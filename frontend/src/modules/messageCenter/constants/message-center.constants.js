import { safeEnumLabel, isTechnicalUiMessage } from '../../../utils/presentationSafety.js'

export const MESSAGE_CAMPAIGN_STATUS_LABELS = Object.freeze({
  DRAFT: '草稿',
  PENDING_REVIEW: '待审核',
  APPROVED: '审核通过',
  RETURNED: '已退回',
  SCHEDULED: '定时发布',
  PUBLISHING: '投递中',
  PUBLISHED: '已发布',
  PARTIAL_FAILED: '部分失败',
  FAILED: '发布失败',
  WITHDRAWN: '已撤回',
  EXPIRED: '已过期'
})

export const MESSAGE_CATEGORY_LABELS = Object.freeze({
  ANNOUNCEMENT: '公告',
  BUSINESS: '业务通知',
  REMINDER: '提醒',
  TODO: '待办提醒',
  WARNING: '风险预警',
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
  DEGRADED: '部分功能暂不可用',
  UNAVAILABLE: '暂不可用',
  DISABLED: '已停用'
})

function label(value, dictionary, unknownLabel) {
  const raw = String(value ?? '').trim()
  if (/[一-鿿]/.test(raw) && !isTechnicalUiMessage(raw)) return raw
  const result = safeEnumLabel({ value, dictionary, unknownLabel })
  return typeof result === 'string' ? result : unknownLabel
}

const CHANNEL_LABELS = { IN_APP: '站内消息', SMS: '短信', WECHAT: '微信' }
const JOB_KIND_LABELS = { DELIVERY_JOB: '消息投递', DELIVERY: '消息投递', OUTBOX: '业务通知', EVENT_OUTBOX: '业务通知' }
const ALERT_LABELS = { OUTBOX_BACKLOG: '业务通知积压', OUTBOX_DEAD: '业务通知处理失败', DELIVERY_JOB_BACKLOG: '消息投递积压', DELIVERY_JOB_DEAD: '消息投递失败' }

export const messageChannelLabel = value => label(value, CHANNEL_LABELS, '其他渠道')
export const messageJobKindLabel = value => label(value, JOB_KIND_LABELS, '其他任务')
export const messageAlertLabel = value => label(value, ALERT_LABELS, '其他提醒')

export const messageCampaignStatusLabel = (value) => label(value, MESSAGE_CAMPAIGN_STATUS_LABELS, '发布状态待确认')
export const messageCategoryLabel = (value) => label(value, MESSAGE_CATEGORY_LABELS, '消息类型待确认')
export const messageDeliveryStatusLabel = (value) => label(value, MESSAGE_DELIVERY_STATUS_LABELS, '投递状态待确认')
export const messageChannelStatusLabel = (value) => label(value, MESSAGE_CHANNEL_STATUS_LABELS, '渠道状态待确认')

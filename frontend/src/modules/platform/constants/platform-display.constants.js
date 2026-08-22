import { safeEnumLabel } from '../../../utils/presentationSafety.js'

const PLATFORM_STATUS_LABELS = Object.freeze({
  DRAFT: '草稿', PUBLISHED: '已发布', ACTIVE: '正常', EXPIRED: '已过期', REVOKED: '已撤销',
  OPEN: '待处理', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭',
  PENDING: '待处理', RUNNING: '执行中', SUCCEEDED: '已成功', FAILED: '失败',
  APPROVED: '已批准', ASSESSED: '已评估', IMPLEMENTING: '实施中', SCHEDULED: '已排期',
  VERIFIED: '已验证', ROLLED_BACK: '已回滚', COMPLETED: '已完成', CANCELLED: '已取消',
  CONTACTED: '已联系', COMMITTED: '已承诺', RENEWED: '已续约', AT_RISK: '存在风险', CHURNED: '已流失',
  PASSED: '已通过', DEGRADED: '服务降级', DEPRECATED: '已停用',
  WAITING_INPUT: '等待补充信息', COMPENSATING: '回滚处理中', COMPENSATED: '已回滚',
  NEEDS_MANUAL_REVIEW: '需人工复核'
})

export function platformStatusLabel(value) {
  const raw = String(value ?? '').trim()
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return safeEnumLabel({ value, dictionary: PLATFORM_STATUS_LABELS, unknownLabel: '状态待确认' })
}

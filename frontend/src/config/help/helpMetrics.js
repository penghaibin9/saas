import { request } from '@/services/http/client'

/**
 * V3-08 质量指标客户端。
 * 指标失败绝不阻塞用户看帮助；写失败也绝不回退 mock 或伪造“已记录”。
 */
export async function recordHelpMetric(payload) {
  try {
    return await request('/help/metrics/events', { method: 'POST', body: payload })
  } catch {
    return null
  }
}

export async function loadHelpMetricsSummary(days = 30) {
  try {
    return await request('/help/metrics/summary', { params: { days } })
  } catch {
    // 普通老师没有学校级审计权限时正常隐藏质量面板。
    return null
  }
}

export function formatHelpRate(value) {
  return typeof value === 'number' ? `${Math.round(value * 1000) / 10}%` : '—'
}

export function helpMetricStatusLabel(value) {
  return {
    HEALTHY: '达到当前目标',
    NEEDS_ATTENTION: '需要继续优化',
    INSUFFICIENT_DATA: '样本不足'
  }[value] || '尚无数据'
}

import { getToken, request } from '@/services/http/client'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

async function postMetric(path, payload, token) {
  const bearer = String(token || '').trim()
  if (!bearer) return null
  try {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bearer}`
      },
      body: JSON.stringify(payload)
    })
    const body = await response.json().catch(() => null)
    if (!response.ok || !body || body.code !== 0) return null
    return body.data
  } catch {
    return null
  }
}

/**
 * V3-08 质量指标客户端。
 * 指标失败绝不阻塞用户看帮助；写失败也绝不回退 mock、刷新主会话、跳登录页或伪造“已记录”。
 */
export async function recordHelpMetric(payload) {
  return postMetric('/help/metrics/events', payload, getToken())
}

/**
 * 公开 /help 页面没有管理端登录要求。
 * 小程序 WebView 只携带后端签发的 10 分钟 Help-Metrics capability；它不是主 JWT，
 * 只能写低敏帮助指标，不能访问任何普通 authenticated API。
 */
export async function recordPublicHelpMetric(payload, metricToken) {
  return postMetric('/help/metrics/public/events', payload, metricToken)
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

import { isTechnicalUiMessage, normalizeUiError } from '@/utils/presentationSafety'

const CONFLICT_MESSAGE_PATTERN = /(?:记录|版本|数据).*(?:变化|变更|更新)|已被处理|已批阅|并发|stale|conflict/i

function numericStatus(response = {}) {
  const raw = response.status ?? response.code ?? 0
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  return value >= 100000 ? Math.trunc(value / 1000) : Math.trunc(value)
}

function rawBackendMessage(response = {}) {
  const value = response && typeof response === 'object' ? response.message : response
  return String(value || '').trim()
}

function appendBackendMessage(base, response) {
  const raw = rawBackendMessage(response)
  if (!raw || raw.length > 160 || isTechnicalUiMessage(raw) || base.includes(raw)) return base
  return `${base}（服务端：${raw}）`
}

export function isGraduationConflictResponse(response = {}) {
  const status = numericStatus(response)
  const bizCode = String(response.bizCode || response.code || '').trim().toUpperCase()
  return status === 409 || bizCode === 'VERSION_CONFLICT' || CONFLICT_MESSAGE_PATTERN.test(rawBackendMessage(response))
}

export function graduationConflictMessage(response = {}) {
  // 业务规则冲突（如「答辩阶段未开放」「评委尚未全部评分」）不是别人改了记录：
  // 直接把服务端原因告诉老师，不要说「记录已变化、请重新提交」，否则重试永远失败。
  const raw = rawBackendMessage(response)
  const bizCode = String(response.bizCode || '').trim().toUpperCase()
  if (bizCode !== 'VERSION_CONFLICT' && raw && raw.length <= 160 && !isTechnicalUiMessage(raw)
    && !CONFLICT_MESSAGE_PATTERN.test(raw)) {
    return `${raw}。你填写的内容已保留。`
  }
  return appendBackendMessage(
    '记录已发生变化，已刷新最新数据；你刚才填写的内容已保留，请核对后重新确认提交。',
    response
  )
}

export function graduationActionErrorMessage(response = {}, fallback = '操作未完成，请稍后重试') {
  const safe = normalizeUiError(response, { fallback })
  return appendBackendMessage(safe.userMessage, response)
}

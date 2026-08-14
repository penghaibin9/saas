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
  return appendBackendMessage(
    '记录已发生变化，已刷新最新数据；你刚才填写的内容已保留，请核对后重新确认提交。',
    response
  )
}

export function graduationActionErrorMessage(response = {}, fallback = '操作未完成，请稍后重试') {
  const safe = normalizeUiError(response, { fallback })
  return appendBackendMessage(safe.userMessage, response)
}

/**
 * audit event helper — 前端安全审计事件（总册 §8）。
 * 当前仅生成前端事件对象并入内存队列，不落库、不接真实 API（sendAuditEventToBackend 为预留）。
 * detail 一律经 sanitizeAuditDetail 脱敏：password/token/idCard/phone 等禁止明文进入。
 */
import { AUDIT_EVENT_TYPE, AUDIT_FORBIDDEN_KEYS } from '../constants/security.constants'
import { getAuthContext } from '../auth/auth.context'
import { maskIdCard, maskPhone } from './sensitive-mask.helper'
import { createRequestId } from '../request/secure-request.client'

/** 内存事件队列（仅演示可观测用；真实阶段替换为上报通道） */
const pendingEvents = []

export function getPendingAuditEvents() {
  return [...pendingEvents]
}

/** detail 脱敏：禁词字段替换/脱敏，嵌套对象递归 */
export function sanitizeAuditDetail(detail) {
  if (detail == null) return {}
  if (typeof detail !== 'object') return { value: String(detail) }
  const out = Array.isArray(detail) ? [] : {}
  for (const [key, val] of Object.entries(detail)) {
    const lower = key.toLowerCase()
    if (AUDIT_FORBIDDEN_KEYS.some((k) => lower.includes(k.toLowerCase()))) {
      if (lower.includes('phone') || lower.includes('mobile')) out[key] = maskPhone(val)
      else if (lower.includes('idcard')) out[key] = maskIdCard(val)
      else out[key] = '******'
    } else if (val && typeof val === 'object') {
      out[key] = sanitizeAuditDetail(val)
    } else {
      out[key] = val
    }
  }
  return out
}

/** 通用事件工厂 */
export function createAuditEvent(eventType, action, detail = {}, target = {}) {
  const auth = getAuthContext()
  return {
    eventId: createRequestId(),
    eventType,
    action,
    operatorId: auth.userId || 'anonymous',
    operatorName: auth.displayName || '未登录用户',
    tenantId: auth.tenantId || '',
    targetType: target.targetType || '',
    targetId: target.targetId || '',
    detail: sanitizeAuditDetail(detail),
    occurredAt: new Date().toISOString(),
    source: 'frontend'
  }
}

export function createLoginAuditEvent(success, detail = {}) {
  return createAuditEvent(AUDIT_EVENT_TYPE.LOGIN, success ? '登录成功' : '登录失败', detail)
}

export function createPermissionAuditEvent(permissionKey, allowed, detail = {}) {
  return createAuditEvent(
    AUDIT_EVENT_TYPE.PERMISSION_DENIED,
    allowed ? '权限校验通过' : '权限校验拒绝',
    { permissionKey, ...detail }
  )
}

export function createExportAuditEvent(exportType, scopeDesc, rowCount, detail = {}) {
  return createAuditEvent(AUDIT_EVENT_TYPE.EXPORT, '数据导出', {
    exportType,
    scope: scopeDesc,
    rowCount,
    ...detail
  })
}

export function createDownloadAuditEvent(fileId, fileName, detail = {}) {
  return createAuditEvent(
    AUDIT_EVENT_TYPE.DOWNLOAD,
    '文件下载',
    { fileId, fileName, ...detail },
    { targetType: 'FILE', targetId: fileId }
  )
}

export function createApprovalAuditEvent(taskId, action, detail = {}) {
  return createAuditEvent(
    AUDIT_EVENT_TYPE.APPROVAL,
    `审批操作：${action}`,
    detail,
    { targetType: 'APPROVAL_TASK', targetId: taskId }
  )
}

/**
 * 上报（预留）。当前：入内存队列并返回 mock 成功，不发任何网络请求。
 * 真实阶段：POST /api/v1/security/audit-events（走 secureRequest），失败本地重试。
 */
export async function sendAuditEventToBackend(event) {
  pendingEvents.push(event)
  if (pendingEvents.length > 200) pendingEvents.shift()
  return { code: 0, message: 'audit event queued (mock)', data: { eventId: event.eventId } }
}

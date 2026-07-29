/**
 * 教师/管理 PC 工作台真实数据入口。
 * 默认工作台摘要、分类、最近待办和消息角标共用一个后端快照；
 * 权限与数据范围仍由后端统一裁定。
 */
import { request } from '@/services/http'
import { getToken } from '@/services/http/client'
import { invalidateAdminQueries, runAdminQuery } from '@/services/performance/queryCoordinator'

function identityKey() {
  const token = String(getToken() || '')
  return token ? token.slice(-32) : 'anonymous'
}

function stable(value) {
  try { return JSON.stringify(value || {}) } catch { return String(value || '') }
}

function workbenchRead(name, path, options = {}, ttl = 5_000) {
  return runAdminQuery(
    `workbench|${identityKey()}|${name}|${stable(options.params)}`,
    () => request(path, options),
    { ttl }
  )
}

export function fetchWorkbenchSnapshot() {
  return workbenchRead(
    'snapshot',
    '/admin/workbench-snapshot',
    { params: { pageSize: 8 } },
    5_000
  )
}

export async function fetchTodoSummary() {
  const snapshot = await fetchWorkbenchSnapshot()
  return snapshot?.summary || { role: '', pending: 0, overdue: 0, nearDeadline: 0, doneToday: 0 }
}

export async function fetchTodoCount() {
  const snapshot = await fetchWorkbenchSnapshot()
  return snapshot?.count || { total: 0, byType: {} }
}

export function fetchTodoList(params = {}) {
  const requested = { status: 'PENDING', page: 1, pageSize: 8, ...params }
  requested.pageSize = Math.min(50, Math.max(1, Number(requested.pageSize) || 8))
  const isWorkbenchDefault = requested.status === 'PENDING'
    && Number(requested.page || 1) === 1
    && !requested.todoType
    && requested.pageSize <= 8
  if (isWorkbenchDefault) {
    return fetchWorkbenchSnapshot().then((snapshot) => snapshot?.todos || {
      items: [], total: 0, page: 1, pageSize: requested.pageSize, hasMore: false
    })
  }
  return workbenchRead('todo-list', '/admin/todos', { params: requested }, 5_000)
}

export async function fetchMessageCount() {
  const snapshot = await fetchWorkbenchSnapshot()
  return snapshot?.messages || { unread: 0, pendingAck: 0 }
}

export async function completeTodo(todoId, comment) {
  const result = await request(`/admin/todos/${todoId}/complete`, {
    method: 'POST', body: { comment }
  })
  invalidateAdminQueries(`workbench|${identityKey()}|`)
  return result
}

/** 品牌、当前身份、权限、范围和消息角标并行读取。 */
export async function fetchLayoutContext() {
  let brand = { schoolName: '管理端' }
  let currentRole = { roleCode: '', roleName: '', userName: '', roleType: '' }
  let dataScope = { scopeName: '' }
  let permissionPatterns = null
  let messageUnreadCount = 0
  let readonlyTenant = false
  let readonlyReason = ''

  const [brandResult, contextResult, messageResult] = await Promise.allSettled([
    workbenchRead('tenant-brand', '/tenant/brand', {}, 60_000),
    workbenchRead('rbac-context', '/rbac/current-context', {}, 15_000),
    fetchMessageCount()
  ])

  if (brandResult.status === 'fulfilled' && brandResult.value) {
    const b = brandResult.value
    brand = { ...brand, ...b, schoolName: b.schoolName || brand.schoolName }
  }

  let contextPayload = {}
  if (contextResult.status === 'fulfilled' && contextResult.value) {
    contextPayload = contextResult.value
    if (contextPayload.currentRole) {
      currentRole = { ...currentRole, ...contextPayload.currentRole }
      if (!currentRole.roleType && currentRole.roleCode) currentRole.roleType = currentRole.roleCode
    }
    if (contextPayload.dataScope) {
      dataScope = {
        ...dataScope,
        ...contextPayload.dataScope,
        scopeName: contextPayload.dataScope.scopeName || contextPayload.dataScope.scopeLabel || ''
      }
    }
    if (Array.isArray(contextPayload.permissionPatterns)) {
      permissionPatterns = contextPayload.permissionPatterns
    }
    readonlyTenant = !!contextPayload.readonlyTenant
    readonlyReason = contextPayload.readonlyReason || (
      readonlyTenant ? '当前学校环境为只读，数据不可修改。' : ''
    )
  }

  if (messageResult.status === 'fulfilled') {
    messageUnreadCount = Number(messageResult.value?.unread) || 0
  }

  const ctxKey = [
    String(contextPayload.tenantId || currentRole.tenantId || ''),
    String(contextPayload.userId || currentRole.userId || ''),
    currentRole.contextId || '',
    currentRole.permissionVersion || '',
    currentRole.roleCode || '',
    Array.isArray(permissionPatterns) ? [...permissionPatterns].sort().join(',') : '',
    Array.isArray(contextPayload.moduleEntitlements)
      ? [...contextPayload.moduleEntitlements].sort().join(',') : ''
  ].join('|')

  return {
    tenantBrandConfig: brand,
    currentRole,
    dataScope,
    permissionPatterns,
    messageUnreadCount,
    ctxKey,
    readonlyTenant,
    readonlyReason
  }
}

export function fetchSchoolStats() {
  return workbenchRead('school-stats', '/stats/workbench', {}, 10_000)
}

export function trackWorkbenchEvent(event, detail = {}) {
  return request('/me/telemetry', {
    method: 'POST',
    body: { event: event || 'WORKBENCH_CLICK', detail }
  })
}

export async function fetchMyScheduleToday(teacherKey) {
  const key = String(teacherKey || '').trim()
  if (!key) return { items: [], teacherKey: '' }
  try {
    const data = await workbenchRead(
      'today-schedule',
      `/academic-affairs/schedule/teacher/${encodeURIComponent(key)}`,
      {},
      30_000
    )
    const items = Array.isArray(data?.items) ? data.items : []
    const jsDay = new Date().getDay()
    const weekday = jsDay === 0 ? 7 : jsDay
    const today = items.filter((it) => Number(it.weekday || it.dayOfWeek || 0) === weekday)
    return { items: (today.length ? today : items).slice(0, 6), teacherKey: key, weekday }
  } catch {
    return { items: [], teacherKey: key }
  }
}

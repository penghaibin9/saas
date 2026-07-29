/**
 * 教师/管理 PC 工作台真实数据入口。
 * 所有业务可见性仍由后端裁定；这里只治理相同 GET 的 single-flight、短缓存与写后失效。
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

/** 待办汇总：{ role, pending, overdue, nearDeadline, doneToday } */
export function fetchTodoSummary() {
  return workbenchRead('todo-summary', '/todos/summary', {}, 8_000)
}

/** 待办分类计数：{ total, byType } */
export function fetchTodoCount() {
  return workbenchRead('todo-count', '/admin/todos/count', {}, 8_000)
}

/** 待办列表：首屏固定最多 8 条，完整列表进入待办页服务端分页。 */
export function fetchTodoList(params = {}) {
  const safe = { status: 'PENDING', page: 1, pageSize: 8, ...params }
  safe.pageSize = Math.min(50, Math.max(1, Number(safe.pageSize) || 8))
  return workbenchRead('todo-list', '/admin/todos', { params: safe }, 5_000)
}

/** 未读消息数：{ unread, pendingAck } */
export function fetchMessageCount() {
  return workbenchRead('message-count', '/admin/messages/count', {}, 5_000)
}

/** 确认类待办完成后，主动失效工作台摘要；审批类仍进入各自业务页。 */
export async function completeTodo(todoId, comment) {
  const result = await request(`/admin/todos/${todoId}/complete`, {
    method: 'POST', body: { comment }
  })
  invalidateAdminQueries(`workbench|${identityKey()}|`)
  return result
}

/**
 * 门户壳上下文：品牌、当前身份、权限、数据范围和消息角标并行读取。
 * 任一非关键子请求失败只降级该板块，不串行拖慢整个壳。
 */
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

/** 当前身份数据范围内的工作台汇总。 */
export function fetchSchoolStats() {
  return workbenchRead('school-stats', '/stats/workbench', {}, 10_000)
}

/** 工作台点击审计，不参与读缓存。 */
export function trackWorkbenchEvent(event, detail = {}) {
  return request('/me/telemetry', {
    method: 'POST',
    body: { event: event || 'WORKBENCH_CLICK', detail }
  })
}

/** 本人今日课表摘要；失败只降级该板块。 */
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

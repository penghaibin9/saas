/**
 * 工作台数据入口（真实后端，无 mock 分支）。
 *
 * 对应后端：
 *   GET /todos/summary        本人可见范围的 待处理/逾期/临期/今日完成 + role
 *   GET /admin/todos/count    本人可见范围的 PENDING 计数，按 todoType 分组
 *   GET /admin/todos          本人可见范围的待办列表
 *   GET /admin/messages/count 本人未读消息数
 *   GET /tenant/brand         门户壳品牌（布局用）
 *   GET /rbac/current-context 门户壳角色/范围/权限码（布局用，非工作台业务角色）
 *   GET /stats/workbench      工作台汇总（P3 已按数据范围收敛：本班/本院/全校）
 *
 * 可见性由后端 services/workbench_todo_service / stats_service 统一裁定，
 * 前端不做任何过滤，也不得在此处补默认值掩盖失败——取不到就如实抛错，由页面显示错误态。
 *
 * request() 已解包统一响应的 data 字段；调用方拿到的是业务对象本身。
 */
import { request } from '@/services/http'

/** 待办汇总：{ role, pending, overdue, nearDeadline, doneToday } */
export function fetchTodoSummary() {
  return request('/todos/summary')
}

/** 待办分类计数：{ total, byType: { LEAVE_APPROVAL: 3, ... } } */
export function fetchTodoCount() {
  return request('/admin/todos/count')
}

/** 待办列表：{ items, total, page, pageSize }；字段含 todoId/todoType/title/priority/dueAt */
export function fetchTodoList(params = {}) {
  return request('/admin/todos', { params: { status: 'PENDING', pageSize: 8, ...params } })
}

/** 未读消息数：{ unread, pendingAck } */
export function fetchMessageCount() {
  return request('/admin/messages/count')
}

/**
 * 完成待办（确认类）。业务审批仍须走各自业务页，此处只处理可直接确认的待办。
 * P2 列表下钻不调用本方法；保留供后续明细办理复用。
 */
export function completeTodo(todoId, comment) {
  return request(`/admin/todos/${todoId}/complete`, { method: 'POST', body: { comment } })
}

/**
 * 门户壳上下文（品牌 + 当前身份 + 权限码 + 消息未读角标）。
 * 对齐学工/实习布局：真实共享端点，失败时静默降级保证壳可渲染；
 * 工作台业务数字仍由 fetchTodo* 严格失败，不在此兜底。
 *
 * 工作台「我是谁」业务角色权威来源仍是 /todos/summary.role，
 * 本函数仅服务 BasePortalLayout 菜单/顶栏，不参与 recipe 选择。
 */
export async function fetchLayoutContext() {
  let brand = { schoolName: '管理端' }
  let currentRole = { roleCode: '', roleName: '', userName: '', roleType: '' }
  let dataScope = { scopeName: '' }
  let permissionPatterns = null
  let ctxKey = ''
  let messageUnreadCount = 0
  let readonlyTenant = false
  let readonlyReason = ''

  try {
    const b = await request('/tenant/brand')
    if (b) {
      brand = {
        ...brand,
        ...b,
        schoolName: b.schoolName || brand.schoolName
      }
    }
  } catch {
    /* 品牌兜底，不阻断壳 */
  }

  try {
    const ctx = await request('/rbac/current-context')
    if (ctx.currentRole) {
      currentRole = { ...currentRole, ...ctx.currentRole }
      // adminMenu.roleType() 读 roleType||type；rbac 只下发 roleCode。
      // 用后端已返回的 roleCode 填 roleType，供一级轨白名单 fail-closed；不是前端猜角色。
      if (!currentRole.roleType && currentRole.roleCode) {
        currentRole.roleType = currentRole.roleCode
      }
  ctxKey = [
        String(ctx.tenantId || currentRole.tenantId || ''),
        String(ctx.userId || currentRole.userId || ''),
        currentRole.contextId || '',
        currentRole.permissionVersion || '',
        currentRole.roleCode || '',
        Array.isArray(permissionPatterns) ? [...permissionPatterns].sort().join(',') : '',
        Array.isArray(ctx.moduleEntitlements) ? [...ctx.moduleEntitlements].sort().join(',') : '',
      ].join('|')
    }
    if (ctx.dataScope) {
      dataScope = {
        ...dataScope,
        ...ctx.dataScope,
        scopeName: ctx.dataScope.scopeName || ctx.dataScope.scopeLabel || ''
      }
    }
    if (Array.isArray(ctx.permissionPatterns)) {
      permissionPatterns = ctx.permissionPatterns
    }
    readonlyTenant = !!ctx.readonlyTenant
    readonlyReason = ctx.readonlyReason || (
      readonlyTenant
        ? '正式演示环境为只读，数据不可修改。需要动手体验请用沙箱账号登录（admin2 / teacher2 / student2，密码 123456）'
        : ''
    )
  } catch {
    /* 身份上下文失败：壳仍可开；业务数字由工作台页独立报错 */
  }

  try {
    const cnt = await fetchMessageCount()
    messageUnreadCount = (cnt && cnt.unread) || 0
  } catch {
    /* 消息角标失败不阻断壳 */
  }

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

/**
 * 工作台汇总（按当前身份数据范围收敛，含 scopeType/scopeLabel）。
 * T4 辅导员样板仍以 /todos/summary 为主；本接口供校级/院级汇总磁贴与 /dashboard/summary 使用。
 * 数据中心全校 BI（/stats/overview 等）对一线角色会 403，勿当作兜底。
 */
export function fetchSchoolStats() {
  return request('/stats/workbench')
}

/**
 * 工作台埋点（独立通道，不写偏好计数冒充分析）。
 * POST /me/telemetry → 审计队列 WORKBENCH_CLICK。
 */
export function trackWorkbenchEvent(event, detail = {}) {
  return request('/me/telemetry', {
    method: 'POST',
    body: { event: event || 'WORKBENCH_CLICK', detail }
  })
}

/**
 * B8：本人今日课表摘要（失败返回空，不阻断工作台主链）。
 * teacherKey 优先用工号/登录名；与课表页本人口径一致。
 */
export async function fetchMyScheduleToday(teacherKey) {
  const key = String(teacherKey || '').trim()
  if (!key) return { items: [], teacherKey: '' }
  try {
    const data = await request(`/academic-affairs/schedule/teacher/${encodeURIComponent(key)}`)
    const items = Array.isArray(data && data.items) ? data.items : []
    // 无周次参数时后端回整学期；前端取 weekday=今日（1=周一）摘要最多 6 条
    const jsDay = new Date().getDay() // 0=日
    const weekday = jsDay === 0 ? 7 : jsDay
    const today = items.filter((it) => Number(it.weekday || it.dayOfWeek || 0) === weekday)
    return { items: (today.length ? today : items).slice(0, 6), teacherKey: key, weekday }
  } catch {
    return { items: [], teacherKey: key }
  }
}

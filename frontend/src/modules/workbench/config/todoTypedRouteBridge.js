import { TODO_TYPE_ROUTES } from './workbenchRecipes'

function routeWithQuery(item) {
  const path = String(item?.routePath || '').trim()
  if (!path) return ''
  const query = item?.query && typeof item.query === 'object' ? item.query : {}
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value) !== '') params.set(key, String(value))
  })
  const suffix = params.toString()
  if (!suffix) return path
  return `${path}${path.includes('?') ? '&' : '?'}${suffix}`
}

/**
 * P1-07 兼容桥：WorkbenchView 的旧 openTodo() 仍通过 TODO_TYPE_ROUTES 查地址，
 * 这里把服务端 typed DTO 的 routePath/query 注册成“本条待办专属键”。
 * 因此正式数据不再按 todoType 猜地址；旧静态映射只作为无 typed DTO 时的兼容兜底。
 */
export function adaptTypedTodo(item) {
  if (!item || typeof item !== 'object') return item
  const target = routeWithQuery(item)
  if (!target || !item.routeName) return item
  const originalType = String(item.todoType || '')
  const key = `__typed_todo__:${item.todoId || item.recordId || 'row'}:${item.version ?? 0}`
  TODO_TYPE_ROUTES[key] = target
  return {
    ...item,
    todoTypeName: item.todoTypeName || originalType,
    contractTodoType: originalType,
    todoType: key,
    typedRouteTarget: target
  }
}

export function adaptTypedTodoPage(page) {
  if (!page || typeof page !== 'object') return page
  const items = Array.isArray(page.items) ? page.items.map(adaptTypedTodo) : []
  return { ...page, items }
}

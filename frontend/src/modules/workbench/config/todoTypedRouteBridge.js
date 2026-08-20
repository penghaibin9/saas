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
 * P1-07 typed todo bridge：服务端 routePath/query 直接成为本条待办的 typedRouteTarget。
 * 不再为了兼容旧 openTodo() 往全局静态路由映射写“每条记录专属键”，避免长会话中
 * 随刷新/分页不断累积记录级路由和跨记录残留。静态 todoType 映射仅由消费端作为旧 DTO 兜底。
 *
 * V3 施工手册 TP-W07：todo_route_registry 只区分 exact（真详情页）/ 非 exact（可处理
 * 列表，recordId 供 query 携带，页面不一定实现了定位）。这里把它显式归一成
 * focusMode（DETAIL/NONE），consumer 必须据此决定文案——NONE 只能说"前往列表"，
 * 不能假装"打开了这条对象"。没有真实 LIST_FOCUS 事实前，不伪造中间态。
 */
export function adaptTypedTodo(item) {
  if (!item || typeof item !== 'object') return item
  const target = routeWithQuery(item)
  if (!target || !item.routeName) return { ...item, focusMode: 'NONE' }
  const originalType = String(item.todoType || '')
  return {
    ...item,
    todoTypeName: item.todoTypeName || originalType,
    contractTodoType: originalType,
    typedRouteTarget: target,
    focusMode: item.routeExact ? 'DETAIL' : 'NONE'
  }
}

export function adaptTypedTodoPage(page) {
  if (!page || typeof page !== 'object') return page
  const items = Array.isArray(page.items) ? page.items.map(adaptTypedTodo) : []
  return { ...page, items }
}

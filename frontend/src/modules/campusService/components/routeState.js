/**
 * 列表上下文 ←→ 路由 query 同步（返回列表 / 刷新 / 前进后退不丢筛选、页码、选中项、页签）。
 * 只写入 page / 页签 / 选中 id / 筛选字段等非敏感短值；禁止把完整业务对象或敏感明文写入 URL。
 */

/** 从路由 query 读取列表状态；filterKeys 之外的 query 一律忽略 */
export function readListState(route, filterKeys = []) {
  const q = (route && route.query) || {}
  const filters = {}
  for (const k of filterKeys) {
    if (q[k] != null && q[k] !== '') filters[k] = String(q[k])
  }
  return {
    page: Math.max(1, parseInt(q.page, 10) || 1),
    filters,
    selectedId: q.sel ? String(q.sel) : '',
    tab: q.tab ? String(q.tab) : ''
  }
}

/** 把列表状态写回路由 query（replace，不产生历史噪音；值为空的键删除） */
export function writeListState(router, route, { page, filters = {}, selectedId, tab, filterKeys = [] }) {
  if (!router || !route) return
  const query = { ...route.query }
  const setOrDel = (k, v) => {
    if (v == null || v === '' || v === undefined) delete query[k]
    else query[k] = String(v)
  }
  setOrDel('page', page && page > 1 ? page : '')
  setOrDel('sel', selectedId)
  setOrDel('tab', tab)
  for (const k of filterKeys) setOrDel(k, filters[k])
  const same = JSON.stringify(query) === JSON.stringify(route.query)
  if (!same) router.replace({ query }).catch(() => {})
}

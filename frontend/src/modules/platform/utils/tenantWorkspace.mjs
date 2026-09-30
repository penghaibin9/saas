/** Display/navigation only. Runtime entitlement and state transitions remain server-owned. */
const STATUSES = { trial: ['warning', '试用中'], active: ['success', '正式'], expired: ['danger', '已到期'], disabled: ['default', '已停用'] }
export const LIST_PATHS = new Set(['/admin/platform/tenants', '/admin/platform/features', '/admin/platform/rules', '/admin/platform/workflows', '/admin/platform/brands', '/admin/platform/users'])
export const TABS = new Set(['info', 'features', 'rules', 'workflows', 'brand', 'users', 'studentPortal', 'offboarding'])
const scalar = value => typeof value === 'string' ? value : ''
export function wholeNumber(value) {
  if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) return null
  const n = Number(value)
  return Number.isSafeInteger(n) && n >= 0 ? n : null
}
export function countLabel(value) {
  const n = wholeNumber(value)
  return n === null ? '未取得' : n.toLocaleString('zh-CN')
}
export function statusLabel(value) { return STATUSES[value]?.[1] || '状态待核实' }
export function statusTone(value) { return STATUSES[value]?.[0] || 'warning' }
export function environmentLabel(value) {
  return ({ production: '生产环境', prod: '生产环境', demo: '样例环境', sandbox: '沙箱环境', test: '测试环境' })[value] || '环境未取得'
}
export function dateLabel(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.replace('T', ' ').slice(0, 10) : '未取得'
}
export function usagePercent(used, limit) {
  const u = wholeNumber(used), l = wholeNumber(limit)
  return u === null || l === null || l === 0 ? null : Math.min(100, Math.round(u / l * 100))
}
export function parseListQuery(query = {}) {
  return {
    keyword: scalar(query.keyword).trim().slice(0, 100),
    status: Object.hasOwn(STATUSES, scalar(query.status)) ? query.status : '',
    page: Math.max(1, wholeNumber(query.page) || 1),
    pageSize: [20, 50, 100].includes(wholeNumber(query.pageSize)) ? wholeNumber(query.pageSize) : 20
  }
}
export function listQuery(filters) {
  const f = parseListQuery(filters), out = {}
  if (f.keyword) out.keyword = f.keyword
  if (f.status) out.status = f.status
  if (f.page > 1) out.page = String(f.page)
  if (f.pageSize !== 20) out.pageSize = String(f.pageSize)
  return out
}
export function tenantLocation(id, tab = 'info', route = {}) {
  // BIGINT identifiers stay strings; never coerce a tenant id through Number.
  if (typeof id !== 'string' || !/^[1-9]\d*$/.test(id)) return null
  const filters = parseListQuery(route.query)
  return { path: `/admin/platform/tenants/${id}`, query: {
    tab: TABS.has(tab) ? tab : 'info',
    returnTo: LIST_PATHS.has(route.path) ? route.path : '/admin/platform/tenants',
    listKeyword: filters.keyword, listStatus: filters.status,
    listPage: String(filters.page), listPageSize: String(filters.pageSize)
  } }
}
export function returnLocation(query = {}) {
  return { path: LIST_PATHS.has(query.returnTo) ? query.returnTo : '/admin/platform/tenants',
    query: listQuery({ keyword: query.listKeyword, status: query.listStatus, page: query.listPage, pageSize: query.listPageSize }) }
}
export function authorityLabel(row = {}) {
  if (row.commercialAuthorityVerified === false) return '授权待核验'
  if (row.commercialAuthorityVerified !== true) return '需在详情核验'
  if (row.commercialAuthoritySource === 'TRIAL') return '试用授权'
  if (row.commercialAuthoritySource === 'CONTROLLED_EXCEPTION') return '受控特批'
  return '授权已核验'
}
export function validateTenantList(data) {
  if (!data || !Array.isArray(data.list)) throw new Error('学校清单数据格式异常，请重新读取')
  if (data.list.some(row => !row || typeof row !== 'object' || typeof row.tenantId !== 'string' || !/^[1-9]\d*$/.test(row.tenantId))) throw new Error('学校标识缺失或格式异常，已停止展示')
  if (new Set(data.list.map(row => row.tenantId)).size !== data.list.length) throw new Error('学校清单包含重复标识，请重新读取')
  // The current endpoint returns the entire filtered list. Do not silently treat
  // a future server-paginated response as a complete local pagination source.
  if (data.total != null && wholeNumber(data.total) !== data.list.length) throw new Error('学校清单尚未完整返回，不能据此判断总数')
  return data.list
}

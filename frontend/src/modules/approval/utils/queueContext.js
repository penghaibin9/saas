/**
 * PcQueueContext v1（V3 施工手册 §14.3 · Lane T / T3）。
 *
 * 实现选择：字段直接铺平进 route.query（bizType/urgency/keyword/submitDate/
 * result/actedFrom/actedTo/page/pageSize/source/tab），不整体编码成一个不透明
 * blob。理由：铺平字段可读、可收藏/分享 URL、天然配合浏览器前进/后退与
 * router.replace 做 URL 状态同步，也不需要额外的编解码失败兜底路径；字段集合
 * 与手册 14.3 定义的 PcQueueContext 完全对应，只是序列化载体不同（query string
 * 而不是 base64 JSON）。
 *
 * 安全规则（手册 14.3 明示，不得违反）：
 * - qctx 永远不参与服务端授权判断——所有服务端接口仍必须按当前登录身份 + 租户
 *   重新计算可见性/可操作性，qctx 只用于"回到原队列"的 UX 续航。
 * - returnTo 只允许命中下面的内部 allowlist，不接受任意外部或业务猜测路径，
 *   防止把 query 里的任意字符串当跳转目标用。
 */

export const QCTX_VERSION = 1

export const RETURN_ALLOWLIST = Object.freeze([
  '/admin/approval/todos',
  '/admin/approval/done'
])

const FILTER_KEYS = ['bizType', 'urgency', 'keyword', 'submitDate', 'result', 'actedFrom', 'actedTo', 'readStatus']

export function pickFilters(source = {}) {
  const out = {}
  for (const key of FILTER_KEYS) {
    if (source[key]) out[key] = source[key]
  }
  return out
}

/** 列表页跳转详情时调用：把当前生效筛选 + 分页 + 来源列表铺平进详情页 query。 */
export function buildDetailQuery({ filters, page, pageSize, returnTo, tab } = {}) {
  const safeReturnTo = RETURN_ALLOWLIST.includes(returnTo) ? returnTo : RETURN_ALLOWLIST[0]
  const query = { ...pickFilters(filters), source: safeReturnTo }
  if (page && Number(page) > 1) query.page = String(page)
  if (pageSize && Number(pageSize) !== 10) query.pageSize = String(pageSize)
  if (tab) query.tab = tab
  return query
}

/** 详情页"返回列表"时调用：把当前 route.query 里的 qctx 字段还原成列表页 query。 */
export function buildReturnQuery(routeQuery = {}) {
  const query = pickFilters(routeQuery)
  if (routeQuery.page) query.page = routeQuery.page
  if (routeQuery.pageSize) query.pageSize = routeQuery.pageSize
  if (routeQuery.tab) query.tab = routeQuery.tab
  return query
}

/** 详情页"返回列表"时调用：算出真实要跳回的列表路径，只认 allowlist。 */
export function returnPath(routeQuery = {}) {
  const source = String(routeQuery.source || '')
  return RETURN_ALLOWLIST.includes(source) ? source : RETURN_ALLOWLIST[0]
}

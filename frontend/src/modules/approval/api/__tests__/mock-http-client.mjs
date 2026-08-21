/** TP-A10 契约测试用 mock（劫持 @/services/http/client 的 request）：按 URL 路径路由到
 * 测试驱动的固定响应，记录调用次数。 */
const calls = globalThis.__APPROVAL_BIZ_TYPE_CALLS__ || (globalThis.__APPROVAL_BIZ_TYPE_CALLS__ = [])

export async function request(path) {
  calls.push(path)
  const state = globalThis.__APPROVAL_BIZ_TYPE_STATE__ || {}
  if (path === '/approvals/biz-types') {
    if (state.bizTypesShouldFail) throw new Error('biz-types unavailable')
    return state.bizTypes || []
  }
  if (path === '/tenant/brand') return { schoolName: '测试学校' }
  if (path === '/rbac/current-context') {
    return { permissionPatterns: [], currentRole: {}, dataScope: {} }
  }
  throw new Error(`unexpected request: ${path}`)
}

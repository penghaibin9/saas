/** TP-W11 契约测试用 mock（劫持 @/services/http 的 request）：记录调用次数，返回按当前身份
 * 状态编好的快照，用来断言 identityKey() 是否真的按身份维度重新取数。 */
export async function request() {
  const state = globalThis.__WB_IDENTITY_STATE__ || {}
  const calls = globalThis.__WB_IDENTITY_CALLS__ || (globalThis.__WB_IDENTITY_CALLS__ = [])
  calls.push(state.claims ? state.claims.currentRoleCode : null)
  const role = state.claims ? state.claims.currentRoleCode : ''
  return { summary: { role }, count: {}, todos: {}, messages: {} }
}

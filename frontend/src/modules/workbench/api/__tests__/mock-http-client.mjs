/** TP-W11 契约测试用 mock（由 workbenchIdentityKey.contract.hooks.mjs 劫持
 * @/services/http/client）：只暴露 identityKey() 需要的 getToken/currentUserFromToken，
 * 状态由测试文件通过 globalThis 驱动。 */
export function getToken() {
  const state = globalThis.__WB_IDENTITY_STATE__
  return (state && state.token) || ''
}

export function currentUserFromToken() {
  const state = globalThis.__WB_IDENTITY_STATE__
  return (state && state.claims) || null
}

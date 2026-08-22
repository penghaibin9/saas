/**
 * TP-W11：workbenchRead 去重 key 必须随身份维度（tenant/user/role/context）变化，不能只依赖
 * "token 恰好也变了"这一间接推论。见 workbench.api.js::identityKey() 的注释。
 *
 * 运行（在 frontend/ 目录）：
 *   node --test src/modules/workbench/api/__tests__/workbenchIdentityKey.contract.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL, fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '../../../../..')

const mockHttpUrl = pathToFileURL(path.join(__dirname, 'mock-http.mjs')).href
const mockClientUrl = pathToFileURL(path.join(__dirname, 'mock-http-client.mjs')).href

register('./workbenchIdentityKey.contract.hooks.mjs', import.meta.url, {
  data: { frontendRoot, mockHttpUrl, mockClientUrl }
})

globalThis.__WB_IDENTITY_CALLS__ = []

function setIdentity(token, claims) {
  globalThis.__WB_IDENTITY_STATE__ = { token, claims }
}

const { fetchWorkbenchSnapshot } = await import('../workbench.api.js')

test('同身份维度命中缓存，只发一次真实请求', async () => {
  globalThis.__WB_IDENTITY_CALLS__.length = 0
  setIdentity('token-header-payload.sig-0001aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', {
    tenantId: 't1', userId: 'u1', currentRoleCode: 'COUNSELOR', activeContextId: 'ctx1'
  })
  await fetchWorkbenchSnapshot()
  await fetchWorkbenchSnapshot()
  assert.equal(globalThis.__WB_IDENTITY_CALLS__.length, 1)
})

test('角色切换签发新 token 且 claims 变化：不得复用上一个角色的缓存快照', async () => {
  globalThis.__WB_IDENTITY_CALLS__.length = 0
  setIdentity('token-header-payload.sig-role-a-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', {
    tenantId: 't1', userId: 'u1', currentRoleCode: 'COUNSELOR', activeContextId: 'ctx1'
  })
  const first = await fetchWorkbenchSnapshot()
  assert.equal(first.summary.role, 'COUNSELOR')

  // browser-switch-role 签发全新 accessToken 并切换 currentRoleCode/activeContextId。
  setIdentity('token-header-payload.sig-role-b-cccccccccccccccccccccccccccccccccccccc', {
    tenantId: 't1', userId: 'u1', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'ctx2'
  })
  const second = await fetchWorkbenchSnapshot()

  assert.equal(second.summary.role, 'ACADEMIC_ADMIN')
  assert.equal(globalThis.__WB_IDENTITY_CALLS__.length, 2)
})

test('同租户/用户/角色切换 activeContextId（跨校区/跨范围）也必须重新取数', async () => {
  globalThis.__WB_IDENTITY_CALLS__.length = 0
  setIdentity('token-header-payload.sig-ctx-a-dddddddddddddddddddddddddddddddddddddd', {
    tenantId: 't1', userId: 'u1', currentRoleCode: 'COUNSELOR', activeContextId: 'ctx1'
  })
  await fetchWorkbenchSnapshot()

  setIdentity('token-header-payload.sig-ctx-a-dddddddddddddddddddddddddddddddddddddd', {
    tenantId: 't1', userId: 'u1', currentRoleCode: 'COUNSELOR', activeContextId: 'ctx2'
  })
  await fetchWorkbenchSnapshot()

  assert.equal(globalThis.__WB_IDENTITY_CALLS__.length, 2)
})

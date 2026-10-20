import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { studentAcademicIdentity } from '../src/components/academic/studentAcademicCommandGuard.js'

function sessionStore(loginResult) {
  const values = new Map()
  const sandbox = {
    defineStore: (_id, options) => options,
    portalApi: { login: async () => loginResult },
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
    getToken: () => '', setToken() {}, setRefreshToken() {}, clearSession() {}, request: async () => ({})
  }
  const source = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useSessionStore =', 'globalThis.definition =')
  vm.runInNewContext(source, sandbox)
  const store = sandbox.definition.state()
  for (const [key, action] of Object.entries(sandbox.definition.actions)) store[key] = action.bind(store)
  return store
}

test('login and auth/me restore identify the same tenant, student and active context', async () => {
  const store = sessionStore({ accessToken: 'test-token', tenantId: '42', activeContextId: 'ctx-student', currentRole: { roleCode: 'STUDENT' }, user: { userId: 'db-7', userType: 'STUDENT', realName: 'Test' } })
  await store.login('test-student', 'test-only-password')
  assert.equal(store.user.tenantId, '42')
  assert.equal(store.user.activeContextId, 'ctx-student')
  const initial = studentAcademicIdentity(store)
  store.user = { userId: 'db-7', userType: 'STUDENT', tenantId: '42', activeContextId: 'ctx-student', currentRole: { roleCode: 'STUDENT' } }
  store.token = 'refreshed-test-token'
  assert.equal(studentAcademicIdentity(store), initial)
  store.user.studentNo = 'corrected-student-number'
  assert.equal(studentAcademicIdentity(store), initial)
  store.user.activeContextId = 'ctx-other'
  assert.notEqual(studentAcademicIdentity(store), initial)
})

test('tenant changes never reuse the previous identity and tokens are absent from persistent identity', async () => {
  const store = sessionStore({ accessToken: 'never-persist-this-token', tenantId: '42', activeContextId: 'ctx-student', currentRole: { roleCode: 'STUDENT' }, user: { userId: 'db-7', userType: 'STUDENT' } })
  await store.login('test-student', 'test-only-password')
  const first = studentAcademicIdentity(store)
  assert.equal(first.includes(store.token), false)
  store.user.tenantId = '43'
  assert.notEqual(studentAcademicIdentity(store), first)
})

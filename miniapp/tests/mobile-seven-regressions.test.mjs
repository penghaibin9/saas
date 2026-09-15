import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
const flush = () => new Promise(resolve => setImmediate(resolve))
function component(path, context = {}) {
  const source = readFileSync(new URL('../src/' + path, import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '').replace('export default', 'module.exports =')
  // 组件源码的 import 会在该轻量 VM 夹具中剥离；消息展示层的行为由
  // message-presentation.test.mjs 独立覆盖，这里保留其纯投影接口以验证详情生命周期。
  const scope = { module: { exports: {} }, presentMessage: item => item, ...context }
  vm.runInNewContext(source, scope)
  const c = scope.module.exports
  const state = c.data ? c.data() : {}
  for (const [key, fn] of Object.entries(c.methods || {})) state[key] = fn.bind(state)
  return { c, state, scope }
}
for (const side of ['student', 'teacher']) {
  for (const phase of ['wx-native', 'wx-response', 'select-response', 'select-callback', 'final']) {
    test(`${side}: cancelled ${phase} cannot commit or navigate`, async () => {
      let native, sheet, resolve
      const commits = [], homes = [], calls = []
      const { state: p } = component('components/login/MiniLoginAuthPanel.vue', {
        tenantBrandConfig: {}, getLastTenantCode: () => '', saveLastTenantCode: () => {}, toast() {},
        roleKeyFromBackendRole: () => side, commitNewSessionTokens: (...args) => commits.push(args),
        useSessionStore: () => ({ login() {}, applyRealUser() {} }), relaunch: path => homes.push(path),
        studentApi: { getProfile: () => Promise.resolve({}) },
        uni: { login: options => { native = options }, showActionSheet: options => { sheet = options } },
        realRequest: path => { calls.push(path); return new Promise(r => { resolve = r }) }
      })
      p.isTeacher = side === 'teacher'; p.agree = true
      const data = { accessToken: 'test', currentRole: { roleCode: side === 'teacher' ? 'TEACHER' : 'STUDENT' } }
      if (phase === 'final') { p.invalidateLogin(); p.completeLogin(data) }
      else {
        p.wechatLogin()
        if (phase === 'wx-native') { p.invalidateLogin(); native.success({ code: 'code' }) }
        else {
          native.success({ code: 'code' })
          if (phase === 'wx-response') { p.invalidateLogin(); resolve(data) }
          else {
            resolve({ needSelectTenant: true, wxToken: 'ticket', accounts: [{ tenantCode: 'a' }] }); await flush()
            if (phase === 'select-callback') { p.invalidateLogin(); sheet.success({ tapIndex: 0 }) }
            else { sheet.success({ tapIndex: 0 }); p.invalidateLogin(); resolve(data) }
          }
        }
      }
      await flush()
      assert.equal(commits.length, 0); assert.equal(homes.length, 0)
      if (phase === 'wx-native') assert.equal(calls.length, 0)
      if (phase === 'select-callback') assert.equal(calls.length, 1)
    })
  }
  test(`${side}: missing B never exposes A; read failure stays unread and retries`, async () => {
    let fail = true, reads = 0
    const detail = async () => { if (fail) throw { code: 404001 }; return { id: '202', read: false } }
    const mark = async () => { reads++; if (reads === 1) throw { code: 'NETWORK' } }
    const { c, state: p } = component('pages/common/message-detail/index.vue', {
      popDetail: () => ({ id: '101', content: 'private-A', receipt: true }),
      useSessionStore: () => ({ side }), currentSessionGeneration: () => 0,
      normalizeError: () => ({ kind: 'notfound', text: '不存在' }), toast() {},
      getMessageDetail: detail, getTeacherMessageDetail: detail,
      markMessageRead: mark, markTeacherMessageRead: mark
    })
    c.onLoad.call(p, { id: '202' }); await flush()
    assert.equal(p.m, null); assert.equal(c.computed.showAck.call(p), false)
    fail = false; await p.loadDetail(); await flush()
    assert.equal(p.m.id, '202'); assert.equal(p.m.read, false); assert.equal(p.readError, true)
    await p.readMessage(); assert.equal(p.m.read, true); assert.equal(p.readError, false)
    c.onHide.call(p); assert.equal(p.m, null)
  })
}
test('subscription request uses up to three distinct template IDs, and reports reject/failure', () => {
  let options
  const messages = []
  const { state: p } = component('pages/common/notify-settings/index.vue', {
    uni: { requestSubscribeMessage: value => { options = value } }, toast: text => messages.push(text)
  })
  p.wechat = { configured: true, scenes: [1, 2, 3, 4].map(n => ({ key: 'SCENE' + n, templateId: 'template-' + n, ready: true })) }
  p.requestSubscribe()
  assert.deepEqual(Array.from(options.tmplIds), ['template-1', 'template-2', 'template-3'])
  options.success({ 'template-1': 'reject', 'template-2': 'ban' }); assert.match(messages.at(-1), /未接受/)
  options.fail(); assert.match(messages.at(-1), /失败/)
  p.requesting = false; p.wechat.configured = false; options = null; p.requestSubscribe(); assert.equal(options, null)
})
test('native logout waits for server confirmation and keeps local state on failure', async () => {
  const source = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useSessionStore =', 'const useSessionStore =').replace('export default useSessionStore', 'module.exports = useSessionStore').replaceAll('import.meta.env', '({ PROD: true })')
  let result = { tokenInvalidated: false }, cleared = 0, request
  const ctx = { module: { exports: {} }, defineStore: (_, config) => config, registerForceLogoutHandler() {},
    getToken: () => 'test-token', getRefreshToken: () => 'test-refresh',
    realRequest: async (path, options) => { request = { path, options }; return result }
  }
  vm.runInNewContext(source, ctx)
  const state = { logout() { cleared++ } }
  const logout = ctx.module.exports.actions.logoutCurrentSession.bind(state)
  await assert.rejects(logout()); assert.equal(cleared, 0)
  result = { tokenInvalidated: true }; await logout()
  assert.equal(cleared, 1); assert.equal(request.path, '/auth/logout?scope=current')
})

test('academic session plugin cannot restore an identity before the browser session is verified', () => {
  const source = readFileSync(new URL('../src/stores/sessionAcademicPlugin.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '')
    .replace('export function academicSessionPlugin', 'function academicSessionPlugin')
    .replace('export default academicSessionPlugin', 'module.exports = academicSessionPlugin')
  const storage = new Map([['gx_session_v1', JSON.stringify({
    logged: true,
    identity: { tenantId: 'tenant-a', studentId: 'student-a', realName: '旧学生A' }
  })]])
  const context = {
    module: { exports: {} },
    clearSensitiveLocalDrafts() {},
    uni: {
      getStorageSync: key => storage.get(key) || '',
      setStorageSync: (key, value) => storage.set(key, value)
    }
  }
  vm.runInNewContext(source, context)
  const store = {
    $id: 'session',
    identity: {},
    persistedIdentityVerified: false,
    $patch(value) { Object.assign(this, value) },
    persist() {},
    restore() { this.identity = {}; this.persistedIdentityVerified = false },
    applyRealUser() {},
    setStudentIdentity() {},
    hydrateStudentProfile() {},
    logout() {}
  }
  context.module.exports({ store })
  store.restore()
  assert.deepEqual(store.identity, {})
  assert.equal(Object.hasOwn(JSON.parse(storage.get('gx_session_v1')), 'identity'), false)
})
test('message stash is one-use and invalidates on session change and ID mismatch', () => {
  const source = readFileSync(new URL('../src/utils/msgStash.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replaceAll('export function', 'function') + '\nmodule.exports={stashDetail,popDetail}'
  let generation = 0
  const ctx = { module: { exports: {} }, currentSessionGeneration: () => generation, getToken: () => 'token', uni: { removeStorageSync() {} } }
  vm.runInNewContext(source, ctx)
  const stash = ctx.module.exports
  stash.stashDetail({ id: '101', content: 'secret' }); assert.equal(stash.popDetail('202'), null)
  stash.stashDetail({ id: '101' }); generation++; assert.equal(stash.popDetail('101'), null)
  stash.stashDetail({ id: '101', content: 'secret' }); assert.equal(stash.popDetail('101').content, 'secret'); assert.equal(stash.popDetail(), null)
})

test('same-session business summaries remain readable without inventing read/receipt writes', async () => {
  let generation = 0, requests = 0
  const { c, state: p } = component('pages/common/message-detail/index.vue', {
    popDetail: () => ({ id: 'todo-55', kind: 'TODO_AGG', title: '待补交材料', receipt: true }),
    currentSessionGeneration: () => generation, useSessionStore: () => ({ side: 'student' }),
    getMessageDetail: () => { requests++; throw Error('not a unified message') }
  })
  c.onLoad.call(p, { id: 'todo-55' }); await flush()
  assert.equal(p.m.title, '待补交材料'); assert.equal(c.computed.showAck.call(p), false)
  await p.readMessage(); await p.ack(); assert.equal(requests, 0)
  c.onHide.call(p); generation++; c.onShow.call(p)
  assert.equal(p.m, null)
})

test('reloading a detail instance never carries summary A into another object B', async () => {
  let stash = { id: 'todo-55', kind: 'TODO_AGG', title: '摘要 A' }
  const { c, state: p } = component('pages/common/message-detail/index.vue', {
    popDetail: () => { const item = stash; stash = null; return item },
    currentSessionGeneration: () => 0, useSessionStore: () => ({ side: 'student' }),
    getMessageDetail: async () => ({ id: '202', read: true, receipt: true })
  })
  c.onLoad.call(p, { id: 'todo-55' }); await flush()
  assert.equal(p.m.title, '摘要 A')
  c.onLoad.call(p, { id: 'todo-99' }); await flush()
  assert.equal(p.m, null)
  c.onLoad.call(p, { id: '202' }); await flush()
  assert.equal(p.m.id, '202')
  assert.equal(c.computed.showAck.call(p), true)
})

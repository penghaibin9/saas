import { normalizeLoginTenantHint } from '../src/utils/loginTenantHint.mjs'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/components/login/MiniLoginAuthPanel.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
const flush = () => new Promise(resolve => setImmediate(resolve))

function panel({ reject = false } = {}) {
  let settle
  const requests = [], messages = [], logins = [], copies = []
  const context = {
    module: { exports: {} }, normalizeLoginTenantHint, tenantBrandConfig: {}, getLastTenantCode: () => 'school-a',
    saveLastTenantCode: () => {}, toast: text => messages.push(text),
    realRequest: (path, options) => { requests.push({ path, options }); return new Promise((resolve, fail) => { settle = reject ? fail : resolve }) },
    uni: { showModal: options => { context.modal = options }, setClipboardData: options => { copies.push(options.data); options.success() } }
  }
  vm.runInNewContext(script, context)
  const component = context.module.exports
  const instance = { ...component.data(), entry: 'student', isTeacher: false }
  for (const [name, method] of Object.entries(component.methods)) instance[name] = method.bind(instance)
  instance.completeLogin = data => logins.push(data)
  instance.handleCaptchaError = () => false
  instance.binding = true
  instance.wxToken = 'applicant-token'
  instance.bindForm = { loginName: ' student ', password: 'not-a-real-password', tenantCode: 'school-a' }
  return { instance, requests, messages, logins, copies, context, settle: data => settle(data) }
}

test('approval is transient and is transmitted only to binding endpoint', async () => {
  const p = panel()
  p.instance.bindingApprovalToken = '  ' + 'A'.repeat(43) + '  '
  p.instance.submitBind()
  assert.equal(p.requests.length, 1)
  assert.equal(p.requests[0].path, '/auth/wx-bind')
  assert.equal(p.requests[0].options.data.bindingApprovalToken, 'A'.repeat(43))
  p.settle({ userId: 'db-7' }); await flush()
  assert.equal(p.instance.bindingApprovalToken, '')
  assert.equal(p.instance.bindForm.password, '')
  assert.equal(p.instance.wxToken, '')
  assert.equal(p.logins.length, 1)
})

for (const code of ['WX_BIND_APPROVAL_REQUIRED', 'WX_BIND_APPROVAL_INVALID']) {
  test(`${code} reveals the independent verification step`, async () => {
    const p = panel({ reject: true })
    p.instance.bindingApprovalToken = 'A'.repeat(43)
    p.instance.submitBind(); p.settle({ bizCode: code, message: 'contact school' }); await flush()
    assert.equal(p.instance.bindingApprovalRequired, true)
    assert.equal(p.instance.bindLoading, false)
    assert.equal(p.logins.length, 0)
    if (code.endsWith('INVALID')) assert.equal(p.instance.bindingApprovalToken, '')
  })
}

test('cancel clears secrets and ignores an already in-flight response', async () => {
  const p = panel()
  p.instance.bindingApprovalToken = 'A'.repeat(43)
  p.instance.submitBind(); p.instance.cancelBind(); p.settle({ userId: 'db-7' }); await flush()
  assert.equal(p.instance.bindingApprovalToken, '')
  assert.equal(p.instance.bindForm.password, '')
  assert.equal(p.instance.wxToken, '')
  assert.equal(p.logins.length, 0)
})

test('copy requires confirmation and never copies the campus password or approval code', () => {
  const p = panel()
  p.instance.bindingApprovalToken = 'A'.repeat(43)
  p.instance.copyWxBindingRequest()
  assert.equal(p.copies.length, 0)
  p.context.modal.success({ confirm: true })
  assert.deepEqual(p.copies, ['applicant-token'])
})

test('stale copy confirmation cannot copy a cancelled or replaced request', () => {
  const p = panel()
  p.instance.copyWxBindingRequest(); p.instance.cancelBind()
  p.context.modal.success({ confirm: true })
  assert.equal(p.copies.length, 0)
})

test('double submit makes one request; missing WeChat ticket makes no request', () => {
  const p = panel()
  p.instance.submitBind(); p.instance.submitBind()
  assert.equal(p.requests.length, 1)
  const q = panel(); q.instance.wxToken = ''; q.instance.submitBind()
  assert.equal(q.requests.length, 0)
})

test('approval input is masked and the longer sheet can scroll', () => {
  assert.match(source, /v-model="bindingApprovalToken"[^>]*type="password"/)
  assert.match(source, /max-height: 90vh; overflow-y: auto/)
  assert.doesNotMatch(source, /setStorageSync\([^\n]*bindingApprovalToken/)
})

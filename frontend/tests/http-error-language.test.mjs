import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const source = readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
const transport = source.slice(source.indexOf('function transportFailure('), source.indexOf('function markOffline('))
const raw = source.slice(source.indexOf('async function rawRequest('), source.indexOf('function newBrowserSessionId('))

for (const [method, code, message] of [
  ['GET', 503001, '数据加载失败，请稍后重试'],
  ['POST', 503002, '操作结果尚未确认，请刷新查看']
]) test(`${method}网络异常保留错误属性，文案不暴露开发词或伪报成功`, async () => {
  let calls = 0, sent
  const failure = new Error('connection lost')
  const environment = { isBackendOffline: () => false, canUseMockFallback: () => false,
    isWriteMethod: value => !['GET', 'HEAD', 'OPTIONS'].includes(value),
    state: { token: '' }, API_BASE_URL: '', API_PREFIX: '', REQUEST_TIMEOUT_MS: 1000,
    markOffline() {}, fetch: async (url, options) => { calls++; sent = options; throw failure } }
  const request = new Function(...Object.keys(environment), transport + raw + '; return rawRequest')(...Object.values(environment))
  await assert.rejects(request('/business', { method, body: { value: 7 }, headers: { 'Idempotency-Key': 'original-request' } }), error => {
    assert.equal(error.code, code)
    assert.equal(error.biz, true)
    assert.equal(error.cause, failure)
    assert.equal(error.message, message)
    assert.doesNotMatch(error.message, /mock|接口|生产环境/)
    return true
  })
  assert.equal(calls, 1)
  assert.equal(sent.headers['Idempotency-Key'], 'original-request')
  assert.equal(sent.body, JSON.stringify({ value: 7 }))
})

test('登录拒绝显示安全的凭据或验证码原因，仍保留认证失败属性且不重复提交', async () => {
  const code = source.slice(source.indexOf('export async function loginWithPassword('), source.indexOf('export async function request(')).replace('export ', '')
  for (const [bizCode, message] of [['UNAUTHORIZED', '账号、学校编码或密码不正确'], ['CAPTCHA_REQUIRED', '请输入图形验证码后继续']]) {
    let calls = 0
    const error = Object.assign(new Error('登录已失效，请重新登录'), { code: 401001, httpStatus: 401, bizCode, rawDeveloperDetail: message })
    const env = { clearOfflineState() {}, browserSessionHeaders: () => ({}), normalizeUiError,
      rawRequest: async () => { calls++; throw error }, _advanceSession: () => assert.fail('失败不得建立会话') }
    const login = new Function(...Object.keys(env), code + '; return loginWithPassword')(...Object.values(env))
    await assert.rejects(login('virtual', 'unused'), result => {
      assert.equal(result.message, message); assert.equal(result.httpStatus, 401); assert.equal(result.bizCode, bizCode); return true
    })
    assert.equal(calls, 1)
  }
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

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

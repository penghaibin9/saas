import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../../miniapp/src/services/sessionGeneration.mjs'

test('staff sensitive 401 neither refreshes nor redirects away from the read-only receipt', async () => {
  const source = readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
  const code = source.slice(source.indexOf('export async function request('), source.indexOf('export async function logoutRemote')).replace('export ', '')
  let sends = 0, refreshes = 0, redirects = 0, ensures = 0
  const env = { state: { token: 'old', sessionGeneration: 1 }, assertNoRoleSwitchTransition() {},
    ensureToken: async () => { ensures++ }, rawRequest: async () => { sends++; throw { biz: true, code: 401001 } },
    tryRefresh: async () => { refreshes++; return true }, _redirectToLogin: () => { redirects++ }, staleSessionError: () => Error('changed') }
  const request = new Function(...Object.keys(env), code + '; return request')(...Object.values(env))
  await assert.rejects(request('/auth/phone-binding/confirm', { noAuthRetry: true }))
  assert.equal(sends, 1); assert.equal(refreshes, 0); assert.equal(redirects, 0)
  ensures = 0
  await assert.rejects(request('/auth/phone-binding/operation-status', { auth: false, noAuthRetry: true }))
  assert.equal(ensures, 0)
})

test('student sensitive request retains original idempotency key and does not clear receipt context on 401', async () => {
  const source = readFileSync(new URL('../../student-portal/src/services/request.js', import.meta.url), 'utf8')
  const code = source.slice(source.indexOf('export async function request('), source.indexOf('export async function uploadFile(')).replace('export ', '')
  let sent, invalidated = 0
  const env = { sessionGeneration: 1, accessToken: 'old', getToken: () => 'old', cleanupStaleGraduationTemps() {},
    addInternshipBatchHeader() {}, addBrowserSessionHeader() {}, withQuery: path => path, browserAuthPath: path => path,
    browserAuthBody: (path, body) => body, API_BASE: '', API_PREFIX: '', responseJson: async res => res.json(),
    isUnauthorized: () => true, staleSessionError: () => Error('changed'), _invalidateIfCurrent: () => { invalidated++ },
    authError: text => Error(text), fetch: async (url, options) => { sent = options; return { status: 401, json: async () => ({ code: 401001 }) } } }
  const request = new Function(...Object.keys(env), code + '; return request')(...Object.values(env))
  await assert.rejects(request('/auth/phone-binding/confirm', { method: 'POST', body: { operationId: 'op' },
    noAuthRetry: true, headers: { 'Idempotency-Key': 'frozen-key' } }))
  assert.equal(sent.headers['Idempotency-Key'], 'frozen-key'); assert.equal(invalidated, 0)
})

test('student retry after a concurrent refresh preserves caller headers and retry policy', async () => {
  const source = readFileSync(new URL('../../student-portal/src/services/request.js', import.meta.url), 'utf8')
  const code = source.slice(source.indexOf('export async function request('), source.indexOf('export async function uploadFile(')).replace('export ', '')
  const sent = []
  let token = 'old'
  const env = { sessionGeneration: 1, get accessToken() { return token }, getToken: () => token,
    cleanupStaleGraduationTemps() {}, addInternshipBatchHeader() {}, addBrowserSessionHeader() {},
    withQuery: path => path, browserAuthPath: path => path, browserAuthBody: (path, body) => body,
    API_BASE: '', API_PREFIX: '', responseJson: async res => res.json(),
    isUnauthorized: (res) => res.status === 401, staleSessionError: () => Error('changed'),
    _invalidateIfCurrent() {}, authError: text => Error(text), refreshOnce: async () => {},
    fetch: async (url, options) => {
      sent.push(options)
      if (sent.length === 1) { token = 'new'; return { status: 401, json: async () => ({ code: 401001 }) } }
      return { status: 200, json: async () => ({ code: 0, data: { ok: true } }) }
    } }
  const request = new Function(...Object.keys(env), code + '; return request')(...Object.values(env))
  const result = await request('/business/write', { method: 'POST', body: { value: 1 },
    headers: { 'Idempotency-Key': 'business-key' }, noAuthRetry: false })
  assert.equal(result.ok, true)
  assert.equal(sent.length, 2)
  assert.equal(sent[1].headers['Idempotency-Key'], 'business-key')
})

test('mini original uni transport sends the same idempotency header without a second request', async () => {
  const source = readFileSync(new URL('../../miniapp/src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const sent = [], uni = { getStorageSync: key => key === 'gx_token_v1' ? 'synthetic-access' : '',
    request: options => { sent.push(options); options.success({ statusCode: 200, data: { code: 0, data: { accepted: true } } }) } }
  const request = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), source + '; return realRequest')(
    { apiBaseUrl: '', apiPrefix: '', requestTimeout: 1000 }, () => {}, uni, ...Object.values(generation))
  await request('/auth/phone-binding/confirm', { method: 'POST', data: { operationId: 'op' }, headers: { 'Idempotency-Key': 'frozen-key' } })
  assert.equal(sent.length, 1); assert.equal(sent[0].header['Idempotency-Key'], 'frozen-key')
})

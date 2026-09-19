import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

function setup({ manual = false } = {}) {
  const sent = []
  const storage = { gx_token_v1: 'isolated-test-access', gx_refresh_v1: 'isolated-test-refresh' }
  const requestSource = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const uni = {
    getStorageSync: key => storage[key] || '',
    setStorageSync: (key, value) => { storage[key] = value },
    request(options) { sent.push(options); if (!manual) options.success({ statusCode: 200, data: { code: 0, data: { items: [], total: 0 } } }) }
  }
  const realRequest = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${requestSource}\nreturn realRequest`)(
    { apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 }, () => {}, uni, ...Object.values(generation))
  const source = readFileSync(new URL('../src/services/affairsContractApi.js', import.meta.url), 'utf8')
    .replace(/^import .+$/gm, '').replace('export const', 'const').replace('export default affairsContractApi', 'return affairsContractApi')
  const api = new Function('realRequest', source)(realRequest)
  return { api, sent, storage, realRequest }
}

test('internship requests coalesce within a batch but never across batches', async () => {
  const { realRequest, sent, storage } = setup({ manual: true })
  storage.gx_student_internship_batch_v1 = '9007199254740993'
  const first = realRequest('/mobile/internship/plan')
  assert.equal(realRequest('/mobile/internship/plan'), first)
  storage.gx_student_internship_batch_v1 = '9007199254740995'
  const second = realRequest('/mobile/internship/plan')
  const count = sent.length
  for (const request of sent) request.success({ statusCode: 200, data: { code: 0, data: request.header['X-Internship-Batch-Id'] } })
  assert.deepEqual(await Promise.all([first, second]), ['9007199254740993', '9007199254740995'])
  assert.equal(count, 2)
})

test('internship mutation keeps its original batch through token refresh', async () => {
  const { realRequest, sent, storage } = setup({ manual: true })
  storage.gx_student_internship_batch_v1 = '11'
  const pending = realRequest('/mobile/internship/plan', { method: 'POST', data: { note: 'original batch' } })
  storage.gx_student_internship_batch_v1 = '22'
  sent[0].success({ statusCode: 401, data: { code: 401001 } })
  await new Promise(resolve => setImmediate(resolve))
  sent[1].success({ statusCode: 200, data: { code: 0, data: { accessToken: 'rotated-test-access', refreshToken: 'rotated-test-refresh' } } })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(sent.length, 3)
  sent[2].success({ statusCode: 200, data: { code: 0, data: { ok: true } } })
  await pending
  assert.equal(sent[2].header['X-Internship-Batch-Id'], '11')
})

test('unfiltered teacher materials omit empty integer context at the uni.request boundary', async () => {
  const { api, sent } = setup()
  await api.getMaterialRequirements('', 1, 20, { requirementId: undefined, bizId: '', bizType: null })
  assert.deepEqual(sent[0].data, { page: 1, pageSize: 20 })
  assert.equal(sent[0].method, 'GET')
})

test('exact application/material context and page survive without numeric coercion', async () => {
  const { api, sent } = setup()
  await api.getMaterialRequirements('RETURNED', 3, 20, { requirementId: '9007199254740993', bizType: 'FUNDING', bizId: '9007199254740995' })
  assert.deepEqual(sent[0].data, { status: 'RETURNED', page: 3, pageSize: 20, requirementId: '9007199254740993', bizType: 'FUNDING', bizId: '9007199254740995' })
})

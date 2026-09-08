import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

function setup() {
  const sent = []
  const requestSource = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const uni = {
    getStorageSync: key => key === 'gx_token_v1' ? 'isolated-test-access' : '',
    request(options) { sent.push(options); options.success({ statusCode: 200, data: { code: 0, data: { items: [], total: 0 } } }) }
  }
  const realRequest = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${requestSource}\nreturn realRequest`)(
    { apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 }, () => {}, uni, ...Object.values(generation))
  const source = readFileSync(new URL('../src/services/affairsContractApi.js', import.meta.url), 'utf8')
    .replace(/^import .+$/gm, '').replace('export const', 'const').replace('export default affairsContractApi', 'return affairsContractApi')
  const api = new Function('realRequest', source)(realRequest)
  return { api, sent }
}

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

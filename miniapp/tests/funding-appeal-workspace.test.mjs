import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
const source = fs.readFileSync(new URL('../src/pages/teacher/affairs-review/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
function make(api) {
  const component = new Function('teacherApi', 'affairsContractApi', 'affairsAppealApi', 'normalizeError', 'toast', script)({}, {}, api, () => ({}), () => {})
  const vm = { ...component.data(), ...component.methods, kind: 'FUNDING_APPEAL_REVIEW' }
  for (const [key, get] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => get.call(vm) })
  return vm
}
test('funding appeal queue sends page parameters and exposes only server-authorized actions', async () => {
  const calls = []
  const vm = make({ getPending: async (kind, params) => { calls.push([kind, params]); return { total: 21, items: [{ appealId: String(params.page), allowedActions: params.page === 1 ? ['REVIEW'] : [] }] } } })
  await vm.load(); await vm.loadMore()
  assert.deepEqual(calls.map(x => x[1].page), [1, 2])
  assert.equal(calls[0][0], 'FUNDING_APPEAL')
  assert.equal(vm.visibleAppealActions(vm.list[0]).length, 2)
  assert.equal(vm.visibleAppealActions(vm.list[1]).length, 0)
})
test('notification reads its exact funding appeal, including a closed result, without loading an unrelated queue', async () => {
  const vm = make({ getPending: () => assert.fail('must not replace exact record'), getFundingAppealDetail: async id => ({ appealId: id, status: 'CLOSED', resultLabel: '异议不成立', allowedActions: [] }) })
  vm.focusId = '201'; await vm.load()
  assert.equal(vm.list[0].appealId, '201'); assert.equal(vm.expandedId, '201')
  assert.equal(vm.visibleAppealActions(vm.list[0]).length, 0)
})



test('appeal paging reaches uni.request through the actual adapter and request implementation', async () => {
  const generation = await import('../src/services/sessionGeneration.mjs')
  const requestSource = fs.readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const sent = []
  const uni = { getStorageSync: key => key === 'gx_token_v1' ? 'test-access' : '', request: options => {
    sent.push(options); options.success({ statusCode: 200, data: { code: 0, data: { items: [], total: 41 } } })
  } }
  const realRequest = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), requestSource + '\nreturn realRequest')(
    { apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 }, () => {}, uni, ...Object.values(generation))
  const adapter = fs.readFileSync(new URL('../src/services/affairsAppealApi.js', import.meta.url), 'utf8')
    .replace(/^import .+$/gm, '').replace('export const', 'const').replace('export default affairsAppealApi', 'return affairsAppealApi')
  const api = new Function('realRequest', adapter)(realRequest)
  await api.getPending('FUNDING_APPEAL', { page: 2, pageSize: 20 })
  await api.getPending('AID_OBJECTION', { page: 3, pageSize: 20 })
  await api.getMyCreditAppeals(4, 20)
  assert.deepEqual(sent.map(x => x.data.page), [2, 3, 4])
  assert.ok(sent.every(x => x.method === 'GET' && x.data.pageSize === 20))
  assert.match(sent[0].url, /FUNDING_APPEAL$/)
})

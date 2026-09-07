import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = parse(fs.readFileSync(new URL('../src/pages/teacher/internship-volunteers/index.vue', import.meta.url), 'utf8')).descriptor.script.content.replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
function fixture(overrides = {}, allowed = true) {
  const calls = []; let modal
  const context = { load: async () => {}, can: () => allowed, selectedBatchId: 1, batches: [{ id: '1', name: '批次' }] }
  const api = { campaigns: async () => ({ items: [{ id: '2', status: 'OPEN', schoolConfirmStartAt: '2020-01-01T00:00:00Z', schoolConfirmEndAt: '2099-01-01T00:00:00Z' }] }), list: async () => ({ batchId: '1', items: [], total: 0 }), detail: async () => ({ id: '3', batchId: '1', campaignId: '2', status: 'SUBMITTED', version: 4, recordVersion: 5, recordStatus: 'PREPARING', eligibilityStatus: 'QUALIFIED', advisorUserId: '9', material: {}, volunteers: [{ id: '8', version: 6, currentSubmission: true, positionAvailable: true, status: 'PENDING_REVIEW', companyName: '企业', positionName: '岗位' }] }), confirm: async (...args) => calls.push(args), return: async (...args) => calls.push(args), ...overrides }
  const options = new Function('useInternshipContextStore', 'teacherVolunteerApi', 'openBusinessFile', 'uni', source)(() => context, api, async () => {}, { redirectTo: value => calls.push(value), showModal: value => { modal = value } })
  const page = options.data()
  for (const [key, fn] of Object.entries(options.methods)) page[key] = fn.bind(page)
  for (const [key, fn] of Object.entries(options.computed)) Object.defineProperty(page, key, { get: () => fn.call(page) })
  return { page, options, calls, context, modal: () => modal }
}
async function detail(f) { f.page.scope = { batchId: '1', campaignId: '2', groupId: '3', status: 'PENDING', keyword: '陈', page: 2 }; await f.page.load(); f.page.selectedId = '8' }

test('permission denial prevents recruitment data reads', async () => {
  const f = fixture({ campaigns: () => assert.fail('unauthorized request') }, false)
  await f.page.load(); assert.equal(f.page.state, 'forbidden')
})
test('explicit foreign batch and campaign never fall back to defaults', async () => {
  for (const scope of [{ batchId: '4' }, { batchId: '1', campaignId: '9' }]) {
    const f = fixture({ list: () => assert.fail('wrong scope') }); Object.assign(f.page.scope, scope)
    await f.page.load(); assert.equal(f.page.state, 'error')
  }
})
test('numeric default batch is normalized and exact detail scope is checked', async () => {
  const f = fixture(); await f.page.load(); assert.equal(f.page.state, 'ready'); assert.equal(f.page.scope.batchId, '1')
  const wrong = fixture({ detail: async () => ({ id: '3', batchId: '1', campaignId: '99' }) }); await detail(wrong)
  assert.equal(wrong.page.state, 'error'); assert.equal(wrong.page.detail, null)
})
test('malformed deep links fail before loading', () => {
  for (const query of [{ groupId: '3' }, { batchId: ['1', '2'] }, { campaignId: '-2' }]) {
    const f = fixture(); f.page.load = () => assert.fail('invalid entry'); f.page.applyQuery(query); assert.equal(f.page.state, 'error')
  }
})
test('return keeps original queue filters and page', async () => {
  const f = fixture(); await detail(f); f.page.returnToList()
  assert.match(f.calls[0].url, /batchId=1&campaignId=2&status=PENDING&keyword=%E9%99%88&page=2$/)
})
test('confirmation captures all versions and prevents duplicate modal submissions', async () => {
  const f = fixture(); await detail(f); assert.equal(f.page.confirmBlock, '')
  const pending = f.page.handle('confirm'); await f.page.handle('confirm'); f.page.detail.version = 999
  f.modal().success({ confirm: true }); await pending
  assert.equal(f.calls.length, 1); assert.deepEqual(f.calls[0][1], { expectedGroupVersion: 4, expectedRecordVersion: 5, applicationId: '8', expectedApplicationVersion: 6 })
})
test('route changes while modal is open cancel the old action', async () => {
  const f = fixture(); await detail(f); f.page.reason = '补充材料'; const pending = f.page.handle('return')
  f.options.onUnload.call(f.page); f.modal().success({ confirm: true }); await pending; assert.equal(f.calls.length, 0)
})
test('failed writes cannot be repeated until latest data is reloaded', async () => {
  const f = fixture({ return: async () => { throw new Error('版本冲突') } }); await detail(f); f.page.reason = '补充材料'
  const pending = f.page.handle('return'); f.modal().success({ confirm: true }); await pending
  assert.match(f.page.actionError, /版本冲突/); assert.equal(f.page.canHandle, false)
  await f.page.load(); assert.equal(f.page.canHandle, true)
})
test('school confirmation rejects missing evidence, advisor and expired windows', async () => {
  const f = fixture(); await detail(f)
  f.page.detail.material = null; assert.match(f.page.confirmBlock, /材料/)
  f.page.detail.material = {}; f.page.detail.advisorUserId = null; assert.match(f.page.confirmBlock, /教师/)
  f.page.detail.advisorUserId = '9'; f.page.campaigns[0].schoolConfirmEndAt = '2020-01-02T00:00:00Z'; assert.match(f.page.confirmBlock, /确认窗口/)
})
test('late requests cannot restore the previous student', async () => {
  let resolve; const f = fixture({ detail: () => new Promise(r => { resolve = r }) }); const pending = detail(f)
  await new Promise(r => setImmediate(r)); f.options.onUnload.call(f.page)
  resolve({ id: '3', batchId: '1', campaignId: '2' }); await pending; assert.equal(f.page.detail, null)
})

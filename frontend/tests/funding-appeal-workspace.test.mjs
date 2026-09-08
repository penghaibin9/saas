import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingAppealView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
function method(name, next) {
  const start = source.indexOf(`    async ${name}`), end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start)
  return source.slice(source.indexOf('{', start + `    async ${name}`.length) + 1, end).replace(/\n {4}\},$/, '')
}
const load = new AsyncFunction('studentAffairsApi', method('load()', 'setStatus'))
const review = new AsyncFunction('studentAffairsApi', 'toast', '{ reason }', method('submitReview({ reason })', 'typeLabel'))
function vm() { return { loadSeq: 0, focusId: '', appealStatus: 'CLOSED', publicityPage: { page: 2, pageSize: 10 }, appealPage: { page: 11, pageSize: 20 } } }
test('funding appeals use independent full pagination and do not misrepresent a failed query as empty', async () => {
  const target = vm(), calls = []
  const api = { getFundingApplications: async p => { calls.push(p); return { code: 0, data: { items: [], total: 305 } } }, getFundingAppeals: async p => { calls.push(p); return { code: 0, data: { items: [{ appealId: '201' }], total: 401 } } } }
  await load.call(target, api)
  assert.equal(target.publicityPage.total, 305); assert.equal(target.appealPage.total, 401)
  assert.equal(calls[0].page, 2); assert.equal(calls[1].page, 11)
  api.getFundingAppeals = async () => ({ code: 500, message: '服务暂不可用' })
  await load.call(target, api); assert.match(target.errorMessage, /服务暂不可用/)
})
test('a focused notification requests the exact appeal across all statuses', async () => {
  const target = vm(); target.focusId = '208'
  await load.call(target, { getFundingApplications: async () => ({ code: 0, data: { items: [], total: 0 } }), getFundingAppeals: async p => {
    assert.equal(p.appealId, '208'); assert.equal(p.status, ''); assert.equal(p.page, 1)
    return { code: 0, data: { items: [{ appealId: '208', status: 'CLOSED' }], total: 1 } } }
  })
  assert.equal(target.appeals[0].status, 'CLOSED')
})
test('review requires an explicit decision and sends the visible version only once', async () => {
  let finish; const calls = [], errors = []
  const target = { acting: '', revDlg: { visible: true, appealId: '7', result: '', version: 4 }, load: () => assert.fail('failed review must retain draft') }
  const api = { reviewFundingAppeal: (...args) => { calls.push(args); return new Promise(r => { finish = r }) } }, toast = { error: x => errors.push(x), success() {} }
  await review.call(target, api, toast, { reason: '核查意见已填写' }); assert.equal(calls.length, 0)
  target.revDlg.result = 'OVERRULED'
  const first = review.call(target, api, toast, { reason: '核查意见已填写' })
  await review.call(target, api, toast, { reason: '核查意见已填写' })
  assert.deepEqual(calls, [['7', 'OVERRULED', '核查意见已填写', 4]])
  finish({ code: 409, message: '请刷新核对' }); await first
  assert.equal(target.revDlg.visible, true); assert.equal(target.acting, '')
  assert.match(errors.at(-1), /刷新/)
})

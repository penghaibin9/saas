import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as volunteers from '../src/modules/internshipVolunteerModel.js'
import * as selection from '../src/modules/internshipSelectionModel.js'
import * as company from '../src/modules/internshipCompanyPublicModel.js'

const source = fs.readFileSync(new URL('../src/pages/student-internship/enterprises/index.vue', import.meta.url), 'utf8').split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm, '').replace('export default', 'return')
function fixture(api) {
  const deps = { ...volunteers, ...selection, ...company, normalizeMobileCatalogQuery: x => x, internshipSelectionApi: { forScope: () => api } }
  const options = new Function(...Object.keys(deps), source)(...Object.values(deps))
  const page = options.data()
  Object.assign(page, { contextState: 'ready', context: { catalogState: 'AVAILABLE', canSelect: true }, volunteerState: 'ready', group: { status: 'DRAFT', version: 1, slots: [] } })
  for (const [key, method] of Object.entries(options.methods)) page[key] = method.bind(page)
  for (const [key, getter] of Object.entries(options.computed)) Object.defineProperty(page, key, { get: () => getter.call(page) })
  return page
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test('old material preview cannot reopen confirmation in a different round', async () => {
  let resolve; const page = fixture({ materialPreview: () => new Promise(r => { resolve = r }) })
  page.prepareSubmit(); page.contextSeq++; page.volunteerBusy = false
  resolve({ previewHash: 'old', profileVersion: 1 }); await flush()
  assert.equal(page.confirmOpen, false); assert.equal(page.materialPreview.previewHash, '')
})
test('late failed withdrawal does not replace the new round error or busy state', async () => {
  let reject; const page = fixture({ withdrawVolunteers: () => new Promise((_, r) => { reject = r }) })
  page.withdrawVolunteers(); page.contextSeq++; page.volunteerError = '当前轮次提示'; page.volunteerBusy = true
  reject(new Error('旧轮次失败')); await flush()
  assert.equal(page.volunteerError, '当前轮次提示'); assert.equal(page.volunteerBusy, true)
})
test('late successful unlock does not reload an unrelated group', async () => {
  let resolve; const page = fixture({ requestUnlock: () => new Promise(r => { resolve = r }) })
  page.requestUnlock(); page.contextSeq++; page.loadVolunteers = () => assert.fail('wrong group reload')
  resolve({}); await flush()
})
test('failed completeness reload cannot retain a previous ready state', async () => {
  const page = fixture({ volunteers: async () => ({ status: 'DRAFT' }), profile: async () => { throw new Error('offline') }, profileCompleteness: async () => { throw new Error('offline') } })
  page.profile = { old: true }; page.profileCompleteness = { ready: true, percent: 100 }
  await page.loadVolunteers(); assert.equal(page.profile, null); assert.equal(page.profileCompleteness.ready, false)
})
test('starting a new context clears prior consent and frozen preview immediately', async () => {
  const page = fixture({ context: async () => { throw new Error('denied') } })
  page.confirmOpen = true; page.consentConfirmed = true; page.materialPreview = { previewHash: 'old' }; page.volunteerBusy = true
  const pending = page.loadContext()
  assert.equal(page.confirmOpen, false); assert.equal(page.consentConfirmed, false); assert.equal(page.volunteerBusy, false)
  await pending; assert.equal(page.contextState, 'error')
})

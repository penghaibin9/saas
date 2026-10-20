import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { formatDateTime } from '../src/utils/dateUtils.js'

function form(api = {}, fileSdk = {}, props = {}) {
  const source = parse(fs.readFileSync(new URL('../src/modules/internship/views/components/EnterpriseInspectionForm.vue', import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import.*$/gm, '').replace(/components:\s*\{[^}]*\},/, 'components: {},').replace('export default', 'return')
  const options = new Function('complianceApi', 'fileSdk', 'formatDateTime', 'window', source)(api, fileSdk, formatDateTime, {})
  const events = []
  const instance = { companyId: '1', companyName: '虚构企业', batchId: '23', record: null, canManage: true, ...props, $emit: (...args) => events.push(args) }
  Object.assign(instance, options.data.call(instance))
  for (const [key, method] of Object.entries(options.methods)) instance[key] = method.bind(instance)
  Object.defineProperty(instance, 'readonly', { get: () => options.computed.readonly.call(instance) })
  return { instance, events }
}
const ok = (data) => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { resolve, promise } }

test('inspection saves a draft with its company and batch and carries all evidence IDs', async () => {
  let body
  const { instance: page, events } = form({ createInspection: async value => { body = value; return ok({ id: '10' }) } })
  page.form.conclusion = '现场条件已核查'
  page.form.fileIds = ['5']
  page.files = [{ fileId: '5', readyForBusiness: true }]
  await page.save()
  assert.equal(body.companyId, '1')
  assert.equal(body.batchId, '23')
  assert.equal(body.conclusion, '现场条件已核查')
  assert.deepEqual(body.fileIds, ['5'])
  assert.deepEqual(events, [['saved', { id: '10' }]])
})

test('inspection conflicts preserve current fields and expose the latest record for explicit reload', async () => {
  let payload
  const original = { id: '8', status: 'DRAFT', version: 2, conclusion: '初稿' }
  const { instance: page, events } = form({
    updateInspection: async (id, body) => { payload = body; return { code: 409001, message: '版本已变化' } },
    listInspections: async () => ok([{ ...original, version: 3, status: 'SUBMITTED', statusLabel: '待审核', conclusion: '他人提交的结论' }])
  }, {}, { record: original })
  page.form.conclusion = '我的未保存结论'
  await page.save()
  assert.equal(payload.expectedVersion, 2)
  assert.equal(page.form.conclusion, '我的未保存结论')
  assert.equal(page.base.version, 2)
  assert.equal(page.latest.version, 3)
  assert.equal(events.length, 0)
  page.replaceWithLatest()
  assert.equal(page.form.conclusion, '他人提交的结论')
  assert.equal(page.readonly, true)
})

test('unscanned evidence and read-only records cannot be saved', async () => {
  let writes = 0
  const { instance: page } = form({ createInspection: async () => { writes++; return ok({}) } })
  page.form.fileIds = ['5']; page.files = [{ fileId: '5', readyForBusiness: false }]
  await page.save()
  assert.match(page.error, /安全检查/)
  assert.equal(writes, 0)
  page.files = []; page.base = { status: 'APPROVED' }
  await page.save()
  assert.equal(writes, 0)
})

test('a late file refresh does not reintroduce evidence removed from the draft', async () => {
  const old = deferred()
  const { instance: page } = form({}, { metadata: () => old.promise })
  page.form.fileIds = ['5']
  const pending = page.loadFiles()
  page.removeFile('5')
  await Promise.resolve()
  old.resolve({ fileId: '5', fileName: '旧附件' })
  await pending
  assert.deepEqual(page.form.fileIds, [])
  assert.deepEqual(page.files, [])
})

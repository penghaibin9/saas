import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(fileSdk) {
  const session = { generation: 1 }, events = []
  const context = vm.createContext({ fileSdk, currentSessionGeneration: () => session.generation })
  const source = readFileSync(new URL('../src/pages/student/academic-affairs/AcademicMaterials.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const page = { ...context.component.data(), files: [], purpose: 'AA_RECOGNITION', disabled: false, $emit: (name, value) => events.push([name, value]) }
  for (const [name, fn] of Object.entries(context.component.methods)) page[name] = fn.bind(page)
  return { page, events, session, component: context.component }
}

test('materials never let an old upload overwrite a replaced material scope', async () => {
  let release
  const { page, events } = mount({
    choose: async () => ({ path: 'local' }),
    upload: () => new Promise(resolve => { release = resolve })
  })
  const pending = page.add()
  await new Promise(setImmediate)
  page.files = [{ fileId: '31', readyForBusiness: true }]
  page.filesRevision += 1
  release({ fileId: '32', readyForBusiness: true })
  await pending
  assert.equal(events.filter(([name]) => name === 'update:files').length, 0)
  assert.equal(page.busy, false)
})

test('metadata cannot upgrade an unrelated or unverified file to a submit-ready candidate', async () => {
  const { page, events } = mount({ metadata: async () => ({ fileId: '42', readyForBusiness: true }) })
  page.files = [{ fileId: '41', readyForBusiness: false }]
  await page.refresh()
  assert.equal(events.filter(([name]) => name === 'update:files').length, 0)
  assert.match(page.errorText, /无法核对/)

  const invalid = mount({ choose: async () => ({ path: 'local' }), upload: async () => ({ fileId: 'temporary-reference', readyForBusiness: true }) })
  await invalid.page.add()
  assert.equal(invalid.events.filter(([name]) => name === 'update:files').length, 0)
  assert.match(invalid.page.errorText, /无法核对/)
})

test('material permission loss clears evidence, but a late 403 cannot clear a replacement scope', async () => {
  const denied = mount({ metadata: async () => { throw { httpStatus: 403 } } })
  denied.page.files = [{ fileId: '41', fileName: 'private.pdf', readyForBusiness: false }]
  await denied.page.refresh()
  assert.equal(denied.events.find(([name]) => name === 'update:files')[1].length, 0)
  assert.equal(denied.events.filter(([name]) => name === 'forbidden').length, 1)

  let reject
  const late = mount({ metadata: () => new Promise((_, fail) => { reject = fail }) })
  late.page.files = [{ fileId: '41', readyForBusiness: false }]
  const pending = late.page.refresh()
  late.page.files = [{ fileId: '42', readyForBusiness: true }]
  late.page.filesRevision++
  reject({ httpStatus: 403 })
  await pending
  assert.equal(late.events.filter(([name]) => name === 'update:files' || name === 'forbidden').length, 0)
})

test('uploading an existing file cannot add a duplicate material candidate', async () => {
  const { page, events } = mount({ choose: async () => ({ path: 'local' }), upload: async () => ({ fileId: '41', readyForBusiness: true }) })
  page.files = [{ fileId: '41', readyForBusiness: true }]
  await page.add()
  assert.equal(events.filter(([name]) => name === 'update:files').length, 0)
  assert.match(page.errorText, /重复/)
})

test('recognition and exemption submit only scanned, formal file IDs and keep their material scope disposable', () => {
  const recognition = readFileSync(new URL('../src/pages/student/academic-affairs/recognition.vue', import.meta.url), 'utf8')
  const makeup = readFileSync(new URL('../src/pages/student/academic-affairs/makeup.vue', import.meta.url), 'utf8')
  for (const source of [recognition, makeup]) {
    assert.match(source, /:key="materialScopeEpoch"/)
    assert.match(source, /new Set\(ids\)\.size === ids\.length/)
    assert.match(source, /file\?\.readyForBusiness === true/)
    assert.match(source, /materialScopeEpoch\+\+/)
  }
  assert.match(recognition, /attachmentFileIds: this\.materialIds/)
  assert.match(makeup, /body\.materialFileIds = this\.materialIds/)
  assert.match(makeup, /courseName: this\.selectedExemption\.courseName/)
  assert.doesNotMatch(makeup, /termCode: this\.(retakeForm|exForm)\.termCode/)
})

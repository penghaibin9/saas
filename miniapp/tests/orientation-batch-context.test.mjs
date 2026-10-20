import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function component(name, dependencies) {
  const source = readFileSync(new URL(`../src/pages/teacher/orientation/${name}/index.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'return')
  const options = new Function(...Object.keys(dependencies), script)(...Object.values(dependencies))
  return { page: { ...options.data(), ...options.methods }, options }
}

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('dashboard continues the same batch and optionally the selected student', () => {
  const paths = []
  const { page } = component('dashboard', { uni: { navigateTo: ({ url }) => paths.push(url) }, teacherApi: {}, normalizeError() {} })
  page.goWorklist()
  page.goGc()
  assert.equal(paths.length, 0, 'No current batch must not silently open all batches')
  page.d = { batchId: '9007199254740993', batchName: '2026迎新 · 批次甲' }
  page.goWorklist()
  page.goWorklist('9007199254740995')
  page.goGc()
  const listParams = new URLSearchParams(paths[0].split('?')[1])
  const studentParams = new URLSearchParams(paths[1].split('?')[1])
  assert.equal(listParams.get('batchId'), page.d.batchId)
  assert.equal(listParams.get('batchName'), page.d.batchName)
  assert.equal(listParams.has('orientationStudentId'), false)
  assert.equal(studentParams.get('batchId'), page.d.batchId)
  assert.equal(studentParams.get('orientationStudentId'), '9007199254740995')
  const greenParams = new URLSearchParams(paths[2].split('?')[1])
  assert.equal(greenParams.get('batchId'), page.d.batchId)
  assert.equal(greenParams.get('batchName'), page.d.batchName)
})

test('returning to dashboard rereads results and ignores a previous visit response', async () => {
  const requests = []
  const { page, options } = component('dashboard', {
    teacherApi: { getOrientationDashboard: () => { const next = deferred(); requests.push(next); return next.promise } },
    normalizeError: () => ({ pageState: 'error' }),
  })
  const old = options.onShow.call(page)
  options.onHide.call(page)
  const current = options.onShow.call(page)
  requests[1].resolve({ hasData: true, batchId: '18', notReportedTotal: 0 })
  await current
  requests[0].resolve({ hasData: true, batchId: '17', notReportedTotal: 2101 })
  await old
  assert.equal(page.d.batchId, '18')
  assert.equal(page.d.notReportedTotal, 0)
  const failed = page.load()
  assert.equal(page.d, null)
  requests[2].reject(new Error('读取失败'))
  await failed
  assert.equal(page.state, 'error')
  assert.equal(page.d, null)
})

function worklist(handler) {
  const calls = []
  const result = component('worklist', {
    realRequest: async (url, options) => { calls.push({ url, options }); return handler(url, options) },
    toast() {}, FilePreviewer: {}, decodeQueryText: value => decodeURIComponent(value || ''),
  })
  return { ...result, calls }
}

test('worklist opens the exact dashboard student and keeps batch through paging, search and returning to all', async () => {
  const { page, options, calls } = worklist(url => {
    if (url === '/orientation/qualifications') return { items: [{ id: '9007199254740995', name: '迎新同学' }], total: 1 }
    if (url === '/orientation/materials') return { items: [] }
    return { student: { version: 2 } }
  })
  options.onLoad.call(page, { batchId: '9007199254740993', batchName: encodeURIComponent('迎新批次甲'), orientationStudentId: '9007199254740995' })
  await page.load()
  assert.equal(page.batchName, '迎新批次甲')
  assert.equal(page.selected.id, '9007199254740995')
  assert.equal(calls[1].url, '/orientation/students/9007199254740995')
  assert.equal(calls[2].options.data.orientationStudentId, '9007199254740995')
  page.close()
  page.page = 2
  await page.load()
  page.keyword = '迎新'; page.filter = 'blocked'
  await page.search()
  assert.equal(page.selected, null, 'Refreshing the list must not reopen a closed sheet')
  for (const call of calls.filter(call => call.url === '/orientation/qualifications')) {
    assert.equal(call.options.data.batchId, '9007199254740993')
    assert.equal(call.options.data.orientationStudentId, '9007199254740995')
  }
  assert.equal(calls.at(-1).options.data.queue, 'blocked')
  await page.showAll()
  assert.equal(calls.at(-1).options.data.batchId, '9007199254740993')
  assert.equal(calls.at(-1).options.data.orientationStudentId, undefined)
  assert.equal(page.page, 1)
  assert.equal(page.keyword, '')
})

test('missing target never falls back to opening an unrelated student', async () => {
  const { page, options, calls } = worklist(() => ({ items: [], total: 0 }))
  options.onLoad.call(page, { batchId: '18', orientationStudentId: 'missing' })
  await page.load()
  assert.equal(calls.length, 1)
  assert.equal(page.selected, null)
  assert.equal(page.total, 0)
})

test('material review rechecks the same student inside the dashboard batch', async () => {
  const { page, options, calls } = worklist((url, request) => {
    if (request?.method === 'POST') return {}
    if (url === '/orientation/qualifications') return { items: [{ id: '25', canFinalize: true }] }
    if (url === '/orientation/materials') return { items: [] }
    return { student: { version: 8 } }
  })
  options.onLoad.call(page, { batchId: '18', orientationStudentId: '25' })
  page.canManage = true
  page.selected = { id: '25', canFinalize: false }
  page.detail = { student: { version: 7 } }
  await page.reviewMaterial({ id: '40', version: 3 }, 'approve')
  const read = calls.find(call => call.url === '/orientation/qualifications')
  assert.equal(read.options.data.batchId, '18')
  assert.equal(read.options.data.orientationStudentId, '25')
  assert.equal(page.selected.canFinalize, true)
  assert.equal(page.orientationStudentId, '25')
})

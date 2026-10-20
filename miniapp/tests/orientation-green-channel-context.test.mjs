import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function screen(handler) {
  const script = readFileSync(new URL('../src/pages/teacher/orientation/green-channel/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
  const calls = [], messages = []
  const dependencies = {
    realRequest: async (url, options) => { calls.push({ url, options }); return handler(url, options) },
    normalizeError: error => ({ pageState: String(error.code).startsWith('403') ? 'forbidden' : 'error' }),
    toast: message => messages.push(message), decodeQueryText: value => decodeURIComponent(value || ''), formatDateTime() {},
  }
  const options = new Function(...Object.keys(dependencies), script)(...Object.values(dependencies))
  return { options, page: { ...options.data(), ...options.methods }, calls, messages }
}

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const application = { id: '9007199254740995', version: 3, status: 'SUBMITTED', name: '虚构同学', applyType: 'TUITION_DEFERMENT' }

test('green queue retains the exact batch while switching pending/history and paging', async () => {
  const { page, options, calls } = screen(() => ({ list: [application], total: 65 }))
  options.onLoad.call(page, { batchId: '9007199254740993', batchName: encodeURIComponent('迎新甲批次') })
  await page.load()
  await page.turnPage(2)
  await page.changeQueue('all')
  assert.equal(page.batchName, '迎新甲批次')
  assert.equal(page.statusLabel('SUBMITTED', 'SUBMITTED'), '待审核')
  assert.equal(page.statusLabel('UNKNOWN', 'UNKNOWN'), '状态待确认')
  assert.equal(page.applyTypeLabel('UNKNOWN'), '申请类型待确认')
  assert.deepEqual(calls.map(call => call.options.data), [
    { batchId: '9007199254740993', page: 1, pageSize: 30, queue: 'pending' },
    { batchId: '9007199254740993', page: 2, pageSize: 30, queue: 'pending' },
    { batchId: '9007199254740993', page: 1, pageSize: 30, queue: 'all' },
  ])
})

test('stale queue responses never overwrite the current queue and failures do not become empty success', async () => {
  const requests = []
  const { page } = screen(() => { const request = deferred(); requests.push(request); return request.promise })
  const old = page.load()
  const current = page.changeQueue('all')
  requests[1].resolve({ list: [application], total: 1 }); await current
  requests[0].resolve({ list: [{ id: 'old' }], total: 10 }); await old
  assert.deepEqual(page.list, [application])
  const failed = page.load()
  assert.deepEqual(page.list, [])
  requests[2].reject(new Error('网络中断')); await failed
  assert.equal(page.state, 'error'); assert.equal(page.loadError, '网络中断')
  assert.deepEqual(page.list, [])
})

test('permission failure, readonly tenant and late identity responses cannot enable reviews', async () => {
  for (const context of [{ permissionPatterns: [] }, { permissionPatterns: ['*'], readonlyTenant: true }, { permissionPatterns: ['*'], moduleAccessHealthy: false }]) {
    const { page } = screen(() => context)
    await page.loadPermissions(); page.openReview(application, 'APPROVE')
    assert.equal(page.canManage, false); assert.equal(page.reviewDialog.visible, false)
  }
  const permission = deferred()
  const { page, options } = screen(() => permission.promise)
  const loading = page.loadPermissions(); options.onHide.call(page)
  permission.resolve({ permissionPatterns: ['studentAffairs.orientation.manage'] }); await loading
  assert.equal(page.canManage, false)
  const failed = screen(() => { throw new Error('身份读取失败') })
  await failed.page.loadPermissions(); assert.equal(failed.page.canManage, false)
})

test('review submits the displayed version once and rereads the same batch after success', async () => {
  const writing = deferred()
  const { page, options, calls, messages } = screen((url, request) => request?.method === 'POST' ? writing.promise : { list: [], total: 0 })
  options.onLoad.call(page, { batchId: '18' }); page.canManage = true
  const row = { ...application }; page.openReview(row, 'APPROVE'); row.version = 9
  const first = page.submitReview(); await page.submitReview()
  assert.equal(calls.length, 1); assert.equal(calls[0].options.data.expectedVersion, 3)
  assert.equal(page.acting, true)
  writing.resolve({}); await first
  assert.deepEqual(messages, ['已通过']); assert.equal(page.reviewDialog.visible, false)
  assert.equal(calls[1].options.data.batchId, '18'); assert.equal(page.acting, false)
})

test('conflict keeps comments and original version until the teacher deliberately refreshes and reopens', async () => {
  const { page, calls, messages } = screen((url, request) => {
    if (request?.method === 'POST') throw Object.assign(new Error('版本已变化'), { code: 40901 })
    return { list: [{ ...application, version: 4 }], total: 1 }
  })
  page.canManage = true; page.openReview(application, 'RETURN'); page.reviewDialog.comment = '请补充预计缴费日期'
  await page.submitReview()
  assert.equal(page.reviewDialog.visible, true); assert.equal(page.reviewDialog.conflicted, true)
  assert.equal(page.reviewDialog.target.version, 3); assert.equal(page.reviewDialog.comment, '请补充预计缴费日期')
  assert.deepEqual(messages, []); assert.equal(calls.length, 1)
  await page.submitReview(); assert.equal(calls.length, 1, 'Conflict must not resubmit automatically')
  await page.closeReview(); assert.equal(page.reviewDialog.visible, false)
  page.openReview(page.list[0], 'RETURN')
  assert.equal(page.reviewDialog.target.version, 4); assert.equal(page.reviewDialog.conflicted, false)
  assert.equal(page.reviewDialog.comment, '请补充预计缴费日期')
})

test('an empty last page returns to the valid page while keeping batch and queue', async () => {
  const { page, calls } = screen((url, request) => ({ list: request.data.page === 1 ? [application] : [], total: 1 }))
  page.batchId = '18'; page.queue = 'all'; page.page = 3
  await page.load()
  assert.equal(page.page, 1); assert.deepEqual(page.list, [application])
  assert.deepEqual(calls.map(call => call.options.data.page), [3, 1])
  assert.ok(calls.every(call => call.options.data.batchId === '18' && call.options.data.queue === 'all'))
})

test('leaving the page suppresses a late write receipt; insufficient reasons never submit', async () => {
  const writing = deferred()
  const { page, options, calls, messages } = screen(() => writing.promise)
  page.canManage = true; page.openReview(application, 'RETURN'); page.reviewDialog.comment = '太短'
  await page.submitReview(); assert.equal(calls.length, 0)
  page.reviewDialog.comment = '请补充预计缴费日期'; const saving = page.submitReview()
  options.onUnload.call(page); writing.resolve({}); await saving
  assert.deepEqual(messages, []); assert.equal(calls.length, 1)
})

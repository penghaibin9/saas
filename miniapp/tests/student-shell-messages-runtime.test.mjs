import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function setup() {
  let generation = 1
  const pending = [], reads = []
  const source = readFileSync(new URL('../src/pages/student/messages/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
  const context = { module: { exports: {} }, ensureStudentPerformanceApi() {}, fromNow() {}, deadlineText() {}, toast() {}, go() {}, messageModuleLabel() {},
    currentSessionGeneration: () => generation,
    studentApi: {
      getMessagesPage: (...args) => new Promise((resolve, reject) => pending.push({ args, resolve, reject })),
      markMessageRead: id => new Promise((resolve, reject) => reads.push({ id, resolve, reject }))
    }
  }
  vm.runInNewContext(source, context)
  const component = context.module.exports
  const page = { ...component.data(), _pageActive: true }
  for (const [key, method] of Object.entries(component.methods)) page[key] = method.bind(page)
  for (const [key, get] of Object.entries(component.computed)) Object.defineProperty(page, key, { get: () => get.call(page) })
  return { page, component, pending, reads, switchAccount: () => { generation++ } }
}
const result = id => ({ list: [{ id }], tabs: [], page: 1, hasMore: false })

test('message tabs deduplicate same request but reject late previous-tab responses', async () => {
  const { page, pending } = setup()
  const first = page.load()
  assert.equal(page.load(), first)
  page.tab = 'todo'
  const second = page.load()
  assert.equal(pending.length, 2)
  assert.deepEqual(pending[1].args, ['todo', 1, 20])
  pending[1].resolve(result('current')); await second
  pending[0].resolve(result('old')); await first
  assert.equal(page.list[0].id, 'current')
  assert.equal(page.data.groups.notice, undefined)
})

test('returning to messages reloads; hidden and prior-account replies cannot populate current page', async () => {
  const { page, component, pending, switchAccount } = setup()
  const old = page.load()
  component.onHide.call(page)
  switchAccount()
  component.onShow.call(page)
  const current = page._messagesPromise
  assert.equal(pending.length, 2)
  pending[0].resolve(result('student-A')); await old
  assert.equal(page.list.length, 0)
  pending[1].resolve(result('student-B')); await current
  assert.equal(page.list[0].id, 'student-B')
})

test('message request failure becomes retryable error, not empty success or unhandled rejection', async () => {
  const { page, pending } = setup()
  const request = page.load()
  pending[0].reject(new Error('network')); await request
  assert.equal(page.state, 'error')
  assert.equal(page._messagesPromise, null)
  const retry = page.load()
  pending[1].resolve(result('restored')); await retry
  assert.equal(page.state, 'ready')
})

test('mark-read does not complete business todo; failed notice read rolls back and can retry', async () => {
  const { page, reads } = setup()
  const todo = { id: '1', kind: 'TODO', read: false }
  page._markRead(todo)
  assert.equal(todo.read, false)
  assert.equal(reads.length, 0)
  const notice = { id: 'msg-2', kind: 'UNIFIED_MESSAGE', read: false }
  page.data.tabs = [{ key: 'notice', badge: 1 }]
  const request = page._markRead(notice)
  page._markRead(notice)
  assert.equal(reads.length, 1)
  reads[0].reject(new Error('network')); await request
  assert.equal(notice.read, false)
  assert.equal(page.noticeUnread, 1)
  const retry = page._markRead(notice)
  reads[1].resolve(); await retry
  assert.equal(notice.read, true)
  assert.equal(page.noticeUnread, 0)
})

test('a delayed read acknowledgement cannot subtract again from refreshed server counts', async () => {
  const { page, reads, pending } = setup()
  page.data.tabs = [{ key: 'notice', badge: 2 }]
  const read = page._markRead({ id: 'msg-2', kind: 'UNIFIED_MESSAGE', read: false })
  const refresh = page.load()
  pending[0].resolve({ ...result('fresh'), tabs: [{ key: 'notice', badge: 1 }] }); await refresh
  reads[0].resolve(); await read
  assert.equal(page.noticeUnread, 1)
})

test('a former-account request failure cannot put the current session into an error state', async () => {
  const { page, pending, switchAccount } = setup()
  const old = page.load()
  switchAccount(); page.state = 'ready'
  pending[0].reject(new Error('old account failure')); await old
  assert.equal(page.state, 'ready')
})

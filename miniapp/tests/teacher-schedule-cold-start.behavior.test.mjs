import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { setImmediate } from 'node:timers/promises'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function component(file, globals) {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.options =')
  const sandbox = { ...globals }
  vm.runInNewContext(source, sandbox)
  const page = sandbox.options.data()
  for (const [name, method] of Object.entries(sandbox.options.methods)) page[name] = method.bind(page)
  for (const [name, getter] of Object.entries(sandbox.options.computed || {})) {
    Object.defineProperty(page, name, { get: () => getter.call(page) })
  }
  for (const name of ['onLoad', 'onShow', 'onHide', 'onUnload']) {
    if (sandbox.options[name]) page[name] = sandbox.options[name].bind(page)
  }
  return page
}

function writeContract(storage) {
  const source = readFileSync(new URL('../src/pages/teacher/academic-affairs/write-result.js', import.meta.url), 'utf8')
    .replace(/export function/g, 'function').replace(/export const/g, 'const')
  const sandbox = { uni: storage }
  vm.runInNewContext(`${source}\nglobalThis.contract = { teacherWriteContext, listPersistentWrites, beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, persistWriteAck }`, sandbox)
  return sandbox.contract
}

function changePage({ session, me, teacherApi }) {
  const storage = new Map()
  const uni = {
    getStorageSync: key => storage.get(key) || '',
    setStorageSync: (key, value) => storage.set(key, value),
    showModal: options => options.success({ confirm: true })
  }
  return component('../src/pages/teacher/schedule-change/index.vue', {
    ...writeContract(uni), uni, teacherApi, me, useSessionStore: () => session,
    normalizeError: error => ({ pageState: error?.status === 403 ? 'forbidden' : 'error' }),
    toast() {}
  })
}

test('teacher schedule keeps server week six after selection and refresh', async () => {
  const weeks = []
  const session = { identity: { tenantId: '1', userId: '2', activeContextId: '3' }, currentRole: 'academic' }
  const page = component('../src/pages/teacher/my-schedule/index.vue', {
    useSessionStore: () => session, toast() {}, normalizeError: () => ({ pageState: 'error' }),
    teacherApi: { getMySchedule: async ({ week }) => {
      weeks.push(week)
      return { week: week || 5, currentWeek: 5, teachingWeeks: 18, termCode: '2026-1',
        termStartDate: '2026-09-01', todayItems: [], items: [], timeBands: [] }
    } }
  })
  page.onLoad()
  await page.load()
  assert.equal(page.selectedWeek, 5)
  await page.onWeekChange({ detail: { value: '5' } })
  assert.equal(page.selectedWeek, 6)
  assert.equal(page.weekPickerIndex, 5)
  await page.load()
  assert.equal(page.selectedWeek, 6)
  assert.equal(page.state, 'ready')
  assert.deepEqual(weeks, [undefined, 6, 6])
})

test('cold schedule-change deep link waits for verified teacher identity before reads and writes', async () => {
  const identityRead = deferred()
  const calls = { list: 0, schedule: 0, writes: 0 }
  const session = { identity: {}, realUser: null, currentRole: 'student', persistedIdentityVerified: false,
    applyRealUser(identity) {
      this.realUser = identity
      this.identity = { tenantId: identity.tenantId, userId: identity.userId, activeContextId: identity.activeContextId }
      this.currentRole = 'academic'; this.persistedIdentityVerified = true
    } }
  const page = changePage({ session, me: () => identityRead.promise, teacherApi: {
    getAcademicScheduleChanges: async () => { calls.list++; return { list: [], total: 0 } },
    getAcademicMySchedule: async () => { calls.schedule++; return { items: [{ itemId: '27', courseName: '测试课程' }] } },
    submitAcademicScheduleChange: async () => { calls.writes++; return { changeId: '1' } }
  } })
  page.onLoad({ scheduleItemId: '27' })
  page.onShow()
  assert.equal(page.tab, 'new')
  assert.equal(page.writeStorageBlocked, true)
  assert.deepEqual(calls, { list: 0, schedule: 0, writes: 0 })
  identityRead.resolve({ tenantId: '1', userId: '2', activeContextId: '3' })
  await setImmediate(); await setImmediate()
  assert.equal(page.state, 'ready')
  assert.equal(page.scheduleState, 'ready')
  assert.equal(page.currentItemId, '27')
  assert.equal(page.writeStorageBlocked, false)
  assert.deepEqual(calls, { list: 1, schedule: 1, writes: 0 })
})

test('failed identity recovery leaves schedule-change closed and retry can verify again', async () => {
  const session = { identity: {}, realUser: null, currentRole: 'student', persistedIdentityVerified: false,
    applyRealUser() { throw new Error('identity must not be applied after failure') } }
  let reads = 0, checks = 0
  const page = changePage({ session, me: async () => { checks++; throw { status: 403 } }, teacherApi: {
    getAcademicScheduleChanges: async () => { reads++; return { list: [] } },
    getAcademicMySchedule: async () => { reads++; return { items: [] } }
  } })
  page.onLoad({ scheduleItemId: '27' })
  await setImmediate()
  assert.equal(page.state, 'forbidden')
  assert.equal(page.writeStorageBlocked, true)
  assert.equal(reads, 0)
  await page.load()
  await setImmediate()
  assert.equal(checks, 2)
  assert.equal(reads, 0)
})

test('late old identity response cannot apply after a switch', async () => {
  const first = deferred()
  const session = { identity: {}, realUser: null, currentRole: 'student', persistedIdentityVerified: false,
    applyRealUser() { throw new Error('stale identity must not be applied') } }
  let reads = 0
  const page = changePage({ session, me: () => first.promise, teacherApi: {
    getAcademicScheduleChanges: async () => { reads++; return { list: [] } },
    getAcademicMySchedule: async () => { reads++; return { items: [] } }
  } })
  page.onLoad({ scheduleItemId: '27' })
  session.identity = { tenantId: '2', userId: 'new-user', activeContextId: '4' }
  first.resolve({ tenantId: '1', userId: 'old-user', activeContextId: '3' })
  await setImmediate()
  assert.equal(reads, 0)
  assert.equal(page.writeStorageBlocked, true)
  page.onHide()
  page.onShow()
  assert.equal(page.state, 'loading')
})

test('switching a verified teacher identity clears the previous schedule-change page', async () => {
  const session = { identity: { tenantId: '1', userId: 'A', activeContextId: '3' },
    realUser: { tenantId: '1' }, currentRole: 'academic', persistedIdentityVerified: true }
  let reads = 0
  const page = changePage({ session, me: async () => { throw new Error('already verified') }, teacherApi: {
    getAcademicScheduleChanges: async () => { reads++; return { list: [], total: 0 } },
    getAcademicMySchedule: async () => ({ items: [] })
  } })
  page.onLoad()
  await setImmediate()
  page.changes = [{ changeId: 'A1', reason: '甲的私有申请' }]
  session.identity = { tenantId: '1', userId: 'B', activeContextId: '4' }
  page.onHide()
  page.onShow()
  assert.equal(page.changes.length, 0)
  assert.equal(page.receipt, null)
  await setImmediate()
  assert.equal(page.state, 'ready')
  assert.equal(reads, 2)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(name, studentApi, confirm = async () => ({ confirm: true })) {
  const source = readFileSync(new URL(`../src/pages/student/academic-affairs/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  const context = { studentApi, readPending: () => null, savePending: () => true, createPendingCommand: (_scope, value) => ({ ...value, commandId: 'cmd-1', _pendingOwner: 'test-owner' }), canUpdatePendingCommand: () => true, currentSessionGeneration: () => 1, createSubmitLock: () => ({ run: fn => fn() }), normalizeError: e => ({ text: e.message }), toast() {}, modalConfirm: confirm, isUncertainWriteError: e => !e.biz, getStatusBarHeight: () => 20, go() {} }
  context.academicIcons = {}
  context.AcademicPageNav = {}; context.AcademicPageState = {}
  vm.runInNewContext(script, context)
  const page = context.component.data()
  for (const [name, fn] of Object.entries(context.component.methods)) page[name] = fn.bind(page)
  for (const [name, get] of Object.entries(context.component.computed || {})) Object.defineProperty(page, name, { get: () => get.call(page) })
  return { page, definition: context.component }
}

const batch = { batchId: 'b', options: [{ majorId: 'm1', majorName: '电气' }, { majorId: 'm2', majorName: '机械' }], maxChoices: 2 }
const result = (choices, volunteerId = 'v-1') => ({ openBatches: [batch], myVolunteers: choices ? [{ volunteerId, batchId: 'b', choices, status: 'SUBMITTED' }] : [] })
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }

test('major split keeps a matching readback pending when this command has no receipt', async () => {
  const pending = deferred()
  const { page } = mount('major-split', { submitMajorSplit: async () => null, getMyMajorSplit: () => pending.promise })
  page.d = result(); page.picks.b = ['m1', 'm2']; page.dirty.b = true
  const submit = page.submit(batch)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(page.notice.title, '结果待核实')
  pending.resolve(result(['m1', 'm2']))
  await submit
  assert.equal(page.notice.tone, 'warning')
  assert.equal(page.submitting, false)
  assert.ok(page.pending.b)
})

test('major split verifies the saved order only after its volunteer receipt arrives', async () => {
  const { page } = mount('major-split', {
    submitMajorSplit: async () => ({ volunteerId: 'v-1', batchId: 'b' }),
    getMyMajorSplit: async () => result(['m1', 'm2'], 'v-1')
  })
  page.d = result(); page.picks.b = ['m1', 'm2']; page.dirty.b = true
  await page.submit(batch)
  assert.equal(page.notice.tone, 'success')
  assert.equal(page.submitting, false)
  assert.equal(Object.keys(page.pending).length, 0)
})

test('major split mismatched or failed read never claims success or clears the draft', async () => {
  for (const fail of [false, true]) {
    const { page } = mount('major-split', { submitMajorSplit: async () => null, getMyMajorSplit: async () => { if (fail) throw Error('offline'); return result(['m2', 'm1']) } })
    page.d = result(); page.picks.b = ['m1', 'm2']; page.dirty.b = true
    await page.submit(batch)
    assert.equal(page.notice.title, '结果待核实')
    assert.equal(page.picks.b.join(','), 'm1,m2')
    assert.ok(page.pending.b)
  }
})

test('confirmation from a hidden page cannot send major split command', async () => {
  const answer = deferred()
  let writes = 0
  const { page, definition } = mount('major-split', { submitMajorSplit: async () => { writes += 1 } }, () => answer.promise)
  page.d = result(); page.picks.b = ['m1']
  const submit = page.submit(batch)
  definition.onHide.call(page)
  answer.resolve({ confirm: true }); await submit
  assert.equal(writes, 0)
})

test('home never converts failed reads or absence of registration batches into completion', async () => {
  const { page } = mount('index', {
    getMyExamSchedule: async () => { throw Error('offline') },
    getMyWarnings: async () => { throw Error('offline') },
    getMyRegistration: async () => { throw Error('offline') },
    getSelectionCourses: async () => { throw Error('offline') }
  })
  await page.loadPriority(0)
  assert.equal(page.registrationSummary, '暂时无法核对')
  assert.equal(page.selectionSummary, '暂时无法核对')
  assert.equal(page.todayEmptyText, '今日课表暂时无法核对')
  page.failedSources = []
  assert.equal(page.registrationSummary, '暂无注册批次')
  page.registrationBatches = [{ status: 'OPEN', registrationStatus: 'REGISTERED' }]
  assert.equal(page.registrationSummary, '当前已完成')
})


test('major split clears recovered read failure without discarding unsent choices', async () => {
  let offline = true
  const { page } = mount('major-split', { getMyMajorSplit: async () => { if (offline) throw Error('offline'); return result() } })
  page.picks.b = ['m2', 'm1']; page.dirty.b = true
  await page.load(); assert.equal(page.notice.title, '暂时无法更新')
  offline = false; await page.load()
  assert.equal(page.notice, null)
  assert.equal(page.picks.b.join(','), 'm2,m1')
})


test('home adds the official slot time without deriving a different Today schedule', async () => {
  const today = [{ itemId: 'today', slotNo: 2, courseName: '学校今日安排' }]
  const { page } = mount('index', { getMyAcadStatus: async () => ({}), getMySchedule: async () => ({ items: [{ itemId: 'other', slotNo: 1 }], todayItems: today, timeBands: [{ slotNo: 2, startTime: '10:10' }], todayDate: '2026-09-08', currentWeek: 2 }), getMyExamSchedule: async () => ({ items: [] }), getMyWarnings: async () => ({ items: [] }), getMyRegistration: async () => ({ batches: [] }), getSelectionCourses: async () => [] })
  await page.load()
  assert.equal(page.todayCourses.length, 1)
  assert.equal(page.todayCourses[0].itemId, 'today')
  assert.equal(page.todayCourses[0].startTime, '10:10')
  assert.equal(today[0].startTime, undefined)
})

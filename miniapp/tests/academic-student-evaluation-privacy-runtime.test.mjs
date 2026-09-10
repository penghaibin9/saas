import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mountEvaluation(studentApi) {
  const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)
  const session = { generation: 1 }
  const storage = new Map()
  const persistIdentity = () => storage.set('gx_session_v1', JSON.stringify({ logged: true, currentRole: 'student', identity: { tenantId: 'tenant-1', userId: 'user-1', roleCode: 'STUDENT', activeContextId: 'student-1', studentId: 'student-1' } }))
  persistIdentity()
  const context = vm.createContext({
    studentApi,
    currentSessionGeneration: () => session.generation,
    uni: { getStorageSync: key => storage.get(key) || '', setStorageSync: (key, value) => storage.set(key, value), removeStorageSync: key => storage.delete(key) },
    modalConfirm: async () => ({ confirm: true }),
    isUncertainWriteError: () => false,
    AcademicPageNav: {},
    AcademicPageState: {},
    safeToast() {},
    toast() {},
  })
  for (const helper of ['pending-ledger.js', 'read-page.js', 'application-page.js']) {
    const source = readFileSync(new URL(helper, directory), 'utf8')
      .replace(/^import .*$/gm, '')
      .replace(/export (const|function) /g, '$1 ')
    vm.runInContext(source, context)
  }
  const source = readFileSync(new URL('evaluation.vue', directory), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'component =')
  vm.runInContext(source, context)
  const layers = []
  function collect(component) { for (const mixin of component.mixins || []) collect(mixin); layers.push(component) }
  collect(context.component)
  const page = {}
  for (const layer of layers) Object.assign(page, layer.data?.call(page) || {})
  for (const layer of layers) for (const [key, fn] of Object.entries(layer.methods || {})) page[key] = fn.bind(page)
  for (const layer of layers) for (const [key, fn] of Object.entries(layer.computed || {})) Object.defineProperty(page, key, { get: () => fn.call(page) })
  layers.forEach(layer => layer.created?.call(page))
  return { page, session, pending: context.readPending, savePending: context.savePending, createPendingCommand: context.createPendingCommand }
}

test('evaluation clears the external anonymous-answer drawer and local drafts after a 403 reread', async () => {
  let forbidden = false
  const { page, pending, savePending, createPendingCommand } = mountEvaluation({
    getMyEvaluationTasks: async () => {
      if (forbidden) throw { httpStatus: 403, code: 'NO_PERMISSION', biz: true }
      return { list: [{ taskId: 'task-1', courseName: '电工技术', teacherName: '教师甲', canSubmit: true, submitted: false }] }
    },
  })

  await page.load()
  page.openSubmit(page.d.list[0])
  page.score = '91'
  page.comment = '仅本人的匿名评价草稿'
  page.drafts = { 'task-1': { score: '91', comment: page.comment } }
  page.pendingApplication = createPendingCommand('evaluation', { action: 'evaluation', title: '匿名提交私密标题', existingId: 'task-1', idKey: 'taskId', recordKey: 'taskId', receiptKey: 'taskId', recovery: { field: 'submitted', equals: true }, body: { taskId: 'task-1', objectiveScore: 91, comment: page.comment } })
  savePending('evaluation', page.pendingApplication)
  page.saveAcademicDraft()
  assert.ok(pending('evaluation'))
  assert.ok(pending('draft:evaluation'))

  forbidden = true
  await page.load()

  assert.equal(page.state, 'forbidden')
  assert.equal(page.d, null)
  assert.equal(page.active, null)
  assert.equal(page.score, '')
  assert.equal(page.comment, '')
  assert.equal(Object.keys(page.drafts).length, 0)
  assert.equal(page.pendingApplication, null)
  assert.equal(pending('evaluation').objectId, 'task-1')
  assert.equal(pending('evaluation').body, undefined)
  assert.doesNotMatch(JSON.stringify(pending('evaluation')), /私密标题|仅本人的匿名评价草稿/)
  forbidden = false
  await page.load()
  assert.ok(page.pendingApplication)
  page.openSubmit(page.d.list[0])
  assert.equal(page.active, null)
  assert.equal(pending('draft:evaluation'), null)
})

for (const changeIdentity of [false, true]) {
  test(`late 403 cannot clear a newer evaluation drawer (identity changed: ${changeIdentity})`, async () => {
    let rejectOld, reads = 0
    const old = new Promise((_resolve, reject) => { rejectOld = reject })
    const run = mountEvaluation({ getMyEvaluationTasks: () => ++reads === 1 ? old : Promise.resolve({ list: [{ taskId: 'new-task', canSubmit: true, submitted: false }] }) })
    const first = run.page.load()
    if (changeIdentity) run.session.generation++
    await run.page.load()
    run.page.openSubmit(run.page.d.list[0])
    run.page.score = '88'; run.page.comment = '新请求的草稿'
    rejectOld({ httpStatus: 403, code: 'NO_PERMISSION' })
    await first
    assert.equal(run.page.state, 'ready')
    assert.equal(run.page.active.taskId, 'new-task')
    assert.equal(run.page.comment, '新请求的草稿')
  })
}

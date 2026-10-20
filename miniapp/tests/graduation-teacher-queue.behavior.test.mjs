import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = path => fs.readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const stripImports = source => source.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
const queueSource = stripImports(read('services/graduationTeacherQueue.js')).replace('export function', 'function')
const pageRows = (page, total = 21) => {
  const rows = Array.from({ length: Math.min(20, total - (page - 1) * 20) }, (_, i) => ({ id: String((page - 1) * 20 + i + 1), gdStudentId: String((page - 1) * 20 + i + 1) }))
  rows._pageMeta = { page, total, hasMore: page * 20 < total }
  return rows
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function instance(def) {
  const vm = {}
  for (const part of [...(def.mixins || []), def]) {
    Object.assign(vm, part.data?.() || {})
    for (const [key, fn] of Object.entries(part.methods || {})) vm[key] = fn.bind(vm)
    for (const [key, fn] of Object.entries(part.computed || {})) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  }
  return vm
}
function queueFactory(api) { return new Function('graduationTeacherPagingApi', queueSource + '\nreturn graduationTeacherQueue')(api) }
function pageDef(path, dependencies) {
  const source = stripImports(read(path).match(/<script>([\s\S]*?)<\/script>/)[1]).replace('export default', 'return')
  return new Function(...Object.keys(dependencies), source)(...Object.values(dependencies))
}

for (const name of ['choices', 'changes', 'students', 'reviews', 'defenses']) {
  test(`${name}: record 21 is reachable by a second bounded request`, async () => {
    const calls = []
    const vm = instance(queueFactory({ [name]: async page => { calls.push(page); return pageRows(page) } })([name]))
    await vm.loadGraduationQueue(name)
    assert.equal(vm.graduationQueues[name].items.length, 20)
    assert.equal(vm.graduationQueues[name].total, 21)
    await vm.loadGraduationQueue(name, true)
    assert.deepEqual(calls, [1, 2])
    assert.equal(vm.graduationQueues[name].items[20].id, '21')
    assert.equal(vm.graduationQueues[name].hasMore, false)
  })
}

test('a failed second page retains rows and permits retry without skipping a page', async () => {
  let fail = true
  const vm = instance(queueFactory({ choices: async page => {
    if (page === 2 && fail) throw new Error('网络中断')
    return pageRows(page)
  } })(['choices']))
  await vm.loadGraduationQueue('choices'); await vm.loadGraduationQueue('choices', true)
  assert.equal(vm.graduationQueues.choices.items.length, 20)
  assert.equal(vm.graduationQueues.choices.page, 1)
  assert.equal(vm.graduationQueues.choices.error, '网络中断')
  fail = false; await vm.loadGraduationQueue('choices', true)
  assert.equal(vm.graduationQueues.choices.items.length, 21)
})

test('batch reset discards late pages and releases the new batch request', async () => {
  const old = deferred(); let calls = 0
  const vm = instance(queueFactory({ choices: async () => ++calls === 1 ? old.promise : pageRows(1, 1) })(['choices']))
  const pending = vm.loadGraduationQueue('choices')
  vm.resetGraduationQueues(); await vm.loadGraduationQueue('choices')
  old.resolve(pageRows(1)); await pending
  assert.equal(vm.graduationQueues.choices.items.length, 1)
  assert.equal(vm.graduationQueues.choices.loading, false)
})

test('duplicate load-more taps send one second-page request', async () => {
  const second = deferred(); let calls = 0
  const vm = instance(queueFactory({ choices: async page => { calls++; return page === 2 ? second.promise : pageRows(1) } })(['choices']))
  await vm.loadGraduationQueue('choices')
  const pending = vm.loadGraduationQueue('choices', true)
  await vm.loadGraduationQueue('choices', true)
  assert.equal(calls, 2); second.resolve(pageRows(2)); await pending
})

test('topic page exposes both second pages and rejects a modal from an old batch', async () => {
  let modal; let writes = 0
  const api = { choices: async p => pageRows(p), changes: async p => pageRows(p) }
  const vm = instance(pageDef('pages/teacher/graduation-topics/index.vue', {
    graduationTeacherQueue: queueFactory(api), toast() {},
    teacherApi: { reviewGraduationChoice: async () => { writes++ } },
    uni: { showModal: options => { modal = options.success } }
  }))
  await vm.load(); await vm.loadMore()
  assert.equal(vm.choices.length, 21)
  vm.switchTab('change'); await vm.loadMore(); assert.equal(vm.changes.length, 21)
  vm.reviewChoice(vm.choices[20], 'CONFIRM')
  await vm.load(); await modal({ confirm: true })
  assert.equal(writes, 0)
})

function scoreVm({ read = async () => pageRows(1), write = async () => ({}) } = {}) {
  const notices = []
  const vm = instance(pageDef('pages/teacher/defense-score/index.vue', {
    graduationTeacherPagingApi: { defenseScores: read },
    teacherApi: { submitGraduationDefenseScore: write },
    toast: message => notices.push(message), normalizeError: error => ({ text: error.message, pageState: 'error' })
  }))
  return { vm, notices }
}

test('defense scoring reaches student 21 and failed readback never claims completion', async () => {
  let fail = false
  const { vm, notices } = scoreVm({ read: async page => { if (fail) throw new Error('回读失败'); return pageRows(page) } })
  await vm.load(); await vm.loadMore(); assert.equal(vm.list.length, 21)
  const student = { gdStudentId: '21', studentName: '测试学生', myStatus: 'PENDING' }
  vm.drafts['21'] = { score: '85' }; fail = true
  vm.submit(student)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(vm.state, 'error')
  assert.equal(vm.actionReceipt.result, '最新队列读取失败')
  assert.ok(!notices.includes('评分已保存，服务器状态已回读'))
})

test('invalid and blank defense scores cannot be submitted as zero or NaN', () => {
  let writes = 0
  const { vm } = scoreVm({ write: async () => { writes++ } })
  for (const score of [' ', 'abc', 'NaN', 'Infinity', '-1', '101']) {
    vm.drafts['1'] = { score }; vm.submit({ gdStudentId: '1' })
  }
  assert.equal(writes, 0)
})

test('a score saved in the previous batch cannot create a receipt in the new batch', async () => {
  const saved = deferred()
  const { vm } = scoreVm({ write: () => saved.promise })
  vm.drafts['1'] = { score: '85' }
  vm.submit({ gdStudentId: '1' }); vm.onBatchReady()
  saved.resolve({}); await new Promise(resolve => setImmediate(resolve))
  assert.equal(vm.actionReceipt, null)
})

test('the guide retains loaded students while loading proposal and final queues independently', () => {
  let modal; let writes = 0
  const vm = instance(pageDef('pages/teacher/graduation-guide/index.vue', {
    graduationTeacherQueue: queueFactory({}), teacherApi: {}, graduationTeacherPagingApi: {},
    graduationTeacherCountTruth: async () => ({}), GRADUATION_TEACHER_PAGE_SIZE: 20,
    normalizeError: error => ({ text: error.message }), isStaleReadError: () => false,
    fileSdk: {}, FILE_STATUS_TEXT: {}, go() {}, toast() {}, uni: { showModal: options => { modal = options.success } }
  }))
  vm.data = { list: [{ id: '21' }], studentPage: 2, studentHasMore: false }
  vm.reviewQueue = [{ proposalId: '1' }]; vm.finalQueue = [{ finalId: '2' }]
  vm.applyReviewTruth({ list: [{ id: '1' }], studentTotal: 21, reviewQueue: [{ proposalId: '3' }], finalQueue: [{ finalId: '2' }] }, {
    appendProposal: true, appendFinal: true, preserveStudents: true
  })
  assert.equal(vm.data.list[0].id, '21')
  assert.deepEqual(vm.reviewQueue.map(row => row.proposalId), ['1', '3'])
  assert.deepEqual(vm.finalQueue.map(row => row.finalId), ['2'])
  vm._confirm('退回', '修改意见', 0, async () => { writes++ })
  vm.detailRequestEpoch++; modal({ confirm: true, content: '修改意见' })
  assert.equal(writes, 0)
})

test('taskbook issue selector loads student 21 and clears the selection on a batch change', async () => {
  const vm = instance(pageDef('pages/teacher/graduation-taskbook/index.vue', {
    graduationTeacherQueue: queueFactory({ students: async page => pageRows(page) }),
    teacherApi: {}, graduationTeacherPagingApi: { taskbooks: async () => ({ list: [] }) },
    GRADUATION_TEACHER_PAGE_SIZE: 20, createSubmitLock: () => ({}), normalizeError: () => ({}), toast() {}
  }))
  await vm.loadGraduationQueue('students'); await vm.loadGraduationQueue('students', true)
  vm.studentIndex = 20; assert.equal(vm.students[vm.studentIndex].gdStudentId, '21')
  vm.issueForm.content = '旧批次任务书'; vm.onBatchReady()
  assert.equal(vm.students.length, 0); assert.equal(vm.studentIndex, 0)
  assert.equal(vm.issueForm.content, '')
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(name, studentApi, confirm = async () => ({ confirm: true })) {
  const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)
  const session = { generation: 1 }
  const storage = new Map()
  let identityGeneration = session.generation
  const persistIdentity = () => storage.set('gx_session_v1', JSON.stringify({ logged: true, currentRole: 'student', identity: { tenantId: 'tenant-1', userId: 'user-' + identityGeneration, roleCode: 'STUDENT', activeContextId: 'student-' + identityGeneration, studentId: 'student-' + identityGeneration } }))
  persistIdentity()
  const currentSessionGeneration = () => {
    if (identityGeneration !== session.generation) { identityGeneration = session.generation; persistIdentity() }
    return session.generation
  }
  const uni = { getStorageSync: key => storage.get(key) || '', setStorageSync: (key, value) => storage.set(key, value), removeStorageSync: key => storage.delete(key) }
  const context = vm.createContext({ studentApi, uni, currentSessionGeneration,
    modalConfirm: confirm, isUncertainWriteError: e => !e?.biz, createSubmitLock: () => ({ run: fn => fn() }),
    AcademicPageNav: {}, AcademicPageState: {}, AcademicMaterials: {}, MobileAcademicDecisionCard: {}, safeToast() {}, toast() {}, go() {}, clampPercent: n => Math.max(0, Math.min(100, n)) })
  for (const helper of ['pending-ledger.js', 'read-page.js', 'application-page.js']) {
    const source = readFileSync(new URL(helper, directory), 'utf8').replace(/^import .*$/gm, '').replace(/export (const|function) /g, '$1 ')
    vm.runInContext(source, context)
  }
  const source = readFileSync(new URL(`${name}.vue`, directory), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const layers = []
  function collect(component) { for (const mixin of component.mixins || []) collect(mixin); layers.push(component) }
  collect(context.component)
  const reopen = () => {
    const page = {}
    for (const layer of layers) Object.assign(page, layer.data?.call(page) || {})
    for (const layer of layers) for (const [key, fn] of Object.entries(layer.methods || {})) page[key] = fn.bind(page)
    for (const layer of layers) for (const [key, fn] of Object.entries(layer.computed || {})) Object.defineProperty(page, key, { get: () => fn.call(page) })
    layers.forEach(layer => layer.created?.call(page))
    return page
  }
  const page = reopen()
  return { page, session, storage, reopen, hook: name => layers.forEach(layer => layer[name]?.call(page)), ledger: vm.runInContext('({ canUpdatePendingCommand, createPendingCommand, readPending, savePending })', context) }
}

const allowRecognition = (page, courseId = '1000000000000063602', courseName = '电工技术') => {
  page.courseOptions = [{ courseId, courseCode: 'KC-01', courseName, version: '2026版' }]
}

test('returned and excluded textbooks remain readable without a new receipt action', async () => {
  const { page } = mount('textbook', { getMyTextbook: async () => ({ distributions: [], fees: {} }) })
  assert.equal(page.statusText('RETURNED'), '已退领')
  assert.equal(page.statusText('EXCLUDED'), '当前不发放')
  for (const status of ['RETURNED', 'EXCLUDED', 'RECEIVED', 'UNKNOWN']) assert.equal(page.canSign({ status }), false)
})

test('recognition preserves draft after timeout and empty readback, and blocks a repeated command', async () => {
  let writes = 0
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: [] }), submitRecognition: async () => { writes++; throw Error('timeout') } })
  await page.load()
  Object.assign(page.form, { sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: '80' })
  allowRecognition(page)
  await page.submit(); await page.submit()
  assert.equal(writes, 1)
  assert.ok(page.pendingApplication)
  assert.match(page.applicationNotice, /结果待核实/)
  assert.equal(page.form.sourceCourseName, '电工基础')
})

test('recognition only clears form after its receipt and matching official record are read', async () => {
  let saved = false
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, status: 'SUBMITTED' }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: saved ? [record] : [] }), submitRecognition: async () => { saved = true; return { recognitionId: '2' } } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page)
  await page.submit()
  assert.equal(page.pendingApplication, null)
  assert.equal(page.form.sourceCourseName, '')
  assert.match(page.applicationNotice, /已核对学校受理记录/)
})

test('recognition keeps a matching new record pending when this command has no receipt', async () => {
  let saved = false, writes = 0
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, status: 'SUBMITTED' }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: saved ? [record] : [] }), submitRecognition: async () => { writes++; saved = true; return null } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page); await page.submit(); await page.submit()
  assert.ok(page.pendingApplication)
  assert.equal(writes, 1)
  assert.match(page.applicationNotice, /结果待核实/)
})

test('old recognition record does not count as confirmation of a new command', async () => {
  const record = { recognitionId: '1', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80 }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: [record] }), submitRecognition: async () => null })
  await page.load(); Object.assign(page.form, { ...record, sourceScore: '80' }); allowRecognition(page); await page.submit()
  assert.ok(page.pendingApplication)
})

test('recognition blocks unchecked materials and requires matching attachment readback', async () => {
  let writes = 0, sent
  const record = { recognitionId: '2', sourceCourseName: '电工基础', targetCourseName: '电工技术', targetCourseId: '1000000000000063602', sourceScore: 80, attachmentFileIds: [] }
  const { page } = mount('recognition', { getMyRecognition: async () => ({ items: writes ? [record] : [] }), submitRecognition: async body => { writes++; sent = body; return { recognitionId: '2' } } })
  await page.load(); Object.assign(page.form, { sourceCourseName: record.sourceCourseName, targetCourseName: record.targetCourseName, targetCourseId: record.targetCourseId, sourceScore: '80' })
  allowRecognition(page)
  page.materials = [{ fileId: '41', readyForBusiness: false }]
  await page.submit(); assert.equal(writes, 0)
  page.materials[0].readyForBusiness = true
  await page.submit(); assert.deepEqual(Array.from(sent.attachmentFileIds), ['41']); assert.ok(page.pendingApplication)
  record.attachmentFileIds = ['41']; await page.load()
  assert.equal(page.pendingApplication, null); assert.equal(page.materials.length, 0)
})

test('confirmation after identity switch sends no command; new load clears old application context', async () => {
  let answer, writes = 0
  const { page, session } = mount('recognition', { getMyRecognition: async () => ({ items: [] }), submitRecognition: async () => { writes++ } }, () => new Promise(resolve => { answer = resolve }))
  await page.load(); Object.assign(page.form, { sourceCourseName: '旧课程', targetCourseName: '目标课程', targetCourseId: '1000000000000063602', sourceScore: '80' })
  allowRecognition(page, '1000000000000063602', '目标课程')
  const pending = page.submit(); session.generation++; answer({ confirm: true }); await pending; await page.load()
  assert.equal(writes, 0); assert.equal(page.form.sourceCourseName, ''); assert.equal(page.pendingApplication, null)
})

test('read-only page ignores a late result from a previous identity', async () => {
  let resolve
  const { page, session } = mount('attendance', { getMyAttendance: () => new Promise(done => { resolve = done }) })
  const pending = page.load(); session.generation++; resolve({ items: [{ courseName: '旧身份课程' }], summary: {} }); await pending
  assert.equal(page.d, null)
})

test('malformed read is an error, not an empty successful academic list', async () => {
  const { page } = mount('credits', { getMyCredits: async () => ({ obtainedCredits: 12 }) })
  await page.load(); assert.equal(page.state, 'error'); assert.equal(page.d, null)
})

test('graduation decision content stays an object and hides technical evidence without changing formal status', () => {
  const { page } = mount('graduation', {})
  page.data = { hasAudit: false, overall: 'SYSTEM_PASSED', items: [{ item: 'CREDIT', result: 'PASS', evidence: 'SELECT * FROM student tenantId=7' }], decisionTrace: { availableResolutions: [{ label: 'SQL provider failure' }] }, decisionText: { title: 'provider exception', reason: 'tenantId=7', nextStep: '核对学校通知' } }
  assert.equal(typeof page.safeDecisionText, 'object')
  assert.equal(page.safeDecisionText.nextStep, '核对学校通知')
  assert.doesNotMatch(JSON.stringify(page.safeDecisionText) + JSON.stringify(page.safeDecisionTrace) + page.studentEvidence(page.items[0]), /SQL|tenantId|provider|SELECT/)
  assert.equal(page.formalText, '尚未纳入正式预审')
})

test('calendar month view uses actual date boundaries and only published events', () => {
  const { page } = mount('calendar', {})
  page.year = 2026; page.month = 8
  page.d = { events: [{ eventId: '1', startDate: '2026-09-12', endDate: '2026-09-12' }, { eventId: '2', startDate: '2026-10-01' }] }
  assert.equal(page.monthDays.filter(day => day.date).length, 30)
  assert.equal(page.visibleEvents.length, 1)
  page.selectedDate = '2026-09-11'; assert.equal(page.visibleEvents.length, 0)
  page.changeMonth(1); assert.equal(page.visibleEvents[0].eventId, '2')
})

test('registration sends requestedUntil through the existing adapter and confirms the exact date', async () => {
  const batch = { batchId: 'b', canDefer: true }
  let sent
  const { page } = mount('registration', { getMyRegistration: async () => ({ batches: [batch] }), deferRegistration: async (...args) => { sent = args; batch.deferral = { deferralId: 'd-other', reason: args[1], requestedUntil: '2026-09-19T00:00:00', status: 'PENDING' }; return { deferralId: 'd-1', batchId: 'b' } } })
  await page.load(); page.doDefer(batch); page.deferReason = '因病申请暂缓'
  await page.submitDefer(batch); assert.equal(sent, undefined)
  page.deferUntil = '2026-09-20'; await page.submitDefer(batch)
  assert.deepEqual(sent, ['b', '因病申请暂缓', '2026-09-20']); assert.ok(page.pendingApplication)
  batch.deferral.requestedUntil = '2026-09-20T00:00:00'; await page.load()
  assert.ok(page.pendingApplication)
  batch.deferral.deferralId = 'd-1'; await page.load()
  assert.equal(page.pendingApplication, null)
})

test('unsent recognition draft survives page recreation but never an identity switch', async () => {
  const { page, reopen, hook, session } = mount('recognition', { getMyRecognition: async () => ({ items: [] }) })
  await page.load(); page.form.sourceCourseName = '原课程'; page.showForm = true
  page.materials = [{ fileId: 'f', readyForBusiness: true }]; hook('onHide')
  const resumed = reopen(); await resumed.load()
  assert.equal(resumed.form.sourceCourseName, '原课程'); assert.equal(resumed.showForm, true)
  assert.equal(resumed.materials[0].readyForBusiness, false)
  session.generation++; const other = reopen(); await other.load()
  assert.equal(other.form.sourceCourseName, ''); assert.equal(other.materials.length, 0)
})

test('recheck draft restores by stable grade id after records change their order', async () => {
  const grades = [{ gradeId: 'a', courseName: '甲课', score: 70 }, { gradeId: 'b', courseName: '乙课', score: 60 }]
  const { page, reopen, hook } = mount('recheck', { getMyRecheck: async () => ({ items: [] }), getMyTranscript: async () => ({ items: grades }) })
  await page.load(); page.picked = 1; page.reason = '核对平时成绩'; page.showForm = true; hook('onHide')
  grades.reverse(); const resumed = reopen(); await resumed.load()
  assert.equal(resumed.grades[resumed.picked].gradeId, 'b'); assert.equal(resumed.reason, '核对平时成绩')
})

test('403 read is restricted, not empty or a generic transient error', async () => {
  const { page } = mount('credits', { getMyCredits: async () => { throw { httpStatus: 403, code: 403001, biz: true } } })
  await page.load(); assert.equal(page.state, 'forbidden')
})

test('textbook and level registration require the explicit object acknowledgement', async () => {
  let writes = 0
  const book = { recordId: 'r', textbookName: '教材', status: 'PENDING' }
  const { page: textbook } = mount('textbook', { getMyTextbook: async () => ({ distributions: [book], fees: {} }), signTextbook: async () => { writes++ } })
  await textbook.load(); textbook.openSign(book); await textbook.sign(book)
  const exam = { examId: 'e', examName: '普通话' }
  const { page: level } = mount('level-exam', { getMyLevelExam: async () => ({ openExams: [exam], myRegs: [] }), registerLevelExam: async () => { writes++ } })
  await level.load(); level.openDetail(exam); await level.register(exam)
  assert.equal(writes, 0); assert.equal(level.feeText(null), '缴费状态待核对')
})

for (const kind of ['registration', 'textbook', 'evaluation', 'level-exam']) {
  test(`${kind}: successful transport with unchanged readback remains unconfirmed`, async () => {
    const cases = {
      registration: { api: { getMyRegistration: async () => ({ batches: [{ batchId: 'b', canRegister: true, registrationStatus: 'PENDING' }] }), registerSelf: async () => null }, run: page => page.doRegister(page.d.batches[0]) },
      textbook: { api: { getMyTextbook: async () => ({ distributions: [{ recordId: 'r', textbookName: '电工基础', status: 'PENDING' }], fees: {} }), signTextbook: async () => null }, run: page => { page.openSign(page.d.distributions[0]); page.received = true; return page.sign(page.d.distributions[0]) } },
      evaluation: { api: { getMyEvaluationTasks: async () => ({ list: [{ taskId: 't', courseName: '电工技术', canSubmit: true, submitted: false }] }), submitEvaluation: async () => null }, run: page => { page.openSubmit(page.d.list[0]); page.score = '85'; return page.submit() } },
      'level-exam': { api: { getMyLevelExam: async () => ({ openExams: [{ examId: 'e', examName: '普通话' }], myRegs: [] }), registerLevelExam: async () => null }, run: page => { page.openDetail(page.d.openExams[0]); page.confirmed = true; return page.register(page.d.openExams[0]) } }
    }
    const sample = cases[kind]
    const { page } = mount(kind, sample.api)
    await page.load(); await sample.run(page)
    assert.ok(page.pendingApplication)
    assert.match(page.applicationNotice, /结果待核实/)
  })
}


test('makeup restores unsent drafts by stable candidate and blocks removed candidates', async () => {
  let writes = 0
  const options = { retakeOptions: [{ gradeId: 'g1', courseName: '课程甲' }], exemptionOptions: [{ courseId: 'c1', courseName: '课程乙' }] }
  const run = mount('makeup', { getMyMakeup: async () => ({ retakes: [], exemptions: [] }), getMakeupOptions: async () => options, applyRetake: async () => { writes++ }, applyExemption: async () => { writes++ } })
  await run.page.load()
  run.page.retakeForm.reason = '保留重修说明'
  run.page.exForm.reason = '保留免修说明'
  run.hook('onHide')
  options.retakeOptions = []; options.exemptionOptions = []
  const restored = run.reopen(); await restored.load()
  assert.equal(restored.retakeForm.reason, '保留重修说明')
  assert.equal(restored.exForm.reason, '保留免修说明')
  assert.equal(restored.retakeAvailable, false)
  assert.equal(restored.exemptionAvailable, false)
  await restored.submitRetake(); await restored.submitExemption()
  assert.equal(writes, 0)
})


test('recognition name-only draft never sends an invalid request or substitutes a manual internal ID', async () => {
  let writes=0
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:[]}),submitRecognition:async()=>{writes++}})
  await page.load();Object.assign(page.form,{sourceCourseName:'原课程',targetCourseName:'手填同名课程',sourceScore:'80'})
  await page.submit();assert.equal(writes,0);assert.equal(page.canSubmit,false);assert.equal(page.form.sourceCourseName,'原课程')
  const src=readFileSync(new URL('../src/pages/student/academic-affairs/recognition.vue',import.meta.url),'utf8')
  assert.doesNotMatch(src,/<input[^>]*v-model="form.targetCourse(Name|Id)"/)
})
test('recognition sends exact string target ID and does not accept adjacent ID with same name', async () => {
  let body,writes=0
  const target='1000000000000063602'
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:writes?[{recognitionId:'NEW',sourceCourseName:'原课程',targetCourseName:'同名课程',targetCourseId:'1000000000000063603',sourceScore:80}]:[]}),submitRecognition:async value=>{body=value;writes++;return {recognitionId:'NEW'}}})
  await page.load();allowRecognition(page,target,'同名课程');Object.assign(page.form,{sourceCourseName:'原课程',targetCourseName:'同名课程',targetCourseId:target,sourceScore:'80'});await page.submit()
  assert.equal(body.targetCourseId,target);assert.equal(body.targetCourseName,'同名课程');assert.ok(page.pendingApplication)
})
test('recognition course options keep string IDs, paginate and ignore stale identity results', async () => {
  const calls=[]
  const {page}=mount('recognition',{getMyRecognition:async()=>({items:[]}),getRecognitionCourses:async q=>{calls.push(q);return {items:[{courseId:q.page===1?'1000000000000063602':'1000000000000063603',courseCode:`KC-${q.page}`,courseName:`课程${q.page}`,version:'2026版'}],total:21}}})
  await page.loadRecognitionCourses(false);await page.loadRecognitionCourses(true);assert.deepEqual(calls.map(q=>[q.page,q.pageSize]),[[1,20],[2,20]]);assert.equal(JSON.stringify(page.courseOptions.map(row=>row.courseId)),JSON.stringify(['1000000000000063602','1000000000000063603']))
  page.selectCourse(page.courseOptions[1]);assert.equal(page.form.targetCourseId,'1000000000000063603');assert.equal(typeof page.form.targetCourseId,'string')
  let release;const late=mount('recognition',{getRecognitionCourses:()=>new Promise(resolve=>{release=resolve})});const pending=late.page.loadRecognitionCourses(false);late.session.generation++;release({items:[{courseId:'9',courseName:'旧身份课程'}],total:1});await pending;assert.equal(late.page.courseOptions.length,0)
})
test('clearance only releases FINISHED formal score, preserving zero and hiding SCORED values', async () => {
  const {page}=mount('clearance',{getMyClearance:async()=>({items:[]})})
  assert.equal(page.resultLabel({status:'SCORED',score:88}),'待公布成绩');assert.equal(page.publishedScore({status:'SCORED',score:88}),'待公布或核对')
  assert.equal(page.resultLabel({status:'FINISHED',score:60}),'已公布成绩');assert.equal(page.publishedScore({status:'FINISHED',score:60}),60)
  assert.equal(page.publishedScore({status:'FINISHED',score:0}),0);assert.equal(page.resultLabel({status:'FINISHED',score:null}),'已结束，成绩待核对')
  assert.equal(page.publishedScore({status:'PUBLISHED',score:88}),'待公布或核对');assert.equal(page.resultLabel({status:'PASSED'}),'结果待核对')
})

for (const kind of ['retake', 'exemption']) {
  test(`${kind}: missing original ACK stays pending even when one new same-source record appears`, async () => {
    let writes = 0
    const idKey = kind === 'retake' ? 'applyId' : 'exemptionId'
    const row = { [idKey]: '9007199254740993', originGradeId: '101', course: { id: '201' } }
    const api = {
      getMyMakeup: async () => ({ retakes: kind === 'retake' && writes ? [row] : [], exemptions: kind === 'exemption' && writes ? [row] : [] }),
      getMakeupOptions: async () => ({ retakeOptions: [{ gradeId: '101' }], exemptionOptions: [{ courseId: '201' }] }),
      applyRetake: async () => { writes++; throw Error('timeout') },
      applyExemption: async () => { writes++; throw Error('timeout') }
    }
    const run = mount('makeup', api)
    await run.page.load()
    await run.page[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.ok(run.page.pendingApplication)
    assert.match(run.page.applicationNotice, /结果待核实/)
    const reopened = run.reopen(); await reopened.load()
    await reopened[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.equal(writes, 1)
    assert.ok(reopened.pendingApplication)
  })

  test(`${kind}: original ACK must also match the original source before clearing the draft`, async () => {
    let writes = 0
    const idKey = kind === 'retake' ? 'applyId' : 'exemptionId'
    const row = { [idKey]: '9007199254740993', originGradeId: '102', course: { id: '202' } }
    const api = {
      getMyMakeup: async () => ({ retakes: kind === 'retake' && writes ? [row] : [], exemptions: kind === 'exemption' && writes ? [row] : [] }),
      getMakeupOptions: async () => ({ retakeOptions: [{ gradeId: '101' }], exemptionOptions: [{ courseId: '201' }] }),
      applyRetake: async () => { writes++; return { [idKey]: row[idKey] } },
      applyExemption: async () => { writes++; return { [idKey]: row[idKey] } }
    }
    const { page } = mount('makeup', api)
    await page.load()
    const form = kind === 'retake' ? page.retakeForm : page.exForm
    form.reason = '保留原申请说明'
    await page[kind === 'retake' ? 'submitRetake' : 'submitExemption']()
    assert.ok(page.pendingApplication)
    assert.equal(form.reason, '保留原申请说明')
    row.originGradeId = '101'; row.course.id = '201'
    await page.load()
    assert.equal(page.pendingApplication, null)
    assert.equal((kind === 'retake' ? page.retakeForm : page.exForm).reason, '')
    assert.equal(writes, 1)
  })
}

test('major split keeps the command pending when a matching record lacks this command receipt', async () => {
  let writes = 0, saved = false
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const volunteer = { volunteerId: 'v-1', batchId: 'b-1', choices: ['m-1'], status: 'SUBMITTED' }
  const { page } = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: saved ? [volunteer] : [] }),
    submitMajorSplit: async () => { writes++; saved = true; return null }
  })
  await page.load(); page.picks = { 'b-1': ['m-1'] }
  await page.submit(batch); await page.submit(batch)
  assert.equal(writes, 1)
  const command = JSON.parse(JSON.stringify(page.pending['b-1']))
  assert.deepEqual({ choices: command.choices, volunteerId: command.volunteerId, batchId: command.batchId }, { choices: ['m-1'], volunteerId: '', batchId: 'b-1' })
  assert.ok(command.commandId)
  assert.match(page.notice.description, /不要重复提交/)
})

test('major split clears only when its volunteer receipt, batch and ordered choices match', async () => {
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const volunteer = { volunteerId: 'v-1', batchId: 'b-1', choices: ['m-1'], status: 'SUBMITTED' }
  const { page } = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [volunteer] }),
    submitMajorSplit: async () => ({ volunteerId: 'v-other', batchId: 'b-1' })
  })
  await page.load(); page.picks = { 'b-1': ['m-1'] }
  await page.submit(batch)
  assert.ok(page.pending['b-1'])
  const exact = mount('major-split', {
    getMyMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [volunteer] }),
    submitMajorSplit: async () => ({ volunteerId: 'v-1', batchId: 'b-1' })
  })
  await exact.page.load(); exact.page.picks = { 'b-1': ['m-1'] }
  await exact.page.submit(batch)
  assert.equal(exact.page.pending['b-1'], undefined)
  assert.equal(exact.page.dirty['b-1'], false)
  assert.equal(exact.page.notice.title, '志愿记录已确认')
})

test('major split 403 clears visible information while preserving the pending command', async () => {
  let denied = false
  const batch = { batchId: 'b-1', batchName: '2026 专业分流', maxChoices: 2, options: [{ majorId: 'm-1', majorName: '机电一体化' }] }
  const { page, ledger } = mount('major-split', { getMyMajorSplit: async () => {
    if (denied) throw { httpStatus: 403, code: 403001, biz: true }
    return { openBatches: [batch], myVolunteers: [] }
  } })
  await page.load()
  const pending = ledger.createPendingCommand('major-split', { action: 'MAJOR_SPLIT_SUBMIT', choices: ['m-1'], volunteerId: '', batchId: 'b-1' })
  ledger.savePending('major-split', { 'b-1': pending })
  page.picks = { 'b-1': ['m-1'] }; page.dirty = { 'b-1': true }; page.activeBatchId = 'b-1'
  denied = true; await page.load()
  assert.equal(page.state, 'forbidden')
  assert.equal(page.d, null)
  assert.deepEqual(JSON.parse(JSON.stringify(page.picks)), {})
  assert.equal(page.activeBatchId, '')
  assert.ok(page.pending['b-1'])
})

test('major split ignores a delayed old 403 after a newer successful read', async () => {
  let rejectOld, calls = 0
  const batch = { batchId: 'new', batchName: '当前批次', maxChoices: 1, options: [] }
  const { page } = mount('major-split', { getMyMajorSplit: () => {
    calls++
    return calls === 1 ? new Promise((_, reject) => { rejectOld = reject }) : Promise.resolve({ openBatches: [batch], myVolunteers: [] })
  } })
  const oldRead = page.load()
  await page.load()
  rejectOld({ httpStatus: 403, code: 403001, biz: true })
  await oldRead
  assert.equal(page.state, 'ready')
  assert.equal(page.d.openBatches[0].batchId, 'new')
})

const privacyCases = [
  {
    name: 'recognition', scope: 'recognition', payload: { body: {} }, api: denied => ({ getMyRecognition: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [] }) }),
    prepare: page => { page.form.sourceCourseName = '敏感原课程' }, scrubbed: page => page.form.sourceCourseName === ''
  },
  {
    name: 'recheck', scope: 'recheck', payload: { body: { acadGradeId: 'g-1', reason: '敏感复查理由' } }, api: denied => ({ getMyRecheck: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [] }), getMyTranscript: async () => ({ items: [{ gradeId: 'g-1', courseName: '课程' }] }) }),
    prepare: page => { page.reason = '敏感复查理由'; page.grades = [{ gradeId: 'g-1' }] }, scrubbed: page => page.reason === '' && page.grades.length === 0
  },
  {
    name: 'exam', scope: 'exam', payload: { body: { examCourseId: 'e-1', reason: '敏感缓考理由' } }, api: denied => ({ getMyExamSchedule: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ items: [] }), getMyDeferOptions: async () => ({ items: [] }), getMyDeferrals: async () => ({ items: [] }) }),
    prepare: page => { page.form.reason = '敏感缓考理由'; page.selectedCourse = { examCourseId: 'e-1' } }, scrubbed: page => page.form.reason === '' && page.selectedCourse === null
  },
  {
    name: 'registration', scope: 'registration', payload: { kind: 'defer', body: { batchId: 'b-1', reason: '敏感暂缓理由', requestedUntil: '2026-09-20' } }, api: denied => ({ getMyRegistration: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ batches: [] }) }),
    prepare: page => { page.deferReason = '敏感暂缓理由'; page.deferUntil = '2026-09-20' }, scrubbed: page => page.deferReason === '' && page.deferUntil === ''
  },
  {
    name: 'textbook', scope: 'textbook', payload: { body: { recordId: 'r-1' } }, api: denied => ({ getMyTextbook: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ distributions: [], fees: {} }) }),
    prepare: page => { page.signingId = 'r-1'; page.received = true }, scrubbed: page => page.signingId === '' && page.received === false
  },
  {
    name: 'level-exam', scope: 'level-exam', payload: { body: { examId: 'l-1' } }, api: denied => ({ getMyLevelExam: async () => denied() ? Promise.reject({ httpStatus: 403, code: 403001 }) : ({ openExams: [], myRegs: [] }) }),
    prepare: page => { page.detailId = 'l-1'; page.confirmed = true }, scrubbed: page => page.detailId === '' && page.confirmed === false
  }
]

for (const sample of privacyCases) {
  test(`${sample.name}: a current 403 removes visible academic data but retains the command reference`, async () => {
    let denied = false
    const { page, ledger } = mount(sample.name, sample.api(() => denied))
    await page.load(); sample.prepare(page)
    const pending = ledger.createPendingCommand(sample.scope, { action: sample.scope, title: '本次办理', ...sample.payload, returnedId: '', knownIds: [], idKey: 'id' })
    ledger.savePending(sample.scope, pending)
    denied = true; await page.load()
    assert.equal(page.state, 'forbidden')
    assert.equal(page.d, null)
    assert.ok(page.pendingApplication)
    assert.ok(sample.scrubbed(page))
  })
}

test('registration cannot manufacture a current batch ACK from a different server batch', async () => {
  let writes = 0
  const batch = { batchId: '101', canRegister: true, registrationStatus: 'PENDING' }
  const { page } = mount('registration', {
    getMyRegistration: async () => ({ batches: [batch] }),
    registerSelf: async () => { writes++; batch.registrationStatus = 'REGISTERED'; return { registrationId: '901', batchId: '102' } }
  })
  await page.load(); await page.doRegister(batch)
  assert.ok(page.pendingApplication)
  assert.equal(page.pendingApplication.returnedId, '')
  assert.equal(writes, 1)
})

test('registration accepts its real registrationId ACK and confirms the same batch', async () => {
  const batch = { batchId: '101', registrationId: '', canRegister: true, registrationStatus: 'PENDING' }
  const { page } = mount('registration', {
    getMyRegistration: async () => ({ batches: [batch] }),
    registerSelf: async () => {
      batch.registrationId = '901'; batch.registrationStatus = 'REGISTERED'
      return { registrationId: '901', status: 'REGISTERED' }
    }
  })
  await page.load(); await page.doRegister(batch)
  assert.equal(page.pendingApplication, null)
  assert.match(page.applicationNotice, /本批次注册已完成/)
})

test('registration cold recovery requires both its original registrationId and batch', async () => {
  const { page, ledger } = mount('registration', { getMyRegistration: async () => ({ batches: [] }) })
  const pending = ledger.createPendingCommand('registration', {
    action: 'registration', kind: 'register', existingId: '101', idKey: 'registrationId', recordKey: 'batchId', receiptKey: 'registrationId',
    returnedId: '901', recovery: { field: 'registrationStatus', equals: 'REGISTERED' }
  })
  ledger.savePending('registration', pending)
  page.pendingApplication = { commandId: pending.commandId, _pendingOwner: pending._pendingOwner, action: 'registration', kind: 'register', objectId: '101', recordKey: 'batchId', receiptKey: 'registrationId', returnedId: '901', recovery: { field: 'registrationStatus', equals: 'REGISTERED' }, recoveryOnly: true }
  page.acceptApplication([{ batchId: '101', registrationId: '902', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.ok(page.pendingApplication)
  page.acceptApplication([{ batchId: '102', registrationId: '901', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.ok(page.pendingApplication)
  page.acceptApplication([{ batchId: '101', registrationId: '901', registrationStatus: 'REGISTERED' }], 'registrationId', () => true)
  assert.equal(page.pendingApplication, null)
})

test('recognition refreshed page can reload candidates after an older course query was invalidated', async () => {
  let resolveOld, calls = 0
  const { page } = mount('recognition', {
    getMyRecognition: async () => ({ items: [] }),
    getRecognitionCourses: () => ++calls === 1 ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ items: [{ courseId: '202', courseName: '最新正式课程' }], total: 1 })
  })
  await page.load(); page.showForm = true
  const old = page.loadRecognitionCourses(false)
  await page.load()
  assert.equal(calls, 2)
  await new Promise(setImmediate)
  assert.equal(page.courseLoading, false)
  resolveOld({ items: [{ courseId: '101', courseName: '旧课程' }], total: 1 }); await old
  assert.equal(page.courseOptions[0].courseId, '202')
})

for (const formalId of ['901', '902']) {
  test(`registration accepts the actual ACK without batchId only for its formal registration ${formalId}`, async () => {
    const batch = { batchId: '101', registrationId: null, canRegister: true, registrationStatus: 'PENDING_REGISTER' }
    const { page } = mount('registration', {
      getMyRegistration: async () => ({ batches: [batch] }),
      registerSelf: async () => { batch.registrationId = formalId; batch.registrationStatus = 'REGISTERED'; return { registrationId: '901', status: 'REGISTERED' } }
    })
    await page.load(); await page.doRegister(batch)
    assert.equal(page.pendingApplication === null, formalId === '901')
    if (formalId !== '901') assert.equal(page.pendingApplication.returnedId, '901')
  })
}

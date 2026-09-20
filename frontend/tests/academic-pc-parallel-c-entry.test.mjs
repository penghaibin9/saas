import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { beforeEach } from 'node:test'
import * as recovery from '../src/modules/academicAffairs/views/parallel-c/grade-command-recovery.js'
const store = new Map()
globalThis.window = { sessionStorage: { getItem: key => store.get(key) || null, setItem: (key, value) => store.set(key, value) } }
beforeEach(() => store.clear())
const actor = { tenantId: '1', userId: '2', currentRoleCode: 'ACADEMIC_TEACHER', activeContextId: '3' }
import { gradeError } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaGradeEntryView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g, '').replace(/ {2}components: \{[\s\S]*?\n {2}\},/, '').replace('export default', 'return')
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const task = (id, status = 'INPUTTING') => ({ gradeTaskId: id, courseName: `课程${id}`, status, allowedActions: ['INPUT', 'SUBMIT'], teacherAuthorityReady: true, usualRatio: 30, finalRatio: 70 })
const result = (...rows) => ({ code: 0, data: { list: rows, total: rows.length } })
function dynamicVm(api = {}, notices = []) {
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)) }, api, notices)
  vm.task = task('101'); vm.dynamicMode = true; vm.formalSchemeMode = 'dynamic'
  vm.dynamicData = { gradeTaskId: '101', taskVersion: 4, canWriteComponents: true, page: 1,
    rosterIdentity: { rosterVersionId: '70', rosterHash: 'a'.repeat(64) },
    scheme: { schemeId: '10', schemeVersion: 2, components: [{ code: 'PROJECT' }] },
    items: [{ studentId: '201', recordId: '301', rowVersion: 3, scores: { PROJECT: 80 }, exceptionFlag: 'NORMAL' }] }
  vm.dynamicData.items[0].originalDraft = JSON.stringify([{ PROJECT: 80 }, 'NORMAL'])
  return vm
}

test('动态命令在POST之前持久化；超时后重建页面仅核对原命令，禁止重发', async () => {
  let writes = 0
  const api = { saveDynamicGradeBatch: async () => {
    writes++; assert.ok(store.size); throw new Error('timeout')
  }, getDynamicGradeReceipt: async (_id, operation, commandKey) => ({ code: 0, data: { operation, commandKey, state: 'UNRESOLVED' } }) }
  const first = dynamicVm(api); await first.saveDynamicRow(first.dynamicRows[0])
  const key = first.dynamicCommand.commandKey
  const next = dynamicVm(api); next.restoreDynamicCommand()
  assert.equal(next.dynamicCommand.commandKey, key)
  await next.saveDynamicRow(next.dynamicRows[0]); await next.verifyDynamicCommand()
  assert.equal(writes, 1); assert.ok(next.dynamicCommand); assert.equal(next.dynamicRows[0].scores.PROJECT, 80)
})

test('动态恢复存储不可写时零POST', async () => {
  let writes = 0; const original = window.sessionStorage.setItem
  const vm = dynamicVm({ saveDynamicGradeBatch: async () => { writes++ } })
  window.sessionStorage.setItem = () => { throw new Error('quota') }
  try { await vm.saveDynamicRow(vm.dynamicRows[0]) } finally { window.sessionStorage.setItem = original }
  assert.equal(writes, 0); assert.ok(vm.dynamicRecoveryError)
})

test('动态保存5xx包裹409不能解除原命令锁，403读失败清敏但保留引用', async () => {
  const vm = dynamicVm({ saveDynamicGradeBatch: async () => ({ code: 409001, httpStatus: 500 }),
    getDynamicGradeReceipt: async () => ({ code: 403001, httpStatus: 403 }) })
  await vm.saveDynamicRow(vm.dynamicRows[0])
  assert.equal(vm.task, null); assert.equal(vm.dynamicData, null)
  const persisted = recovery.findGradeCommandReference(recovery.gradeCommandIdentityRef(actor), 'GRADE_COMPONENT_BATCH_SAVE', '101')
  assert.ok(persisted.entry)
})

test('动态POST明确409只解本次命令；保留草稿并提示复核', async () => {
  const vm = dynamicVm({ saveDynamicGradeBatch: async () => ({ code: 409001, httpStatus: 409 }) })
  await vm.saveDynamicRow(vm.dynamicRows[0])
  assert.equal(vm.dynamicCommand, null); assert.equal(vm.dynamicRows[0].scores.PROJECT, 80)
  assert.ok(vm.taskError)
})

test('迟到POST回执不改切换后的任务；原身份引用仍可恢复', async () => {
  const pending = deferred(); const vm = dynamicVm({ saveDynamicGradeBatch: () => pending.promise })
  const saving = vm.saveDynamicRow(vm.dynamicRows[0]); const key = vm.dynamicCommand.commandKey
  vm.identityKey = 'different'; vm.invalidateTask(); vm.task = task('102')
  pending.resolve({ code: 0 }); await saving
  assert.equal(vm.task.gradeTaskId, '102')
  const old = dynamicVm(); old.restoreDynamicCommand(); assert.equal(old.dynamicCommand.commandKey, key)
})

test('动态原回执错对象不能用当前成绩状态推定本次成功', async () => {
  const notices = []
  const vm = dynamicVm({ saveDynamicGradeBatch: async () => ({ code: 0 }),
    getDynamicGradeReceipt: async (_id, operation, commandKey) => ({ code: 0, data: {
      state: 'SUCCESS', operation, commandKey, result: { gradeTaskId: '102' } } }) }, notices)
  await vm.saveDynamicRow(vm.dynamicRows[0]); assert.ok(vm.dynamicCommand); assert.deepEqual(notices, [])
})

test('动态提交质量失败零POST；质量通过后仍要求原提交回执', async () => {
  let writes = 0, ready = false
  const vm = dynamicVm({ getDynamicGradeQuality: async () => ({ code: 0, data: { gradeTaskId: '101', taskVersion: 4, canSubmit: ready } }),
    submitDynamicGrade: async () => { writes++; return { code: 0 } },
    getDynamicGradeReceipt: async (_id, operation, commandKey) => ({ code: 0, data: { state: 'UNRESOLVED', operation, commandKey } }) })
  vm.openSubmit(); await vm.submit(); assert.equal(writes, 0)
  ready = true; vm.openSubmit(); await vm.submit()
  assert.equal(writes, 1); assert.ok(vm.dynamicCommand); assert.equal(vm.submitReceipt, null)
  vm.openSubmit(); await vm.submit(); assert.equal(writes, 1)
})

test('动态分页保留首屏名单版本，存在未保存草稿时不能翻页', async () => {
  const calls = []
  const vm = dynamicVm({ getDynamicGradeRoster: async (id, p) => { calls.push(p); return { code: 0, data: { gradeTaskId: id, scheme: { schemeId: '10' }, items: [] } } } })
  vm.dynamicRows[0].scores.PROJECT = 81
  await vm.changeDynamicPage(2); assert.equal(calls.length, 0)
  vm.dynamicRows[0].scores.PROJECT = 80
  await vm.changeDynamicPage(2); assert.deepEqual(calls, [{ page: 2, pageSize: 30, expectedRosterVersionId: '70' }])
})

test('409后主动回读保留本地草稿，同时展示正式分值和新行版本供复核', async () => {
  let writes = 0
  const vm = dynamicVm({ saveDynamicGradeBatch: async () => { writes++; throw new Error('timeout') }, getDynamicGradeRoster: async () => ({ code: 0, data: {
    gradeTaskId: '101', taskVersion: 5, canWriteComponents: true,
    rosterIdentity: { rosterVersionId: '70', rosterHash: 'a'.repeat(64) },
    scheme: { schemeId: '10', schemeVersion: 2 },
    items: [{ studentId: '201', recordId: '301', rowVersion: 4, scores: { PROJECT: 72 }, exceptionFlag: 'NORMAL' }] } }) })
  vm.dynamicRows[0].scores.PROJECT = 85
  await vm.loadDynamic()
  assert.equal(vm.dynamicRows[0].scores.PROJECT, 85)
  assert.equal(vm.dynamicRows[0].formalScores.PROJECT, 72)
  assert.equal(vm.dynamicRows[0].rowVersion, 4); assert.equal(vm.dynamicDirty, true)
  assert.equal(vm.dynamicRows[0].draftConflict, true)
  await vm.saveDynamicRow(vm.dynamicRows[0]); assert.equal(writes, 0)
  vm.confirmDynamicDraft(vm.dynamicRows[0]); await vm.saveDynamicRow(vm.dynamicRows[0]); assert.equal(writes, 1)
})

test('第二页保存及刷新恢复都携带原名单版本，原回执回读后可解锁', async () => {
  const api = { saveDynamicGradeBatch: async () => { throw new Error('timeout') },
    getDynamicGradeReceipt: async (_id, operation, commandKey) => ({ code: 0, data: { state: 'SUCCESS', operation, commandKey,
      result: { gradeTaskId: '101', savedCount: 1, rosterIdentity: { rosterVersionId: '70' }, items: [{ studentId: '201', recordId: '301', rowVersion: 4 }] } } }),
    getDynamicGradeRoster: async (id, p) => {
      assert.equal(p.page, 2); assert.equal(p.expectedRosterVersionId, '70')
      return { code: 0, data: { gradeTaskId: id, taskVersion: 5, canWriteComponents: true, rosterIdentity: { rosterVersionId: '70' }, scheme: { schemeId: '10', schemeVersion: 2 },
        items: [{ studentId: '201', recordId: '301', rowVersion: 4, scores: { PROJECT: 80 }, exceptionFlag: 'NORMAL' }] } }
    } }
  const vm = dynamicVm(api); vm.dynamicPage = 2
  await vm.saveDynamicRow(vm.dynamicRows[0]); assert.ok(vm.dynamicCommand)
  const reloaded = dynamicVm(api); reloaded.restoreDynamicCommand()
  assert.equal(reloaded.dynamicPage, 2); assert.equal(reloaded.dynamicCommand.rosterVersionId, '70')
  await reloaded.loadDynamic(); await reloaded.verifyDynamicCommand()
  assert.equal(reloaded.dynamicCommand, null); assert.equal(reloaded.dynamicRows[0].rowVersion, 4)
})
function mount(api = {}, dynamic = {}, notices = []) {
  if (dynamic.saveDynamicGrade) {
    const old = dynamic.saveDynamicGrade
    dynamic.saveDynamicGradeBatch = async (id, body, key) => {
      const result = await old(id, body.rows[0])
      dynamic.lastCommand = { id, body, key }
      return result
    }
    dynamic.getDynamicGradeReceipt = async (id, operation, commandKey) => ({ code: 0, data: { state: 'SUCCESS', operation, commandKey,
      result: { gradeTaskId: id, savedCount: dynamic.lastCommand.body.rows.length, items: dynamic.lastCommand.body.rows.map(row => ({ studentId: row.studentId, recordId: '900', rowVersion: 2 })) } } })
  }
  if (dynamic.getDynamicGradeRoster) {
    const read = dynamic.getDynamicGradeRoster
    dynamic.getDynamicGradeRoster = async (id, params) => {
      const res = await read(id, params)
      if (res?.code === 0) res.data = { gradeTaskId: id, taskVersion: 2, canWriteComponents: true, ...res.data,
        items: (res.data.items || []).map(row => ({ recordId: '900', rowVersion: 2, ...row })) }
      return res
    }
  }
  const options = new Function('academicAffairsApi', 'academicAffairsR10Api', 'academicFileExchangeApi', 'gradeIdentityApi', 'gradeReminderApi', 'toast', 'currentUserFromToken', 'gradeError', ...Object.keys(recovery), script)(api, { getGradeScheme: async () => ({ code: 0, data: { schemeId: '', status: 'DEFAULT' } }), ...dynamic }, {}, {}, {}, { success(m) { notices.push(m) }, error(m) { notices.push(m) } }, () => actor, gradeError, ...Object.values(recovery))
  const vm = { ...options.data(), identityKey: 'identity-1', formalSchemeMode: 'fixed', $route: { query: {} }, ctx: { currentRole: { roleCode: 'ACADEMIC_TEACHER' }, dataScope: {} } }
  for (const [name, method] of Object.entries(options.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(options.computed)) if (name !== 'identityKey') Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  return vm
}

test('录入页完整 template 可编译', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'AaGradeEntryView.vue', id: 'parallel-c-entry' }).errors, [])
})

test('深链任务不在第一页时仍精确读取，不能静默替换', async () => {
  const calls = []
  const vm = mount({ getGradeTasks: async p => { calls.push(p); return p.taskId ? result(task(p.taskId)) : result(task('first-page')) }, getGradeRecords: async () => ({ code: 0, data: { items: [] } }) })
  vm.$route.query.taskId = 'off-page'; await vm.loadTasks()
  assert.equal(vm.task.gradeTaskId, 'off-page')
  assert.ok(calls.some(p => p.taskId === 'off-page' && p.pageSize === 1))
})

test('旧记录响应不覆盖新任务', async () => {
  const pending = deferred()
  const vm = mount({ getGradeRecords: () => pending.promise })
  vm.task = task('A'); const load = vm.refreshRecords()
  vm.invalidateTask(); vm.task = task('B')
  pending.resolve({ code: 0, data: { items: [{ studentId: 'old' }] } }); await load
  assert.deepEqual(vm.rows, [])
})

test('新动态任务不会被旧 loading 丢弃；旧异常和收尾无效', async () => {
  const a = deferred(), b = deferred()
  const vm = mount({}, { getDynamicGradeRoster: id => id === 'A' ? a.promise : b.promise })
  vm.task = task('A'); const old = vm.loadDynamic()
  vm.invalidateTask(); vm.task = task('B'); const next = vm.loadDynamic()
  a.reject(new Error('old')); await old
  assert.equal(vm.dynamicLoading, true); assert.equal(vm.dynamicError, '')
  b.resolve({ code: 0, data: { status: 'INPUTTING', items: [], scheme: {} } }); await next
  assert.equal(vm.task.gradeTaskId, 'B'); assert.equal(vm.dynamicLoading, false)
})

test('只有 INPUT 不开放提交', () => {
  const vm = mount(); vm.task = { ...task('A'), allowedActions: ['INPUT'] }
  assert.equal(vm.canSubmit, false)
})

test('提交防重；响应自称成功但正式状态未变化时仍待核实', async () => {
  let writes = 0
  const pending = deferred()
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)), submitGradeTask: () => { writes++; return pending.promise } })
  vm.task = task('A'); vm.openSubmit(); const first = vm.submit(); await vm.submit()
  pending.resolve({ code: 0, data: { status: 'SUBMITTED' } }); await first
  assert.equal(writes, 1); assert.equal(vm.submitReceipt.verified, false); assert.equal(vm.submitPending, true)
  vm.openSubmit(); await vm.submit(); await vm.verifySubmit()
  assert.equal(writes, 1)
})

test('正式回读已提交，展示任务实际状态', async () => {
  let writes = 0
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId, writes ? 'SUBMITTED' : 'INPUTTING')), submitGradeTask: async () => { writes++; return { code: 0 } } })
  vm.task = task('A'); vm.openSubmit(); await vm.submit()
  assert.equal(vm.submitReceipt.verified, true); assert.equal(vm.submitReceipt.taskId, 'A'); assert.equal(vm.submitting, false)
})

test('空分不变成零；保存只回读对应行，不冲掉其他学生草稿', async () => {
  let payload
  const vm = mount({ enterScore: async (_id, body) => { payload = body; return { code: 0 } }, getGradeRecords: async () => ({ code: 0, data: { items: [{ studentId: '1', totalScore: null, passStatus: null }] } }), getGradeTasks: async p => result(task(p.taskId)) })
  vm.task = task('A'); vm.rows = [{ studentId: '1', usual: '', final: null, exceptionFlag: 'NORMAL' }, { studentId: '2', usual: 63 }]
  await vm.saveRow(vm.rows[0])
  assert.equal(payload.usualScore, undefined); assert.equal(payload.finalScore, undefined)
  assert.equal(vm.rows[1].usual, 63); assert.equal(vm.savingRowId, '')
})

test('身份变化后迟到的写响应不改新对象，不显示旧成绩', async () => {
  const response = deferred()
  const vm = mount({ enterScore: () => response.promise })
  vm.task = task('A'); const row = { studentId: '1', usual: 60, final: 70, exceptionFlag: 'NORMAL' }
  const saving = vm.saveRow(row)
  vm.identityKey = 'identity-2'; vm.invalidateTask(); vm.task = task('B')
  response.resolve({ code: 0, data: { totalScore: 99 } }); await saving
  assert.equal(row.total, undefined); assert.equal(vm.task.gradeTaskId, 'B'); assert.equal(vm.savingRowId, '')
})

test('旧导入回调和文件选择不能作用到新成绩任务', async () => {
  let reads = 0
  const vm = mount({ getGradeRecords: async () => { reads++; return { code: 0, data: { items: [] } } } })
  vm.task = task('A'); vm.openImport(); const old = vm.importActions
  vm.invalidateTask(); vm.task = task('B'); vm.openImport()
  await old.complete({ imported: 9 })
  await assert.rejects(old.upload({}), /任务已切换/)
  assert.equal(reads, 0); assert.equal(vm.task.gradeTaskId, 'B')
})

test('动态保存回读对应学生且保留其他草稿，并刷新正式允许动作', async () => {
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)) }, {
    saveDynamicGrade: async () => ({ code: 0 }),
    getDynamicGradeRoster: async () => ({ code: 0, data: { scheme: { editable: false }, items: [{ studentId: '1', totalScore: 66, passStatus: 'PASSED', scores: { A: 66 }, exceptionFlag: 'NORMAL' }] } })
  })
  vm.task = { ...task('101', 'NOT_STARTED'), allowedActions: ['INPUT'] }
  vm.dynamicData = { gradeTaskId: '101', taskVersion: 1, canWriteComponents: true, rosterIdentity: { rosterHash: 'a'.repeat(64) }, scheme: { schemeId: '10', schemeVersion: 1, components: [{ code: 'A' }] }, items: [{ studentId: '1', scores: { A: 66 }, exceptionFlag: 'NORMAL' }, { studentId: '2', scores: { A: 81 } }] }
  await vm.saveDynamicRow(vm.dynamicRows[0])
  assert.equal(vm.dynamicRows[0].totalScore, 66); assert.equal(vm.dynamicRows[1].scores.A, 81)
  assert.equal(vm.canSubmit, true); assert.equal(vm.dynamicSavingId, '')
})

test('动态录分 JSON 保持超过 MAX_SAFE_INTEGER 的学生 ID 精确字符串', async () => {
  const id = '1000000000000063602'; let body
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)) }, {
    saveDynamicGrade: async (_id, payload) => { body = JSON.parse(JSON.stringify(payload)); return { code: 0 } },
    getDynamicGradeRoster: async () => ({ code: 0, data: { scheme: {}, items: [{ studentId: id, scores: { A: 66 }, totalScore: 66, passStatus: 'PASSED', exceptionFlag: 'NORMAL' }] } })
  })
  vm.task = task('101'); vm.dynamicData = { gradeTaskId: '101', taskVersion: 1, canWriteComponents: true, rosterIdentity: { rosterHash: 'a'.repeat(64) }, scheme: { schemeId: '10', schemeVersion: 1, components: [{ code: 'A' }] }, items: [] }
  await vm.saveDynamicRow({ studentId: id, scores: { A: 66 }, exceptionFlag: 'NORMAL' })
  assert.equal(body.studentId, id); assert.equal(typeof body.studentId, 'string')
})

test('已损失精度的数值学生 ID 不允许提交', async () => {
  let writes = 0; const vm = mount({}, { saveDynamicGrade: async () => { writes++ } })
  vm.task = task('A')
  await vm.saveDynamicRow({ studentId: Number('1000000000000063602'), scores: {}, exceptionFlag: 'NORMAL' })
  assert.equal(writes, 0); assert.match(vm.taskError, /标识无法准确/)
})


test('已有动态方案的任务深链自动进入分项，不能走固定写入或导入', async () => {
  let writes = 0
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)), enterScore: async () => { writes++ } }, {
    getGradeScheme: async () => ({ code: 0, data: { schemeId: 'scheme-1', status: 'LOCKED' } }),
    getDynamicGradeRoster: async () => ({ code: 0, data: { items: [], scheme: { schemeId: 'scheme-1', status: 'LOCKED' } } })
  })
  await vm.openTask({ gradeTaskId: 'D' }); assert.equal(vm.dynamicMode, true); assert.equal(vm.fixedEditable, false)
  vm.switchMode(false); assert.equal(vm.dynamicMode, true); await vm.saveRow({studentId:'1'}); vm.openImport(); assert.equal(writes, 0); assert.equal(vm.importVisible, false)
})
test('成绩方案核对失败时，不开放固定写入', async () => {
  const vm = mount({ getGradeTasks: async p => result(task(p.taskId)) }, { getGradeScheme: async () => ({code:503001}) })
  await vm.openTask({gradeTaskId:'A'}); assert.equal(vm.formalSchemeMode, 'unknown'); assert.equal(vm.fixedEditable, false); assert.ok(vm.taskError)
})


test('方案PUT成功但回读失败时，不能固定写入/导入/重存，也不提示已回读', async () => {
  const notices=[];let fixed=0,puts=0
  const vm=mount({enterScore:async()=>{fixed++;return {code:0}}},{updateGradeScheme:async()=>{puts++;return {code:0,data:{schemeId:'new'}}},getDynamicGradeRoster:async()=>({code:503001})},notices)
  vm.task=task('A');vm.dynamicMode=true;vm.dynamicData={scheme:{schemeId:'',status:'DEFAULT',editable:true},items:[]};vm.schemeDraft=[{code:'PROJECT',name:'实训',weight:100,required:true}]
  await vm.saveScheme();vm.switchMode(false);vm.openImport();await vm.saveRow({studentId:'1'});await vm.saveScheme()
  assert.equal(vm.schemePending,true);assert.equal(vm.fixedEditable,false);assert.equal(vm.dynamicMode,true);assert.equal(vm.importVisible,false);assert.equal(fixed,0);assert.equal(puts,1);assert.deepEqual(notices,[])
})
test('未决方案回读仍是旧DEFAULT时继续阻断，读到本次正式方案才恢复', async () => {
  let saved=false
  const components=[{code:'PROJECT',name:'实训',weight:100,required:true}]
  const vm=mount({}, {updateGradeScheme:async()=>({code:0}),getDynamicGradeRoster:async()=>({code:0,data:{scheme:saved?{schemeId:'new',status:'DRAFT',editable:true,components}:{schemeId:'',status:'DEFAULT',editable:true,components:[]},items:[]}})})
  vm.task=task('A');vm.dynamicMode=true;vm.dynamicData={scheme:{editable:true},items:[]};vm.schemeDraft=components
  await vm.saveScheme();assert.equal(vm.schemePending,true);assert.equal(vm.fixedEditable,false)
  saved=true;await vm.retryTask();assert.equal(vm.schemePending,false);assert.equal(vm.formalSchemeMode,'dynamic');assert.equal(vm.fixedEditable,false)
})
test('清空既有固定分数明确传clearUsual，回读更新该行所有正式分项', async () => {
  let payload
  const vm=mount({enterScore:async(_id,p)=>{payload=p;return {code:0}},getGradeRecords:async()=>({code:0,data:{items:[{studentId:'1',usualScore:null,midtermScore:null,finalScore:80,totalScore:null,passStatus:null,exceptionFlag:'NORMAL'}]}}),getGradeTasks:async()=>result(task('A'))})
  vm.task=task('A');const row={studentId:'1',usual:'',midterm:null,final:80,exceptionFlag:'NORMAL',total:77};vm.rows=[row,{studentId:'2',usual:66}]
  await vm.saveRow(row);assert.equal(payload.clearUsual,true);assert.equal(payload.usualScore,undefined);assert.equal(row.usual,null);assert.equal(row.final,80);assert.equal(row.total,null);assert.equal(vm.rows[1].usual,66)
})
test('清空请求回读仍为旧70时不得提示已保存', async()=>{
  const notices=[];const vm=mount({enterScore:async()=>({code:0}),getGradeRecords:async()=>({code:0,data:{items:[{studentId:'1',usualScore:70,finalScore:80,totalScore:77}]}})},{},notices)
  vm.task=task('A');await vm.saveRow({studentId:'1',usual:'',final:80,exceptionFlag:'NORMAL'});assert.deepEqual(notices,[]);assert.match(vm.taskError,/待核实/)
})
test('成绩读取403清除所有旧数据与写权限，迟到的旧动态响应也无效',async()=>{
  const q=deferred();const vm=mount({getGradeRecords:async()=>({code:403001})},{getDynamicGradeRoster:()=>q.promise})
  vm.task=task('A');vm.rows=[{studentId:'private',usual:70}];vm.myTasks=[task('A')];vm.taskTotal=1;vm.schemeDraft=[{name:'private'}];const old=vm.loadDynamic()
  await vm.refreshRecords();assert.equal(vm.task,null);assert.deepEqual(vm.rows,[]);assert.deepEqual(vm.myTasks,[]);assert.deepEqual(vm.schemeDraft,[]);assert.equal(vm.taskTotal,0);assert.equal(vm.fixedEditable,false)
  q.resolve({code:0,data:{scheme:{schemeId:'old',components:[]},items:[{studentId:'old'}]}});await old;assert.equal(vm.dynamicData,null);assert.match(vm.taskError,/无权/)
})


for (const mode of ['fixed', 'dynamic']) {
  test(`${mode}保存成功后回读403仍清除旧对象和权限，不提示保存成功`, async () => {
    const notices = []; let writes = 0
    const denied = async () => ({ code: 403001 })
    const saved = async () => { writes++; return { code: 0 } }
    const vm = mount({ enterScore: saved, getGradeRecords: denied, getGradeTasks: async p => result(task(p.taskId)) }, { saveDynamicGrade: saved, getDynamicGradeRoster: denied }, notices)
    const row = { studentId: '1', usual: 70, final: 80, scores: { A: 70 }, exceptionFlag: 'NORMAL' }
    vm.task = task('101'); vm.rows = [row]; vm.myTasks = [task('101')]; vm.taskTotal = 1
    vm.dynamicData = { gradeTaskId: '101', taskVersion: 1, canWriteComponents: true, rosterIdentity: { rosterHash: 'a'.repeat(64) }, scheme: { schemeId: '10', schemeVersion: 1, components: [{ code: 'A' }] }, items: [row] }
    await (mode === 'fixed' ? vm.saveRow(row) : vm.saveDynamicRow(row))
    assert.equal(writes, 1); assert.equal(vm.task, null); assert.deepEqual(vm.rows, [])
    assert.deepEqual(vm.myTasks, []); assert.equal(vm.taskTotal, 0); assert.equal(vm.dynamicData, null)
    assert.equal(vm.editable, false); assert.equal(vm.fixedEditable, false); assert.deepEqual(notices, [])
    assert.match(vm.taskError, /无权/)
  })
}

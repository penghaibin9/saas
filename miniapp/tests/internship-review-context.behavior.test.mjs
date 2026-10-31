import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as reportPresentation from '../src/services/weeklyReportPresentation.mjs'

function view(kind, { read = async () => ({ items: [], hasMore: false }), write = async () => {} } = {}) {
  const folder = kind === 'report' ? 'process-report-review' : 'plan-task-review'
  const source = fs.readFileSync(new URL(`../src/pages/teacher-internship/${folder}/index.vue`, import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const context = { restore() {}, load: async () => {}, batches: [{ id: '1' }, { id: '2' }], selectedBatchId: '1', can: () => true }
  let modal
  const dependencies = {
    ...reportPresentation, ReportFilePreview:{}, ReportObligations:{}, currentSessionGeneration:()=>1,
    normalizeError:e=>({kind:Number(e?.code)===409001?'conflict':'unknown',text:e?.message||'操作未完成'}),formatDateTime:String,
    useInternshipContextStore: () => context, toast() {}, openBusinessFile: async () => {},
    teacherInternshipProcessReports: read, teacherInternshipPlanTasks: read,
    teacherInternshipProcessReportDetail: async id => ({ id,version: 5,batchId:'1',internshipId:'3',reportType:'DAILY',status:'PENDING_REVIEW', content: '当前正文' }),
    teacherInternshipProcessReportReview: write, teacherInternshipPlanTaskReview: write,
    uni: { showModal: options => { modal = options.success } }
  }
  const def = new Function(...Object.keys(dependencies), source)(...Object.values(dependencies))
  const vm = { ...def.data(), state: 'ready', canReview: true, batchId: '1',$refs:{reportPreview:{reset(){}}},$nextTick:fn=>Promise.resolve().then(fn) }
  for (const [key, method] of Object.entries(def.methods)) vm[key] = method.bind(vm)
  return { vm, context, confirm: async () => {
    if(kind==='task') return modal({ confirm: true, content: '材料内容已核对' })
    if(vm.reviewPanel){vm.reviewPanel.draft.comment='材料内容已核对';vm.reviewPanel.draft.ratingLevel=4}
    return vm.submitReview()
  } }
}

for (const kind of ['report', 'task']) {
  test(`${kind}: refreshing the same batch rejects the old second page`, async () => {
    let finish
    const { vm } = view(kind, { read: async (_batch, page) => page === 2 ? new Promise(resolve => { finish = resolve }) : { items: [{ id: 'fresh' }], hasMore: false } })
    vm.hasMore = true; vm.list = [{ id: 'old' }]
    const pending = vm.loadMore(); await vm.load()
    finish({ items: [{ id: 'stale' }], hasMore: false }); await pending
    assert.deepEqual(vm.list.map(item=>item.id), ['fresh'])
  })

  test(`${kind}: an approval modal cannot submit after the batch changes`, async () => {
    let writes = 0
    const { vm, confirm } = view(kind, { write: async () => { writes++ } })
    if (kind === 'report') vm.detail = { '1': { version: 4 } }
    vm.review({ id: '1', version: 4 }, 'APPROVE')
    vm.loadSeq++; vm.batchId = '2'; await confirm()
    assert.equal(writes, 0)
  })
}

test('report review sends the version of the body actually opened by the teacher', async () => {
  let body
  const { vm, confirm } = view('report', { write: async (_id, _batch, payload) => { body = payload } })
  const row = { id: '9007199254740999', version: 2 }
  await vm.toggle(row); vm.review(row, 'APPROVE'); await confirm()
  assert.equal(body.expectedVersion, 5)
  assert.equal(body.batchId, '1')
})

test('student report retry retains returned text when switching type and disables writes after read failure', async () => {
  const source = fs.readFileSync(new URL('../src/pages/student-internship/process-report/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const report={id:'9',batchId:'1',internshipId:'2',reportType:'SUMMARY',periodKey:'FINAL',status:'RETURNED',content:'学生原来的实习总结。'.repeat(40),version:2,attachments:[]}
  const deps={...reportPresentation,MobileInlineAlert:{},ReportFilePreview:{},currentSessionGeneration:()=>1,useSessionStore:()=>({logged:false}),readInternshipDraft:()=>null,writeInternshipDraft(){},fileSdk:{},normalizeError:e=>({text:e?.message||'读取失败'}),toast(){},studentApi:{getInternshipProcessReportDetail:async()=>report},uni:{setNavigationBarTitle(){}}}
  const def = new Function(...Object.keys(deps),source)(...Object.values(deps))
  const vm = { ...def.data(), pageState: 'ready',loaded:true,batchId:'1',internshipId:'2',$refs:{reportPreview:{reset(){}}} }
  for (const [key, method] of Object.entries(def.methods)) vm[key] = method.bind(vm)
  for (const [key, getter] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => getter.call(vm) })
  vm.reports = [report]
  vm.load=async()=>{}
  vm.pickType('SUMMARY')
  await vm.selectRecord(report)
  assert.equal(vm.form.content, report.content)
  assert.equal(vm.canSubmit, true)
  vm.pageState = 'error'; assert.equal(vm.canSubmit, false)
})

import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { shiftTypeText, shiftTypeValue } from '../src/modules/internship/constants/position.constants.js'

const batch = '9007199254741001', record = '9007199254741003'
const archiveRef = `/admin/internship/archive?batchId=${batch}&id=${record}&keyword=001&page=2`

function page(name, overrides = {}) {
  const source = fs.readFileSync(new URL(`../src/modules/internship/views/${name}.vue`, import.meta.url), 'utf8')
  const body = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names = [...body.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)]
    .flatMap(([, value]) => value.replace(/[{}]/g, '').split(',').map(x => x.trim()))
  const store = { selectedBatchId: batch, withBatchQuery: query => ({ ...query, batchId: store.selectedBatchId }) }
  const deps = { useInternshipBatchStore: () => store, canCode: (ctx, code) => ctx.permissionPatterns.includes(code), formatDateTime: value => value || '',
    emptyConflict: () => ({ active: false }), toast: { success() {}, error() {} }, shiftTypeText, shiftTypeValue, ...overrides }
  const component = new Function(...names, body.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return'))(...names.map(name => deps[name] ?? {}))
  const targets = []
  const vm = { ...component.data(), ctx: { permissionPatterns: [] }, $route: { path: '', fullPath: '', query: { batchId: batch }, params: { id: record } },
    $router: { push: value => { targets.push(value); return Promise.resolve() }, replace: value => { targets.push(value); return Promise.resolve() }, options: { history: { state: {} } } },
    $refs: {}, $nextTick: async callback => callback?.() }
  for (const [key, method] of Object.entries(component.methods)) vm[key] = method.bind(vm)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: getter.bind(vm) })
  return { vm, store, targets, component, source }
}

async function render(p) {
  const template = p.source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render = new Function('Vue', compile(template, { prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ render() { return render(p.vm, []) } })
  for (const name of new Set([...p.source.matchAll(/<([A-Z][A-Za-z]+)/g)].map(match => match[1]))) {
    app.component(name, { inheritAttrs: false, render() { return name === 'AppButton' ? Vue.h('button', this.$slots.default?.()) : [this.$slots.actions?.(), this.$slots.default?.()] } })
  }
  return renderToString(app)
}

test('学生档案进入归档直接定位原生记录，归档核对保留返回档案入口', () => {
  const student = page('InternshipStudentDetailView')
  student.vm.detail = { id: record, batchId: batch }
  student.vm.$route.fullPath = `/admin/internship/students/${record}?batchId=${batch}&section=profile`
  student.vm.goArchive()
  const target = student.targets[0]
  assert.equal(target.query.id, record)
  assert.equal(target.query.internshipId, undefined)
  const archive = page('ArchiveView')
  archive.vm.$route.query = target.query
  let selected
  archive.vm.openDetailById = id => { selected = id }
  archive.vm.syncDetail()
  assert.equal(selected, record)
  assert.equal(archive.vm.sourceReturnTo, student.vm.$route.fullPath)
})

test('归档四类补项使用正式页面、稳定原单和批次，返回可恢复原筛选', () => {
  const p = page('ArchiveView')
  p.vm.$route.fullPath = archiveRef
  p.vm.panel = { data: { studentName: '合成学生', studentNo: '000001' }, rowId: record }
  const cases = {
    eligibility: { path: `/admin/internship/students/${record}`, query: { section: 'eligibility' } },
    advisor: { path: '/admin/internship/students', query: { panel: 'mentor', advisorId: record } },
    visit: { path: '/admin/internship/guidance', query: { panel: 'visit', keyword: '000001' } },
    openIncident: { path: '/admin/internship/compliance', query: { tab: 'incidents', internshipId: record } }
  }
  for (const [code, target] of Object.entries(cases)) {
    p.vm.goFix({ code, path: '/admin/internship/compliance' })
    assert.deepEqual(p.targets.at(-1), { path: target.path, query: { ...target.query, returnTo: archiveRef, batchId: batch } })
  }
})

test('导师分配直接读取补项原单，取消与成功后返回归档而不丢旧队列', async () => {
  const calls = []
  const p = page('InternshipStudentListView', { internStudentApi: {
    getStudentDetail: async id => { calls.push(id); return { code: 0, data: { id, batchId: batch, status: 'ASSESSING', version: 0 } } },
    assignAdvisor: async () => ({ code: 0, data: { id: record, version: 1, name: '合成学生', advisorName: '合成导师' } })
  } })
  p.vm.ctx.permissionPatterns = ['internship.student.view', 'internship.student.manage']
  p.vm.$route.query = { batchId: batch, panel: 'mentor', advisorId: record, returnTo: archiveRef }
  p.vm.openAssignAdvisor = async row => { p.vm.advisorRow = row }
  await p.vm.restoreAdvisor()
  assert.deepEqual(calls, [record])
  p.vm.closeAdvisor()
  assert.equal(p.targets.at(-1), archiveRef)
  p.vm.advisorRow = { id: record, status: 'ASSESSING', version: 0 }
  p.vm.advisorAssignmentUserId = '19'
  p.vm.load = () => assert.fail('返回归档时不再读取旧导师队列')
  await p.vm.submitAssignAdvisor()
  assert.equal(p.targets.at(-1), archiveRef)
  assert.equal(p.vm.advisorReceipt.version, 1)
})

test('归档巡访页签及新增、深链取消后仍保留返回归档入口', () => {
  const p = page('GuidanceVisitView')
  p.vm.$route.query = { batchId: batch, panel: 'visit', keyword: '000001', returnTo: archiveRef }
  let selected
  p.vm.applyPanel = panel => { selected = panel }
  p.vm.syncPanelFromRoute()
  assert.equal(selected, 'visit')
  p.vm.tab = 'visit'
  p.vm.goCreate()
  const target = p.targets.at(-1)
  assert.equal(target.query.returnTo, archiveRef)
  assert.equal(target.query.keyword, '000001')
  const form = page('GuidanceRecordFormView')
  form.vm.$route.query = target.query
  form.vm.type = 'visit'
  form.vm.backToList()
  assert.equal(form.targets[0].query.returnTo, archiveRef)
  assert.equal(form.targets[0].query.panel, 'visit')
})

test('事故按实习记录筛选全部未结原单，事故编号同值也不串学生，非法值不扩大范围', async () => {
  const p = page('InternshipComplianceView')
  p.vm.$route.query = { batchId: batch, internshipId: record, id: record, returnTo: archiveRef }
  p.vm.workbench.incidents = [
    { id: record, internshipId: '8', status: 'REPORTED' },
    { id: '2', internshipId: record, status: 'INVESTIGATING' },
    { id: '3', internshipId: record, status: 'PENDING_REVIEW' },
    { id: '4', internshipId: record, status: 'CLOSED' }
  ]
  assert.deepEqual(p.vm.incidentRows.map(row => row.id), ['2', '3'])
  p.vm.workbench.incidents[1].status = 'CLOSED'
  assert.deepEqual(p.vm.incidentRows.map(row => row.id), ['3'])
  p.vm.workbench.incidents[2].status = 'CLOSED'
  p.vm.activeTab = 'incidents'; p.vm.loading = false; p.vm.can = () => false
  assert.match(await render(p), /该生已无未关闭事故，请返回归档重新核验/)
  for (const invalid of ['bad', '', '0', [record, '8']]) {
    p.vm.$route.query.internshipId = invalid
    assert.ok(p.vm.incidentScopeError)
    assert.deepEqual(p.vm.incidentRows, [])
  }
  delete p.vm.$route.query.internshipId
  assert.equal(p.vm.incidentRows.length, 4)
})

test('风险及调岗查看档案后准确返回原单、筛选和页码，外部或其他批次地址不恢复', () => {
  for (const [name, ref] of [
    ['ChangeRequestListView', `/admin/internship/changes?batchId=${batch}&id=31&panel=pending&page=3&keyword=001`],
    ['RiskDisposalView', `/admin/internship/risk-disposal?batchId=${batch}&id=45&stage=pending&page=2`],
    ['InternshipRiskView', `/admin/internship/risks?batchId=${batch}&panel=board&page=4`]
  ]) {
    const p = page(name)
    p.vm.$route.fullPath = ref
    p.vm.detail = name === 'ChangeRequestListView' ? { data: { internId: record } } : { internId: record }
    p.vm.goStudent({ internId: record })
    const student = page('InternshipStudentDetailView')
    student.vm.$route.query = p.targets[0].query
    student.vm.detail = { batchId: batch }
    student.vm.goBack()
    assert.equal(student.targets[0], ref)
    assert.notEqual(student.vm.backDestination.label, '返回名单')
  }
  const p = page('InternshipStudentDetailView')
  for (const ref of ['https://other.example', '//other.example', '/admin/internship/changes-unsafe?batchId=' + batch, '/admin/internship/changes?batchId=8']) {
    p.vm.$route.query.returnTo = ref
    assert.equal(p.vm.backDestination, null)
  }
})

test('归档返回入口仅接受同批次正式地址，切换批次后不带回旧对象', () => {
  for (const name of ['InternshipStudentListView', 'GuidanceVisitView', 'InternshipComplianceView']) {
    const p = page(name)
    p.vm.$route.query.returnTo = archiveRef
    assert.equal(p.vm.archiveReturnTo, archiveRef)
    for (const ref of ['https://other.example' + archiveRef, '//other.example' + archiveRef, '/admin/internship/archive-unsafe?batchId=' + batch, '/admin/internship/archive?batchId=8']) {
      p.vm.$route.query.returnTo = ref
      assert.equal(p.vm.archiveReturnTo, '')
    }
    p.vm.$route.query.returnTo = archiveRef
    p.store.selectedBatchId = '8'
    assert.equal(p.vm.archiveReturnTo, '')
  }
})

test('普通教师保留关联名称但不能打开未授权企业、岗位或企业评价页面', async () => {
  const p = page('InternshipStudentDetailView')
  p.vm.loading = false
  p.vm.detail = { enterpriseId: '8', positionId: '9', batchId: batch, name: '合成学生', enterpriseName: '合成企业', positionName: '合成岗位', status: 'ASSESSING', eligibilityStatus: 'QUALIFIED' }
  p.vm.openEnterprise(); p.vm.openPosition()
  assert.equal(p.targets.length, 0)
  const teacherHtml = await render(p)
  assert.match(teacherHtml, /合成企业/); assert.match(teacherHtml, /合成岗位/)
  assert.doesNotMatch(teacherHtml, /<button[^>]*>合成(?:企业|岗位)<\/button>/)
  p.vm.ctx.permissionPatterns = ['internship.enterprise.view', 'internship.position.view']
  p.vm.openEnterprise(); p.vm.openPosition()
  assert.equal(p.targets.length, 2)
  assert.match(await render(p), /<button[^>]*>合成企业<\/button>/)
  const evaluation = page('StudentEvalView')
  evaluation.vm.goEnterpriseEvals()
  assert.equal(evaluation.targets.length, 0)
  assert.doesNotMatch(await render(evaluation), /<button[^>]*>企业评价<\/button>/)
  evaluation.vm.ctx.permissionPatterns = ['internship.eval.enterprise.view']
  evaluation.vm.goEnterpriseEvals()
  assert.equal(evaluation.targets.length, 1)
  assert.match(await render(evaluation), /<button[^>]*>企业评价<\/button>/)
})

test('学校可补齐未分配岗位的企业导师，已有分配时不改动原指导关系', async () => {
  for (const allocatedCount of [0, 1]) {
    let submitted
    const p = page('PositionFormView', {
      positionApi: { updatePosition: async (id, body) => { submitted = { id, body }; return { code: 0, data: { id } } } },
      REMUNERATION_TYPE: [], REMUNERATION_CYCLE: []
    })
    p.vm.ctx.permissionPatterns = ['internship.position.manage']
    p.vm.detail = { id: record, version: 3, batchId: batch, allocatedCount, status: 'PENDING' }
    p.vm.form.mentorContactId = '157'
    p.vm.$refs.posForm = { validate: async () => ({ valid: true }) }
    await p.vm.onSubmit()
    assert.equal(submitted.id, record)
    assert.equal(submitted.body.expectedVersion, 3)
    assert.equal(submitted.body.batchId, batch)
    assert.equal(submitted.body.mentorContactId, allocatedCount ? undefined : '157')
  }
})

test('企业评价先办理考核阶段，原单返回与提交前阶段复核均有效', async () => {
  let writes=0
  const p=page('EnterpriseEvalView',{enterpriseEvalApi:{review:async()=>{writes++;return {code:0,data:{id:'94'}}}}})
  p.vm.ctx.permissionPatterns=['internship.eval.enterprise.review','internship.student.view']
  p.vm.selectedId='94';p.vm.$route.fullPath=`/admin/internship/enterprise-evals?batchId=${batch}&id=94&page=2`
  p.vm.detail={loading:false,error:'',data:{id:'94',internId:record,batchId:batch,internshipStatus:'ONBOARD',reviewStatus:'PENDING',version:0}}
  p.vm.openReview(p.vm.detail.data,'APPROVE');assert.equal(p.vm.pending,null)
  p.vm.openStudent()
  const student=page('InternshipStudentDetailView');student.vm.$route.query=p.targets[0].query;student.vm.detail={batchId:batch};student.vm.goBack()
  assert.equal(student.targets[0],p.vm.$route.fullPath)
  p.vm.detail.data.internshipStatus='ASSESSING';p.vm.openReview(p.vm.detail.data,'APPROVE');assert.equal(p.vm.pending.version,0)
  p.vm.detail.data.internshipStatus='ONBOARD';await p.vm.onConfirm({reason:''});assert.equal(writes,0)
})

test('状态推进未满足条件时持续显示中文缺项，保留原学生与版本', async () => {
  const p=page('InternshipStudentDetailView',{internStudentApi:{setStatus:async()=>({code:409001,message:'进入考核前置未完成',details:{blockers:[{label:'指导次数',reason:'应有 2，有效 0，缺 2'}]}})}})
  p.vm.ctx.permissionPatterns=['internship.student.manage']
  p.vm.detail={id:record,batchId:batch,version:5,status:'ONBOARD'}
  p.vm.confirm={visible:true,action:'STATUS',extra:'ASSESS'}
  await p.vm.onConfirm({})
  assert.equal(p.vm.commandError,'进入考核前置未完成')
  assert.deepEqual(p.vm.commandBlockers,['指导次数：应有 2，有效 0，缺 2'])
  assert.equal(p.vm.confirm.visible,true);assert.equal(p.vm.detail.version,5);assert.equal(p.vm.detail.status,'ONBOARD')
})

test('批次页面填写的签到天数实际随规则保存，明确零值仍保留',()=>{
  const p=page('BatchFormView')
  for(const days of [0,1,30]){
    p.vm.rulesForm.checkin.requiredDays=days
    assert.equal(p.vm.buildRulesFromForm().checkin.requiredDays,days)
  }
})

test('考勤工作区仅显示当前身份能进入的补卡办理页签',()=>{
  const p=page('AttendanceView')
  p.vm.ctx.permissionPatterns=['internship.attendance.view']
  assert.deepEqual(p.vm.visibleTabs.map(t=>t.key),['checkins','exceptions'])
  p.vm.ctx.permissionPatterns.push('internship.makeup.view')
  assert.deepEqual(p.vm.visibleTabs.map(t=>t.key),['checkins','exceptions','makeup-apply'])
  p.vm.ctx.permissionPatterns.push('internship.makeup.review')
  assert.ok(p.vm.visibleTabs.some(t=>t.key==='makeup-review'))
})

test('实习日期失败关闭重开保留同单草稿和原版本，明确回读后才采用新版',async()=>{
  let body
  const p=page('InternshipStudentDetailView',{internStudentApi:{updateStudent:async(_id,payload)=>{body=payload;return {code:'DATA_CONFLICT',message:'实习记录版本已更新'}}}})
  p.vm.ctx.permissionPatterns=['internship.student.manage'];p.vm.detail={id:record,batchId:batch,status:'ASSESSING',version:5,internStartDate:'2026-10-18'}
  p.vm.openPeriod();p.vm.periodForm.end='2026-10-18';p.vm.periodForm.reason='虚构联调：经学校核对实际结束日期'
  await p.vm.savePeriod();p.vm.periodVisible=false;p.vm.openPeriod()
  assert.equal(body.expectedVersion,5);assert.equal(p.vm.periodForm.end,'2026-10-18');assert.match(p.vm.periodError,/版本/)
  p.vm.load=async()=>{p.vm.detail={...p.vm.detail,version:6,internRange:'2026-10-18 ~ 2026-10-18'}}
  await p.vm.refreshPeriod();assert.equal(p.vm.periodVersion,6);assert.equal(p.vm.periodForm.reason,'虚构联调：经学校核对实际结束日期')
  assert.equal(p.vm.periodLatest,'2026-10-18 ~ 2026-10-18')
})

test('实习日期离开原单后迟到回执不得关闭新学生填写',async()=>{
  let finish
  const p=page('InternshipStudentDetailView',{internStudentApi:{updateStudent:()=>new Promise(resolve=>finish=resolve)}})
  p.vm.ctx.permissionPatterns=['internship.student.manage'];p.vm.detail={id:record,batchId:batch,status:'ASSESSING',version:5}
  p.vm.openPeriod();p.vm.periodForm={start:'2026-10-18',end:'2026-10-18',reason:'虚构联调实际日期核对'}
  const saving=p.vm.savePeriod();p.vm.loadSequence++;p.vm.detail={...p.vm.detail,id:'9007199254741999'};p.vm.periodSaving=false;p.vm.openPeriod();p.vm.periodForm.reason='新学生未提交说明'
  finish({code:0,data:{}});await saving
  assert.equal(p.vm.periodVisible,true);assert.equal(p.vm.periodForm.reason,'新学生未提交说明')
})


test('批次普通编辑保留历史评分字段，不用新默认配置覆盖旧快照',()=>{
  const p=page('BatchFormView')
  p.vm.fillStructured({rules:{score:{passThreshold:65,components:[{name:'原企业项',weight:.7},{name:'原教师项',weight:.3}]},evaluation:{enterpriseWeight:.5,teacherWeight:.3,selfWeight:.2}}})
  const rules=p.vm.buildRulesFromForm()
  assert.deepEqual(rules.score,{passThreshold:65,components:[{name:'原企业项',weight:.7},{name:'原教师项',weight:.3}]})
  assert.deepEqual(rules.evaluation,{enterpriseWeight:.5,teacherWeight:.3,selfWeight:.2})
})

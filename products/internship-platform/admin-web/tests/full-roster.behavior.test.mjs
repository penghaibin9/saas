import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as dictionaries from '../src/modules/internship/constants/internship-student.constants.js'

const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipStudentListView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
const bindings = [...script.matchAll(/^import (.+?) from .+$/gm)].flatMap(([, names]) => names.replace(/[{}]/g, '').split(',').map(value => value.trim()))
const executable = script.replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

function page(api = {}, query = {}) {
  const batch = { selectedBatchId: '9007199254740993101', canWriteStudents: true, withBatchQuery: value => ({ ...value, batchId: batch.selectedBatchId }) }
  const calls = []
  const deps = { ...dictionaries, internStudentApi: { getStudents: async params => { calls.push(params); return { code: 0, data: { list: [], total: 0 } } }, ...api },
    useInternshipBatchStore: () => batch, canCode: (ctx, code) => ctx.permissionPatterns.includes(code), toast: { success() {}, error() {} } }
  const component = new Function(...bindings, executable)(...bindings.map(name => deps[name] ?? {}))
  const vm = { ...component.data(), ctx: { permissionPatterns: ['internship.student.view', 'internship.student.export', 'internship.student.manage'] },
    $route: { query, path: '/admin/internship/students', fullPath: '/admin/internship/students' }, $router: { replace() {}, resolve: () => ({ fullPath: '/changed' }) } }
  for (const [key, method] of Object.entries(component.methods)) vm[key] = (...args) => method.apply(vm, args)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => getter.call(vm) })
  return { vm, batch, component, calls }
}

test('导师交接回执只展示服务端原对象与接收人，范围切换清除且迟到成功不能覆盖', async () => {
  const wait=deferred();let sent
  const {vm}=page({assignAdvisor:(id,body)=>{sent={id,body};return wait.promise}})
  vm.advisorRow={id:'9007199254740993118',version:3,advisorUserId:'old',status:'ONBOARD'}
  vm.advisorAssignmentUserId='new';vm.advisorAssignmentReason='原导师退出交接'
  const pending=vm.submitAssignAdvisor()
  assert.deepEqual(sent,{id:'9007199254740993118',body:{advisorUserId:'new',reason:'原导师退出交接',expectedVersion:3}})
  wait.resolve({code:0,data:{id:sent.id,version:4,name:'交接学生',advisorName:'接收教师'}});await pending
  assert.equal(vm.advisorReceipt.id,sent.id);assert.equal(vm.advisorReceipt.version,4)
  assert.equal(vm.advisorReceipt.objectLabel,'交接学生 · 现任指导教师：接收教师')
  assert.match(vm.advisorReceipt.nextStep,/在办请假.*另行交接/)
  vm.resetScope();assert.equal(vm.advisorReceipt,null)
  const late=deferred();const next=page({assignAdvisor:()=>late.promise}).vm
  next.advisorRow={id:'2',version:0,status:'ONBOARD'};next.advisorAssignmentUserId='new'
  const saving=next.submitAssignAdvisor();next.resetScope()
  late.resolve({code:0,data:{id:'2',version:1,name:'旧学生',advisorName:'旧教师'}});await saving
  assert.equal(next.advisorReceipt,null)
})

test('导师交接失败保留填写内容且不显示完成回执',async()=>{
  const {vm}=page({assignAdvisor:async()=>({code:409,message:'记录版本冲突'})})
  vm.advisorRow={id:'2',version:0,status:'ONBOARD'};vm.advisorAssignmentUserId='new';vm.advisorAssignmentReason='保留交接说明'
  await vm.submitAssignAdvisor()
  assert.equal(vm.advisorReceipt,null);assert.equal(vm.advisorAssignmentReason,'保留交接说明')
  assert.equal(vm.advisorConflict,true);assert.match(vm.advisorError,/填写内容已保留/)
})

test('采购字段都有中文筛选入口，完整一览表覆盖计划和全部责任老师', () => {
  const { vm } = page()
  const required = ['studentName','studentNo','grade','collegeName','majorName','className','planName','internshipType','internshipMode',
    'status','enterpriseName','companyCreditCode','positionName','salaryMin','salaryMax','workLocation','headTeacherName','advisorName','mentorName',
    'applicationStatus','companyNature','companyIndustry','majorMatch','sourceRegion','rotationInfo','rotationScoreMin','rotationScoreMax','agreementStatus']
  const keys = new Set(vm.filterFields.map(field => field.key))
  for (const key of required) assert.ok(keys.has(key), key)
  for (const field of vm.filterFields) assert.match(field.label, /[\u3400-\u9fff]/)
  vm.tableMode = 'full'
  const columns = new Set(vm.columns.map(column => column.key))
  for (const key of ['className','batchName','planNames','internshipTypeLabel','internshipMode','headTeacherName','advisor','mentorName',
    'applicationStatusLabel','workLocation','rotationInfo','rotationScoreSummary','agreementStatusLabel']) assert.ok(columns.has(key), key)
  assert.equal(columns.has('agreementStatus'), false)
})

test('自主实习无岗位库编号仍显示真实单位和岗位', () => {
  const { vm } = page()
  assert.equal(vm.hasPlacementDetails({ positionId: null, enterpriseName: '合成自主单位', positionName: '研发实习' }), true)
  assert.equal(vm.hasPlacementDetails({ positionId: null, enterpriseName: '', positionName: '' }), false)
})

test('查询与导出共用已应用条件，布尔否和零金额不丢失，学号不变为数字', async () => {
  let exported
  const { vm, calls } = page({ exportStudents: async params => { exported = params; return { code: 0 } } })
  vm.appliedFilters = { ...vm.appliedFilters, studentNo: '0009007199254740993111', salaryMin: '0', majorMatch: 'false', allBatches: 'true', planName: '追加方案' }
  vm.filters.planName = '尚未查询的草稿'
  vm.page = 3
  await vm.load(); await vm.exportFn()
  const { page: number, pageSize, ...listed } = calls[0]
  assert.equal(number, 3)
  assert.equal(pageSize, 10)
  assert.deepEqual(exported, listed)
  assert.equal(exported.majorMatch, false)
  assert.equal(exported.allBatches, true)
  assert.equal(exported.salaryMin, '0')
  assert.equal(exported.studentNo, '0009007199254740993111')
  assert.equal(exported.planName, '追加方案')
})

test('刷新恢复完整视图与全部筛选，翻页保留已查询条件', async () => {
  const { vm, calls } = page({}, { panel: 'roster', tableMode: 'full', page: '2', mentorName: '企业甲教师', rotationScoreMin: '80', agreementStatus: 'EFFECTIVE' })
  vm.restoreAdvisor = () => {}
  vm.applyRouteFilters()
  await Promise.resolve()
  assert.equal(vm.tableMode, 'full')
  assert.equal(calls[0].mentorName, '企业甲教师')
  assert.equal(calls[0].rotationScoreMin, '80')
  let location
  vm.$router.replace = value => { location = value }
  vm.turnPage(3)
  assert.equal(location.query.mentorName, '企业甲教师')
  assert.equal(location.query.agreementStatus, 'EFFECTIVE')
  assert.equal(location.query.tableMode, 'full')
})

test('改变已查询条件或批次后拒绝迟到导出，草稿变化仍可取得同条件结果', async () => {
  for (const change of ['applied', 'batch', 'draft']) {
    const wait = deferred(), { vm, batch } = page({ exportStudents: () => wait.promise })
    const pending = vm.exportFn()
    if (change === 'applied') vm.appliedFilters.studentName = '另一学生'
    if (change === 'batch') batch.selectedBatchId = '9007199254740993102'
    if (change === 'draft') vm.filters.studentName = '尚未查询'
    wait.resolve({ code: 0, data: { contentBase64: 'fixture' } })
    assert.equal((await pending).code, change === 'draft' ? 0 : 1)
  }
})

test('跨批次基础资料携带学生自己的批次，其他批次没有直接办理按钮', () => {
  const { vm } = page()
  const row = { id: '9007199254740993201', batchId: '9007199254740993102', status: 'READY' }
  vm.onRowAction('basic', row)
  assert.equal(vm.basicRecordId, row.id)
  assert.equal(vm.basicBatchId, row.batchId)
  assert.deepEqual(vm.rowActions(row).map(action => action.key), ['detail', 'basic'])
})

test('切换身份或批次后迟到列表不恢复旧学生', async () => {
  const wait = deferred(), { vm } = page({ getStudents: () => wait.promise })
  const pending = vm.load()
  vm.resetScope()
  wait.resolve({ code: 0, data: { list: [{ id: 'old' }], total: 1 } })
  await pending
  assert.deepEqual(vm.rows, [])
  assert.equal(vm.total, 0)
})

test('真实路由监听在切换列模式或翻页时保留尚未查询的输入', () => {
  const { vm, component } = page()
  vm.filters.planName = '还未点击查询的方案'
  const old = { panel:'roster', page:'1' }
  const next = { ...old, tableMode:'full' }
  vm.$route.query = next
  component.watch['$route.query'].handler.call(vm, next, old)
  assert.equal(vm.tableMode, 'full')
  assert.equal(vm.filters.planName, '还未点击查询的方案')
  const nextPage = { ...next, page:'2' }
  vm.$route.query = nextPage
  component.watch['$route.query'].handler.call(vm, nextPage, next)
  assert.equal(vm.page, 2)
  assert.equal(vm.filters.planName, '还未点击查询的方案')
})

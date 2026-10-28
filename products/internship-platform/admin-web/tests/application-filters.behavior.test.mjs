import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { formatDateTime } from '../src/utils/dateUtils.js'
import { compile, createSSRApp, getCurrentInstance, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

const batchId = '9007199254740993001'
const ok = data => ({ code: 0, data })
const emptyOptions = () => ({ academicYears: [], grades: [], colleges: [], majors: [], classes: [] })
function page(api = {}, query = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipApplicationReviewView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const store = { selectedBatchId: batchId, withBatchQuery: q => ({ ...q, batchId }) }
  const scope = Object.fromEntries(['ModulePageShell','DataTable','LoadingState','ErrorState','AppButton','AppStatusTag','AppSearchBox','AppSelect','AppDescriptionList','AppFilePreview','AppAuditTrail','AppPermissionButton','AppConfirmDialog'].map(name => [name, {}]))
  Object.assign(scope, { formatDateTime, emptyConflict: () => ({}), REJECT_APPLICATION: [], useInternshipBatchStore: () => store, canCode: () => true,
    toast: { success() {}, error() {} }, internshipApplicationApi: { getApplications: async () => ok({ list: [], total: 0 }),
      getFilterOptions: async () => ok(emptyOptions()), exportApplications: async () => ok(true), ...api } })
  const component = new Function(...Object.keys(scope), script)(...Object.values(scope))
  const vm = { ...component.data(), ctx: { ctxKey: 'first' }, $route: { query, fullPath: '/admin/internship/applications' },
    $router: { push: to => to, replace: to => to, resolve: to => ({ fullPath: JSON.stringify(to) }) } }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm, args)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, component, store }
}

test('真实搜索子组件清空及上下文恢复后的防抖仍按事件值查询三个字段',()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/views/InternshipApplicationReviewView.vue',import.meta.url),'utf8')
  const childSource=fs.readFileSync(new URL('../src/components/common/display/AppSearchBox.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default','return')
  for(const [field,label] of [['keyword','搜索申请'],['studentName','学生姓名'],['studentNo','学号']]){
    let pending,last
    const child=new Function('setTimeout','clearTimeout',childSource)(fn=>{pending=fn;return 1},()=>{pending=null})
    const {vm,component}=page({}, {[field]:'旧筛选'})
    vm.$router.replace=to=>{last=to};vm.restoreLocation()
    const expression=source.match(new RegExp(`aria-label="${label}"[^>]*@search="([^"]+)"`))[1]
    const onSearch=new Function('vm','$event',`with(vm){const result=(${expression});return typeof result==='function'?result($event):result}`)
    const box={...child.data(),modelValue:'旧筛选',debounce:300,$refs:{},$emit:(event,value)=>{if(event==='search')onSearch(vm,value)}}
    // Exercise the explicit search event while the parent model still contains its restored value.
    child.methods.onClear.call(box);assert.equal(last.query[field],undefined,field)
    vm.restoreLocation();child.methods.onInput.call(box,{target:{value:'明确新值'}})
    component.watch['ctx.ctxKey'].call(vm);pending();assert.equal(last.query[field],'明确新值',field)
  }
})

test('申请提交审核时间按本地日期显示且零薪资和否对口保留',t=>{
  const previous=process.env.TZ;process.env.TZ='Asia/Shanghai';t.after(()=>{if(previous===undefined)delete process.env.TZ;else process.env.TZ=previous})
  const {vm}=page();const raw='2026-10-12T23:35:49Z'
  vm.drawer.data={applicationType:'SELF_ARRANGED',submittedAt:raw,reviewedAt:raw,agreedSalary:0,majorMatch:false}
  assert.equal(vm.detailItems.find(item=>item.label==='提交时间').value,'2026-10-13 07:35')
  assert.equal(vm.reviewItems.find(item=>item.label==='审核时间').value,'2026-10-13 07:35')
  assert.equal(vm.detailItems.find(item=>item.label==='约定实习薪资').value,'0 元/月')
  assert.equal(vm.detailItems.find(item=>item.label==='专业是否对口').value,'否')
  vm.drawer.data.applicationType='EXEMPTION';assert.equal(vm.detailItems.find(item=>item.label==='提交时间').value,'2026-10-13 07:35')
  assert.equal(vm.drawer.data.submittedAt,raw)
})

test('实际筛选模板按身份批次重建搜索实例，旧组件卸载取消延迟查询',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/views/InternshipApplicationReviewView.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const script=fs.readFileSync(new URL('../src/components/common/display/AppSearchBox.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default','return')
  let serial=0;const timers=new Map(),child=new Function('setTimeout','clearTimeout',script)(fn=>{const id=++serial;timers.set(id,fn);return id},id=>timers.delete(id))
  async function instances(identity,batch){
    const {vm,store}=page();vm.ctx.ctxKey=identity;store.selectedBatchId=batch
    const seen=[],search={...child,setup(){seen.push(getCurrentInstance());return {}},render:()=>null}
    const components={ModulePageShell:{setup:(_,{slots})=>()=>h('main',slots.default?.())},AppSearchBox:search}
    for(const name of ['AppButton','AppSelect','ErrorState','LoadingState','DataTable','AppStatusTag','AppDescriptionList','AppFilePreview','AppAuditTrail','AppPermissionButton','AppConfirmDialog'])components[name]={render:()=>null}
    const descriptors=Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(vm)).filter(([key])=>!key.startsWith('$')))
    await renderToString(createSSRApp({components,setup:()=>Object.defineProperties({},descriptors),render:compile(template)}))
    return seen
  }
  const original=await instances('school-role-1','batch-1'),roleChanged=await instances('school-role-2','batch-1'),batchChanged=await instances('school-role-1','batch-2')
  assert.equal(original.length,3);assert.equal(new Set(original.map(instance=>instance.vnode.key)).size,3)
  for(let i=0;i<3;i++){
    assert.notEqual(original[i].vnode.key,roleChanged[i].vnode.key)
    assert.notEqual(original[i].vnode.key,batchChanged[i].vnode.key)
    original[i].proxy.onInput({target:{value:'旧范围输入'}})
    assert.equal(timers.size,1)
    child.beforeUnmount.call(original[i].proxy)
    assert.equal(timers.size,0)
  }
})

test('组合筛选、长编号、页码在刷新及详情返回时保留', () => {
  const query = { batchId, academicYear: '2026-2027', grade: '2024', collegeId: '9007199254740993002', majorId: '9007199254740993003',
    classId: '9007199254740993004', studentName: '合成学生', studentNo: '000000000000000001', exemptionType: 'HEALTH', type: 'EXEMPTION', status: 'ALL', page: '3' }
  const { vm } = page({}, query)
  vm.restoreLocation()
  assert.equal(vm.filters.classId, query.classId)
  assert.equal(vm.filters.studentNo, query.studentNo)
  assert.deepEqual(vm.backToList().query, { ...query, page: 3, keyword: undefined })
  assert.equal(vm.openDetail('9007199254740993009').query.classId, query.classId)
  vm.filters.grade = '2023'
  vm.reload()
  assert.equal(vm.page, 1)
  assert.equal(vm.listQuery().grade, '2023')
})

test('列表分页与导出共用已查询条件，未搜索草稿不改变导出', async () => {
  let listed, exported
  const { vm } = page({ getApplications: async params => { listed = params; return ok({ list: [], total: 0 }) },
    exportApplications: async params => { exported = params; return ok(true) } },
  { grade: '2024', studentNo: '0007', type: 'EXEMPTION', status: 'PENDING_REVIEW', keyword: '原查询' })
  vm.restoreLocation()
  vm.filters.studentNo = '未搜索内容'; vm.keyword = '未搜索关键词'
  await vm.load(); await vm.exportCurrent()
  const { page: ignoredPage, pageSize: ignoredSize, ...listFilters } = listed
  assert.deepEqual(exported, listFilters)
  assert.equal(exported.studentNo, '0007'); assert.equal(exported.keyword, '原查询')
  assert.equal(vm.openDetail('91').query.studentNo, '0007')
  assert.equal(vm.backToList().query.keyword, '原查询')
  let paged
  vm.$router.replace = to => { paged = to }
  vm.onPageChange(2)
  assert.equal(paged.query.studentNo, '0007'); assert.equal(paged.query.page, 2)
})

test('切换申请类型清除不适用的免实习类别，避免隐藏条件筛空', () => {
  const { vm } = page({}, { type: 'POSITION', exemptionType: 'HEALTH' })
  vm.restoreLocation()
  assert.equal(vm.filters.exemptionType, '')
  assert.equal(vm.requestFilters().exemptionType, undefined)
})

test('切换批次后迟到选项不能泄露前一批次组织，失败可明确重试', async () => {
  let release
  const pending = new Promise(resolve => { release = resolve })
  const { vm, store } = page({ getFilterOptions: async id => id === batchId ? pending : { code: 1, message: '筛选选项读取失败' } })
  const first = vm.loadFilterOptions()
  store.selectedBatchId = 'new'
  await vm.loadFilterOptions()
  release(ok({ ...emptyOptions(), colleges: [{ value: 'old', label: '旧学校院系' }] }))
  await first
  assert.deepEqual(vm.filterOptions.colleges, [])
  assert.equal(vm.optionsError, '筛选选项读取失败')
  assert.equal(vm.optionsLoading, false)
})

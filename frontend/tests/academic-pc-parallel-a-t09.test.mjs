import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { setImmediate } from 'node:timers'
import { ref, computed } from 'vue'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'

function batch(api, overrides = {}) {
  const file = fs.readFileSync(new URL('../src/modules/academicAffairs/components/ClassroomBatchWorkspace.vue', import.meta.url), 'utf8')
  const watches = [], emits = [], lifecycle = {}
  const props = { building: { buildingId: '1', floorCount: 1 }, mode: 'generate', initialBatchId: '', ...overrides }
  const script = file.match(/<script setup>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace(/^const props = defineProps.*$/m, '')
    .replace(/^const emit = defineEmits.*$/m, '')
    .replace(/^defineExpose.*$/m, '')
  const vm = new Function('ref', 'computed', 'watch', 'onMounted', 'onBeforeUnmount', 'props', 'emit', 'api', 'isDeniedResult', 'isConflictResult', 'isMissingResult', 'downloadClassroomFile', script + '\nreturn { rules, excluded, step, busy, error, preview, result, dirty, pendingBatch, invalidBatch, accept, confirm, queryResult, generate, recheck, upload, resume }')(
    ref, computed, (get, fn) => watches.push(fn), fn => { lifecycle.mount = fn }, fn => { lifecycle.unmount = fn }, props, (...e) => emits.push(e), api, results.isDeniedResult, results.isConflictResult, results.isMissingResult, () => {})
  return { ...vm, watches, emits, lifecycle, props }
}
const row = { line: 1, action: 'CREATE', row: { buildingCode: 'A', floorNo: 1, roomCode: '101', capacity: 60 } }
const preview = (id = 'batch1', fields = {}) => ({ batchNo: id, status: 'PREVIEW', items: [row], total: 1, createCount: 1, keepCount: 0, errorCount: 0, ...fields })
const success = (id = 'batch1') => ({ ...preview(id), status: 'SUCCESS', result: { batchNo: id, createdCount: 1, keptCount: 0, classroomIds: ['room1'], completedAt: '2026-09-08T12:00:00' } })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

function component(file, deps = {}, options = {}) {
  const storage = new Map()
  Object.defineProperty(globalThis, 'sessionStorage', {configurable:true,value:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}})
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/' + file, import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const names = [...source.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm)].flatMap(([, binding]) => binding.trim().startsWith('{') ? binding.replace(/[{}]/g, '').split(',').map(x => x.trim()).filter(Boolean) : [binding.trim()])
  const defaults = { ...results, ...flow, currentUserFromToken:()=>({tenantId:'1',userId:'2',currentRoleCode:'SCHOOL_ADMIN',activeContextId:'3'}), academicAffairsResourceApi:{commandReceipt:async(commandKey,operation)=>({code:0,data:{commandKey,operation,state:'UNRESOLVED',result:null}})}, matchPermission: (patterns, key) => patterns.includes('*') || patterns.includes(key), ...deps }
  const factory = new Function(...names, source.replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"]\s*$/gm, '').replace('export default', 'return'))(...names.map(name => defaults[name] ?? {}))
  const vm = { ...factory.data(), kind: 'CLASSROOM', ctx: { permissionPatterns: ['*'] }, $route: { query: {} }, $router: { replace: async () => {} }, ...options }
  Object.entries(factory.methods).forEach(([name, fn]) => { vm[name] = fn.bind(vm) })
  Object.entries(factory.computed || {}).forEach(([name, fn]) => Object.defineProperty(vm, name, { get: () => fn.call(vm) }))
  vm.readGate = flow.createAcademicRequestGate(() => JSON.stringify([vm.dateFrom,vm.dateTo,vm.$route?.fullPath]))
  vm.loadGate = flow.createAcademicRequestGate(() => JSON.stringify([vm.date,vm.kind]))
  return vm
}
const booking = (deps, options) => component('components/parallel-a/ResourceBookingWorkspace.vue', deps, options)
const ok = data => ({ code: 0, data })
const record = fields => ({ bookingId: '201', classroomId: '101', bookingDate: '2026-09-08', slotNo: 1, status: 'PENDING', ...fields })

test('T09 booking success reads same stable booking, resource and slot before receipt', async () => {
  const calls = []
  const vm = booking({ academicAffairsClassroomBookingApi: { book: async () => { calls.push('POST'); return ok(record()) }, list: async () => { calls.push('GET'); return ok({ list: [record()], total: 1 }) } } })
  vm.form = { resourceId: '101', bookingDate: '2026-09-08', slotNo: 1, purpose: '隔离验证' }; vm.load = async () => {}; await vm.submitBook()
  assert.deepEqual(calls, ['POST', 'GET']); assert.equal(vm.receipt.status, '待审核'); assert.equal(vm.pending, null)
})
test('T09 timeout without booking ID queries records once and never reissues application', async () => {
  let writes = 0, reads = 0
  const vm = booking({ academicAffairsClassroomBookingApi: { book: async () => { writes++; return { code: 503001, message: '超时' } } } })
  vm.form = { resourceId: '101', bookingDate: '2026-09-08', slotNo: 1, purpose: '隔离验证' }; vm.load = async () => { reads++ }; await vm.submitBook(); await vm.submitBook()
  assert.equal(writes, 1); assert.equal(reads, 1); assert.equal(vm.pending.id, ''); assert.equal(vm.receipt.pending, true)
})
test('T09 booking readback from another resource cannot produce success', async () => {
  const vm = booking({ academicAffairsClassroomBookingApi: { list: async () => ok({ list: [record({ classroomId: 'other' })], total: 1 }) } })
  await assert.rejects(vm.readRecord('201', vm.freezeRow(record()), () => true), /不一致/)
})
test('T09 view permission cannot review pending bookings', async () => {
  let writes = 0
  const vm = booking({ academicAffairsClassroomBookingApi: { review: async () => { writes++ } } }, { ctx: { permissionPatterns: ['academicAffairs.classroom.view'] } })
  vm.openReview(record(), 'APPROVE'); await vm.submitReview(); assert.equal(writes, 0); assert.equal(vm.review.visible, false)
})
test('T09 changed formal booking status preserves rejection reason and prevents POST', async () => {
  let writes = 0
  const vm = booking({ academicAffairsClassroomBookingApi: { list: async () => ok({ list: [record({ status: 'APPROVED' })], total: 1 }), review: async () => { writes++ } } })
  vm.load = async () => {}; vm.openReview(record(), 'REJECT'); vm.review.reason = '当前资源安排冲突'; await vm.submitReview()
  assert.equal(writes, 0); assert.equal(vm.review.reason, '当前资源安排冲突'); assert.match(vm.review.error, /事实已变化/)
})
test('T09 403 booking read clears resource, draft and receipt', () => {
  const vm = booking(); vm.resources = [{ classroomId: 'secret' }]; vm.form = { purpose: 'private' }; vm.receipt = {}; vm.failure({ status: 403, message: '无权访问' })
  assert.deepEqual(vm.resources, []); assert.deepEqual(vm.form, {}); assert.equal(vm.receipt, null)
})
test('T09 matrix never matches a same-name occupancy without a stable resource ID', () => {
  const vm = booking(); vm.occupancy = [{ resourceId: '', resourceLabel: '同名教室', slotNo: 1, source: 'SCHEDULE' }]
  assert.equal(vm.cell({ classroomId: '101', roomName: '同名教室', status: 'AVAILABLE', allowBorrow: true }, 1).label, '待核对·申请')
  assert.equal(vm.cell({ classroomId: '101', status: 'MAINTENANCE' }, 1).occupied, true)
})

test('T09 a known maintenance resource cannot be approved through methods or matrix', async () => {
  let writes=0
  const vm=booking({academicAffairsClassroomBookingApi:{review:async()=>{writes++;return ok(record({status:'APPROVED'}))}}})
  vm.resources=[{classroomId:'101',status:'MAINTENANCE'}];vm.occupancy=[{resourceId:'101',slotNo:1,source:'SCHEDULE'}]
  assert.equal(vm.cell(vm.resources[0],1).occupied,true);vm.openReview(record(),'APPROVE');await vm.submitReview()
  assert.equal(writes,0);assert.match(vm.review.error,/维修或停用/);assert.equal(vm.receipt,null)
})

test('T09 an apparently free resource still cannot approve without complete shared verification', async () => {
  let writes=0
  const vm=booking({academicAffairsClassroomBookingApi:{review:async()=>{writes++}}})
  vm.resources=[{classroomId:'101',status:'AVAILABLE'}];vm.occupancy=[];vm.openReview(record(),'APPROVE');await vm.submitReview()
  assert.equal(writes,0);assert.match(vm.review.error,/未开放借用/)
})

test('T09 safe rejection remains available while approval is blocked',async()=>{
  let writes=0
  const vm=booking({academicAffairsClassroomBookingApi:{list:async()=>ok({list:[record({status:writes?'REJECTED':'PENDING',reviewReason:writes?'该场地处于维修状态':''})],total:1}),review:async(id,action)=>{assert.equal(action,'REJECT');writes++;return ok(record({status:'REJECTED',reviewReason:'该场地处于维修状态'}))}}})
  vm.load=async()=>{};vm.openReview(record(),'REJECT');vm.review.reason='该场地处于维修状态';await vm.submitReview()
  assert.equal(writes,1);assert.equal(vm.receipt.status,'已驳回')
})

for(const [file,apiName,key] of [['AaLabResourceListView','academicAffairsLabApi','lab'],['AaEquipmentListView','academicAffairsEquipmentApi','equipment']]){
  test(`T09 ${key} view-only identity cannot create, update, delete or change status`,async()=>{
    let writes=0;const vm=component(`views/${file}.vue`,{[apiName]:{create:async()=>{writes++},update:async()=>{writes++},setStatus:async()=>{writes++},remove:async()=>{writes++}}},{ctx:{permissionPatterns:[`academicAffairs.${key}.view`]}})
    vm.form[key+'Code']='A';vm.form[key+'Name']='隔离';await vm.submitForm();vm.askDelete({[key+'Id']:'1'});await vm.onConfirm();vm.askStatus({[key+'Id']:'1'},'MAINTENANCE');await vm.onConfirm();assert.equal(writes,0)
  })
  test(`T09 ${key} conflict preserves form while 403 erases sensitive state`,async()=>{
    const vm=component(`views/${file}.vue`);vm.form[key+'Name']='未保存输入';vm.formVisible=true;vm.failure({code:409001,message:'已变化'},'formError');assert.equal(vm.form[key+'Name'],'未保存输入');assert.equal(vm.formVisible,true)
    vm.failure({status:403,message:'无权访问'},'formError');assert.equal(vm.form[key+'Name'],'');assert.equal(vm.formVisible,false);assert.equal(vm.receipt,null)
  })
  test(`T09 ${key} successful command only resolves after exact formal resource read`,async()=>{
    const calls=[],body={[key+'Code']:'A',[key+'Name']:'隔离',...(key==='lab'?{labType:'SKILL'}:{})},row={...body,[key+'Id']:'1',status:'AVAILABLE',statusLabel:'可用'}
    const vm=component(`views/${file}.vue`,{[apiName]:{create:async()=>{calls.push('POST');return ok(row)},get:async()=>{calls.push('GET');return ok(row)}}});vm.form=body;vm.load=async()=>{};await vm.submitForm();assert.deepEqual(calls,['POST','GET']);assert.equal(vm.receipt.pending,false)
  })
}

test('T09 maintenance completion reads actual resource state and does not assume restored availability',async()=>{
  const row={repairId:'1',resourceKind:'CLASSROOM',resourceId:'101',status:'DONE',resolvedAt:'2026-09-08T12:00:00'}
  const vm=component('views/AaResourceRepairView.vue',{academicAffairsResourceApi:{repairs:async()=>ok({list:[row],total:1})},academicAffairsApi:{getClassroom:async()=>ok({classroomId:'101',status:'MAINTENANCE',statusLabel:'维修中'})}})
  vm.pendingResult={id:'1',row,expected:'DONE'};vm.load=async()=>{};await vm.readResult(()=>true)
  assert.equal(vm.receipt.status,'已完成');assert.match(vm.receipt.next,/资源当前状态：维修中/);assert.equal(vm.receipt.time,row.resolvedAt)
})

test('T09 repair read permission never grants reporting or completion',async()=>{
  let writes=0;const vm=component('views/AaResourceRepairView.vue',{academicAffairsResourceApi:{reportRepair:async()=>{writes++}}},{ctx:{permissionPatterns:['academicAffairs.resourceRepair.view']}})
  vm.form={resourceKind:'CLASSROOM',resourceId:'1',faultDesc:'故障'};await vm.submitReport();vm.rows=[{repairId:'1',status:'REPORTED'}];vm.complete('1');await vm.onNoteConfirm();assert.equal(writes,0)
})

test('T09 denied stats cannot retain previous metrics',async()=>{
  const vm=component('views/AaResourceStatsView.vue',{academicAffairsResourceApi:{stats:async()=>({status:403,message:'范围已变化'})}});vm.data={classroom:{total:99}};await vm.load();assert.equal(vm.data,null);assert.match(vm.error,/范围已变化/)
})

test('AA-220 unknown historical lab type is disclosed and cannot be silently written back',async()=>{
  let writes=0
  const vm=component('views/AaLabResourceListView.vue',{academicAffairsLabApi:{update:async()=>{writes++}}})
  vm.editingId='1';vm.form={labCode:'YK-LAB-AI-01',labName:'人工智能综合实训室',labType:'AI_COMPUTING'}
  assert.match(vm.labTypeLabel(vm.form),/历史类型待核对/)
  await vm.submitForm()
  assert.equal(writes,0);assert.match(vm.formError,/正式字典/)
})

test('AA-222 occupancy limits a large formal result to one visible page',async()=>{
  const items=Array.from({length:45},(_,index)=>({source:'SCHEDULE',scheduleItemId:String(index+1),batchId:'3',termId:'4',classId:'5',taskId:'6',resourceKind:'CLASSROOM',resourceId:String(100+index),logicalDate:'2026-09-09',calendarSource:'NORMAL',slotNo:1}))
  const vm=component('views/AaResourceOccupancyView.vue',{academicAffairsResourceApi:{occupancy:async()=>ok({date:'2026-09-09',coverage:{classroomSchedule:'FORMAL_SCOPE_HEAD_CALENDAR',labSchedule:'EXPLICIT_ROOM_BINDING',unmappedScheduleItems:0,unmappedLabs:0,unmappedLabBookings:0},items})}})
  vm.$route={path:'/admin/academic-affairs/resources/occupancy',fullPath:'/admin/academic-affairs/resources/occupancy?date=2026-09-09',query:{date:'2026-09-09'}};vm.queryDate='2026-09-09'
  await vm.load();assert.equal(vm.pagination.total,45);assert.equal(vm.pagedRows.length,20)
})

test('AA-223 conflict paging keeps every source pair while bounding the rendered rows',async()=>{
  const items=Array.from({length:41},(_,index)=>({bookingId:String(100+index),scheduleItemId:String(200+index),batchId:'3',termId:'4',classId:'5',taskId:'6',resourceKind:'CLASSROOM',resourceId:String(300+index),classroomId:String(300+index),date:'2026-09-09',logicalDate:'2026-09-09',calendarSource:'NORMAL',slotNo:1}))
  const vm=component('views/AaResourceConflictView.vue',{academicAffairsResourceApi:{conflicts:async()=>ok({dateFrom:'2026-09-09',dateTo:'2026-09-09',coverage:{classroomSchedule:'FORMAL_SCOPE_HEAD_CALENDAR',labSchedule:'EXPLICIT_ROOM_BINDING',unmappedScheduleItems:0,unmappedLabs:0,unmappedLabBookings:0},items})}})
  vm.$route={path:'/admin/academic-affairs/resources/conflicts',fullPath:'/admin/academic-affairs/resources/conflicts?date=2026-09-09',query:{date:'2026-09-09'}};vm.dateFrom='2026-09-09'
  await vm.load();assert.equal(vm.pagination.total,41);assert.equal(vm.pagedRows.length,20);assert.equal(new Set(vm.rows.map(row=>row._rowKey)).size,41)
})

test('AA-224 repair board maps formal states into the three designed lanes',()=>{
  const vm=component('views/AaResourceRepairView.vue')
  vm.rows=[{repairId:'1',status:'REPORTED'},{repairId:'2',status:'IN_REPAIR'},{repairId:'3',status:'DONE'},{repairId:'4',status:'CANCELLED'}]
  assert.deepEqual(vm.repairGroups.map(group=>[group.title,group.rows.length]),[['待领取',1],['处理中',1],['已关闭',2]])
  assert.match(vm.timelineIssue({createdAt:'2026-08-31T00:28:26Z',resolvedAt:'2026-08-27T10:30:00Z'}),/早于报修时间/)
})

test('AA-225 statistics drill-down uses the formal resource routes',()=>{
  let path='';const vm=component('views/AaResourceStatsView.vue',{},{$router:{push:value=>{path=value}}})
  vm.drill('/admin/academic-affairs/resources/occupancy');assert.equal(path,'/admin/academic-affairs/resources/occupancy')
})

test('T09 old conflict range response cannot overwrite a newer range',async()=>{
  const first=deferred()
  const payload=(date,bookingId)=>ok({dateFrom:date,dateTo:date,total:1,coverage:{classroomSchedule:'FORMAL_SCOPE_HEAD_CALENDAR',labSchedule:'EXPLICIT_ROOM_BINDING',unmappedScheduleItems:0,unmappedLabs:0,unmappedLabBookings:0},items:[{bookingId,scheduleItemId:'2',batchId:'3',termId:'4',resourceId:'101',resourceKind:'CLASSROOM',classroomId:'101',date,logicalDate:date,calendarSource:'NORMAL',slotNo:1}]})
  const vm=component('views/AaResourceConflictView.vue',{academicAffairsResourceApi:{conflicts:from=>from==='2026-09-08'?first.promise:Promise.resolve(payload(from,'new'))}})
  vm.$nextTick=async()=>{}
  vm.dateFrom='2026-09-08';vm.$route.query={date:vm.dateFrom};const old=vm.load();vm.dateFrom='2026-09-09';vm.$route.query={date:vm.dateFrom};await vm.load();first.resolve(payload('2026-09-08','old'));await old;assert.equal(vm.rows[0].bookingId,'new')
})

test('T09 numeric floor including zero is safely encoded in classroom query', async () => {
  let query
  const vm = component('views/AaClassroomListView.vue', {}, { $router: { replace: async value => { query = value.query } } })
  vm.filters.floorNo = 2; await vm.updateQuery(); assert.equal(query.floorNo, '2')
  vm.filters.floorNo = 0; await vm.updateQuery(); assert.equal(query.floorNo, '0')
})
test('T09 classroom denied response keeps its classification and clears editor and receipt', async () => {
  const vm = component('views/AaClassroomListView.vue', { academicAffairsApi: { listClassrooms: async () => ({ code: 403001, message: '范围已变化' }) } })
  vm.formVisible = true; vm.form.roomCode = 'secret'; vm.receipt = {}; await vm.load()
  assert.equal(vm.formVisible, false); assert.equal(vm.form.roomCode, ''); assert.equal(vm.receipt, null); assert.match(vm.error, /已清除/)
})

test('T09 confirm uses precheck, one command, and exact formal batch readback', async () => {
  const calls = []; let reads = 0
  const vm = batch({ batch: async id => { calls.push('GET:' + id); return ++reads === 1 ? preview() : success() }, confirm: async id => { calls.push('POST:' + id); return {} } })
  vm.accept(preview()); await vm.confirm()
  assert.deepEqual(calls, ['GET:batch1', 'POST:batch1', 'GET:batch1']); assert.equal(vm.step.value, 3); assert.equal(vm.result.value.completedAt, '2026-09-08T12:00:00')
})
test('T09 lost confirm response reads formal result without replay', async () => {
  let reads = 0, writes = 0
  const vm = batch({ batch: async () => ++reads === 1 ? preview() : success(), confirm: async () => { writes++; throw new Error('超时') } })
  vm.accept(preview()); await vm.confirm(); assert.equal(writes, 1); assert.equal(vm.step.value, 3)
})
test('T09 uncertain result stays pending and repeat clicks only query', async () => {
  let writes = 0
  const vm = batch({ batch: async () => preview(), confirm: async () => { writes++; throw new Error('超时') } })
  vm.accept(preview()); await vm.confirm(); await vm.confirm(); await vm.queryResult()
  assert.equal(writes, 1); assert.equal(vm.pendingBatch.value, 'batch1'); assert.equal(vm.result.value, null)
  await vm.generate(); assert.match(vm.error.value, /先查询/)
})
test('T09 successful existing batch is idempotently read without a new command', async () => {
  let writes = 0
  const vm = batch({ batch: async () => success(), confirm: async () => { writes++ } }); vm.accept(preview()); await vm.confirm()
  assert.equal(writes, 0); assert.equal(vm.step.value, 3)
})
test('T09 all KEEP rows require no command and use original rows when rechecked', async () => {
  let writes = 0, sent
  const keep = { ...row, action: 'KEEP', existing: { roomCode: 'original' } }
  const vm = batch({ confirm: async () => { writes++ }, preview: async rows => { sent = rows; return preview() } })
  vm.accept(preview('batch1', { items: [keep], createCount: 0, keepCount: 1 })); vm.preview.value.items[0].edit.roomCode = 'malicious-edit'
  await vm.confirm(); assert.equal(writes, 0); await vm.recheck(); assert.equal(sent[0].roomCode, '101')
})
test('T09 error rows, dirty rows, and a mismatched batch never submit', async () => {
  let writes = 0
  const vm = batch({ batch: async () => preview('other'), confirm: async () => { writes++ } })
  vm.accept(preview('batch1', { errorCount: 1 })); await vm.confirm()
  vm.accept(preview()); vm.dirty.value = true; await vm.confirm()
  vm.dirty.value = false; await vm.confirm(); assert.equal(writes, 0); assert.match(vm.error.value, /不能入库/)
})
test('T09 expired precheck preserves edits and requires fresh preview', async () => {
  let writes = 0
  const vm = batch({ batch: async () => { throw { status: 404, message: '批次已过期' } }, confirm: async () => { writes++ } })
  vm.accept(preview()); await vm.confirm(); assert.equal(writes, 0); assert.equal(vm.invalidBatch.value, true); assert.equal(vm.dirty.value, true); assert.equal(vm.preview.value.items[0].edit.roomCode, '101')
})
test('T09 concurrency conflict retains data but invalidates authorization', async () => {
  const vm = batch({ batch: async () => preview(), confirm: async () => { throw { bizCode: 'DATA_CONFLICT', message: '楼栋已变化' } } })
  vm.accept(preview()); await vm.confirm(); assert.equal(vm.invalidBatch.value, true); assert.equal(vm.pendingBatch.value, ''); assert.equal(vm.preview.value.batchNo, 'batch1')
})
test('T09 403 clears previous batch and receipt', async () => {
  const vm = batch({ batch: async () => { throw { status: 403, message: '归属变化' } } })
  vm.accept(preview()); vm.result.value = { sensitive: true }; await vm.confirm()
  assert.equal(vm.preview.value, null); assert.equal(vm.result.value, null); assert.equal(vm.busy.value, false)
})
test('T09 switching batch during precheck prevents old batch confirmation', async () => {
  const first = deferred(); let writes = 0
  const vm = batch({ batch: id => id === 'batch1' ? first.promise : Promise.resolve(preview('batch2')), confirm: async () => { writes++ } })
  vm.accept(preview()); const old = vm.confirm(); vm.watches[0]('batch2'); await new Promise(r => setImmediate(r)); first.resolve(preview()); await old
  assert.equal(writes, 0); assert.equal(vm.preview.value.batchNo, 'batch2')
})
test('T09 malformed formal receipt cannot display completed', async () => {
  let reads = 0
  const vm = batch({ batch: async () => ++reads === 1 ? preview() : { ...success(), result: { ...success().result, batchNo: 'other' } }, confirm: async () => ({}) })
  vm.accept(preview()); await vm.confirm(); assert.equal(vm.step.value, 2); assert.equal(vm.pendingBatch.value, 'batch1'); assert.match(vm.error.value, /不一致/)
})
test('T09 frontend rejects over-limit generation and invalid import before API calls', async () => {
  let requests = 0
  const vm = batch({ generate: async () => { requests++ }, upload: async () => { requests++ } })
  vm.rules.value.roomsPerFloor = 1001; await vm.generate()
  await vm.upload({ target: { files: [{ name: 'data.csv', size: 100 }] } }); await vm.upload({ target: { files: [{ name: 'data.xlsx', size: 6 * 1024 * 1024 }] } })
  assert.equal(requests, 0)
})

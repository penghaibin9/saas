import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { formatDateTime } from '../src/utils/dateUtils.js'

function view(name, api) {
  const source = readFileSync(new URL(`../src/views/admin/orientation/${name}.vue`, import.meta.url), 'utf8')
  const names = []
  const script = parse(source).descriptor.script.content
    .replace(/import (\w+) from [^\n]+/g, (_, name) => { names.push(name); return '' })
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => {
      names.push(...list.split(',').map(s => s.trim())); return ''
    }).replace('export default', 'return')
  const errors = []
  const successes = []
  const component = new Function('api', ...names, script)(api, ...names.map(n => n === 'toast'
    ? { success(message) { successes.push(message) }, error(message) { errors.push(message) } } : n === 'formatDateTime' ? formatDateTime : {}))
  const vm = component.data()
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = fn.bind(vm)
  vm.load = async () => { vm.reloaded = true }
  vm.confirmRow = { id: '63055', version: 7 }
  vm.confirmVisible = true
  return { vm, errors, successes, component }
}

test('stopped orientation shows restoration guidance and cannot reopen account activation', () => {
  const { vm } = view('OrientationQualificationView', {})
  vm.perms = { 'orientation.identity.activate': { allowed: true }, 'orientation.enrollment.finalize': { allowed: true } }
  for (const stage of ['CANCELLED', 'NO_SHOW', 'DEFERRED']) {
    const row = { id: '1', stage, reportStatus: 'NO_SHOW', verdict: 'NOT_QUALIFIED' }
    assert.notEqual(vm.qualificationText(row.verdict, stage), '仍需补办')
    assert.match(vm.blockerText(row), /恢复/)
    assert.equal(vm.rowActions(row).some(action => action.key === 'activate'), false)
    assert.equal(vm.rowActions(row).find(action => action.key === 'disposition').label, '恢复或调整报到')
    vm.onRowAction('activate', row)
    assert.equal(vm.activateVisible, false)
  }
  assert.equal(vm.qualificationText('NOT_QUALIFIED', 'ADMITTED'), '仍需补办')
  assert.equal(vm.rowActions({ stage: 'ADMITTED', reportStatus: 'NOT_REPORTED' }).some(action => action.key === 'activate'), true)
})

test('student detail distinguishes stopped history from an actionable welcome record', () => {
  const { vm, component } = view('OrientationStudentDetailView', {})
  for (const stage of ['CANCELLED', 'NO_SHOW', 'DEFERRED']) {
    vm.detail = { student: { stage, recordStatus: 'ACTIVE' } }
    assert.match(component.computed.arrangementHint.call(vm), /恢复/)
    assert.equal(component.computed.canContinue.call(vm), false)
  }
  vm.detail.student.stage = 'ADMITTED'
  assert.equal(component.computed.canContinue.call(vm), true)
  vm.detail.student.recordStatus = 'VOIDED'
  assert.equal(component.computed.canContinue.call(vm), false)
})

test('student detail ignores previous students late data and serializes review actions', async () => {
  const pending = new Map()
  const {vm,component,successes} = view('OrientationStudentDetailView', {
    getOrientationContext: async()=>({code:0,data:{}}),
    getStatusOptions: async()=>({code:0,data:{}}),
    getOrientationStudentDetail: id=>new Promise(resolve=>pending.set(id,resolve))
  })
  vm.load = component.methods.load.bind(vm)
  vm.$route={params:{studentId:'1'}}
  const first = vm.load()
  vm.$route.params.studentId='2'
  const second = vm.load()
  pending.get('2')({code:0,data:{student:{id:'2',version:5}}})
  await second
  pending.get('1')({code:0,data:{student:{id:'1',version:1}}})
  await first
  assert.equal(vm.detail.student.id,'2')
  let complete, writes=0
  const action=()=>{ writes++; return new Promise(resolve=>{complete=resolve}) }
  const reviewing=vm.runApi(action,'材料已通过')
  await vm.runApi(action,'材料已通过')
  assert.equal(writes,1)
  vm.detailSerial++
  complete({code:0})
  await reviewing
  assert.deepEqual(successes,[])
  assert.equal(vm.submitting,false)
})

test('student detail green-channel actions send the displayed application version', async () => {
  const calls = []
  const api = Object.fromEntries(['approveGreenChannel', 'returnGreenChannel', 'rejectGreenChannel'].map(name => [name, async (...args) => { calls.push([name, ...args]); return {code:0} }]))
  const {vm} = view('OrientationStudentDetailView', api)
  vm.runApi = fn => fn()
  vm.openReason = conf => { vm.reasonAction = conf.handler }
  const application = {id:'9007199254740993', version:7}
  vm.approveGreen(application)
  for (const action of ['returnGreen','rejectGreen']) {
    vm[action](application)
    await vm.reasonAction({reason:'请补充申请材料'})
  }
  assert.equal(calls.length,3)
  for (const [,id,body] of calls) { assert.equal(id,application.id); assert.equal(body.expectedVersion,7) }
  assert.equal(calls[1][2].reason,'请补充申请材料')
})

test('material review sends displayed versions and preserves stale return input', async () => {
  const calls = []
  const api = Object.fromEntries(['approveOrientationMaterial', 'returnOrientationMaterial'].map(name => [name, async (...args) => { calls.push([name, ...args]); return {code:409, message:'材料已变化，请刷新核对'} }]))
  const {vm} = view('OrientationStudentDetailView', api)
  vm.runApi = fn => fn(); vm.openReason = conf => { vm.reasonAction = conf.handler }
  const material = {id:'9007199254740993',version:4,status:'UPLOADED'}
  vm.approveMaterial(material); vm.returnMaterial(material); await vm.reasonAction({reason:'请补充清晰材料'})
  for (const [,id,body] of calls) { assert.equal(id,material.id); assert.equal(body.expectedVersion,4) }
  const queue = view('OrientationMaterialReviewView', api).vm
  queue.viewTarget = material; queue.returnVisible = true
  await queue.onReturnConfirm({reason:'请补充清晰材料'})
  assert.equal(queue.returnVisible,true)
  assert.equal(queue.viewTarget.version,4)
  assert.equal(queue.reloaded,undefined)
})

test('batch review retains selected versions and reports partial completion without retrying writes', async () => {
  const calls = []
  const {vm} = view('OrientationMaterialReviewView', {batchReviewOrientationMaterials: async (...args) => {
    calls.push(args); return {code:409, message:'已完成1份，其余请刷新核对',data:{completedIds:['1']}}
  }})
  vm.rows=[{id:'1',version:2},{id:'2',version:8}]; vm.selected=['1','2']
  vm.onBatch('batchReturn')
  vm.rows[1].version=9
  await vm.onBatchReturnConfirm({reason:'材料照片需要补充'})
  assert.deepEqual(calls[0][0],[{id:'1',version:2},{id:'2',version:8}])
  assert.equal(calls[0][1].pass,false)
  assert.equal(calls[0][1].reason,'材料照片需要补充')
  assert.equal(calls[0][1].shouldContinue(),true)
  assert.equal(vm.batchReturnVisible,true)
  assert.deepEqual(vm.batchTargets,[{id:'2',version:8}])
  assert.deepEqual(vm.selected,['2'])
  assert.match(vm.batchError,/已完成1份/)
})

test('material context change closes old dialogs and ignores a late batch result', async () => {
  let complete, options
  const {vm} = view('OrientationMaterialReviewView', {batchReviewOrientationMaterials: async (_rows, opts) => {
    options = opts
    return new Promise(resolve => { complete = resolve })
  }})
  vm.batchTargets=[{id:'1',version:2}]; vm.batchApproveVisible=true
  const pending = vm.reviewBatch(true)
  vm.changeContext()
  assert.equal(options.shouldContinue(),false)
  assert.equal(vm.batchApproveVisible,false)
  assert.equal(vm.viewTarget,null)
  complete({code:409,message:'旧对象的响应',data:{completedIds:[]}})
  await pending
  assert.equal(vm.batchError,'')
  assert.deepEqual(vm.batchTargets,[])
})

for (const [name, mode, method] of [
  ['OrientationVerifyView', 'pass', 'verifyOrientationStudent'],
  ['OrientationVerifyView', 'fail', 'verifyOrientationStudent'],
  ['OrientationGreenChannelView', 'return', 'returnGreenChannel'],
  ['OrientationGreenChannelView', 'reject', 'rejectGreenChannel'],
  ['OrientationBatchListView', 'void', 'voidOrientationBatch']
]) {
  test(`${name} ${mode}: dialog object sends a string reason and prevents duplicate writes`, async () => {
    let complete
    const calls = []
    const { vm, successes } = view(name, { [method]: (...args) => {
      calls.push(args); return new Promise(resolve => { complete = resolve })
    } })
    vm.confirmMode = mode
    const event = { reason: mode === 'pass' ? '' : '请核对填写的信息', notify: true }
    const first = vm.onConfirm(event)
    await vm.onConfirm(event)
    assert.equal(calls.length, 1)
    assert.equal(calls[0][0], '63055')
    assert.equal(mode === 'void' ? calls[0][1] : calls[0][1].reason, event.reason)
    if (name === 'OrientationVerifyView') {
      assert.equal(calls[0][1].passed, mode === 'pass')
      assert.equal(calls[0][1].expectedVersion, 7)
    }
    if (name === 'OrientationGreenChannelView') assert.equal(calls[0][1].expectedVersion, 7)
    assert.equal(vm.confirmSubmitting, true)
    complete({ code: 0 })
    await first
    assert.equal(vm.confirmSubmitting, false)
    assert.equal(vm.confirmVisible, false)
    assert.equal(vm.reloaded, true)
    if (name === 'OrientationVerifyView') {
      assert.deepEqual(successes, [mode === 'pass' ? '信息核验已通过' : '已退回学生补正，原因已记录'])
    }
  })

  test(`${name} ${mode}: failure retains dialog and permits deliberate retry`, async () => {
    let attempts = 0
    const { vm, errors } = view(name, { [method]: async () => {
      attempts++
      if (attempts === 1) throw new Error('网络连接失败')
      return { code: 0 }
    } })
    vm.confirmMode = mode
    const event = { reason: '请核对填写的信息', notify: true }
    await vm.onConfirm(event)
    assert.equal(vm.confirmVisible, true)
    assert.equal(vm.confirmSubmitting, false)
    assert.equal(vm.reloaded, undefined)
    assert.deepEqual(errors, ['网络连接失败'])
    assert.equal(event.reason, '请核对填写的信息')
    await vm.onConfirm(event)
    assert.equal(attempts, 2)
    assert.equal(vm.confirmVisible, false)
  })
}

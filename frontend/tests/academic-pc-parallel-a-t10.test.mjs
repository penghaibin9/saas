import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const ok = data => ({ code: 0, data })

function mount(api = {}) {
  const file = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleMaintainView.vue', import.meta.url), 'utf8')
  const script = file.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'return')
  const componentNames = ['ModulePageShell', 'LoadingState', 'AppButton', 'AppSectionCard', 'AppConfirmDialog', 'AppInlineAlert', 'AppSelect', 'AppClassPicker', 'AppClassroomPicker', 'AppStatusTag', 'AaAuthoritativeImportDrawer', 'AaScheduleGrid', 'AaOperationReceipt', 'AaScheduleStageRail']
  const factory = new Function(
    'academicAffairsApi', 'SCHEDULE_BATCH_STATUS', 'academicFileExchangeApi', 'toast', 'academicRouteState', 'createAcademicRequestGate', 'routeScalar', 'isDeniedResult', 'isConflictResult', 'scheduleTruthPresentation', 'readAllPages', ...componentNames, script
  )(
    api, { DRAFT: '草稿' }, {}, { error() {}, success() {}, info() {} }, () => ({}), () => ({ begin: () => () => true, invalidate() {} }), value => Array.isArray(value) ? value[0] : (value ?? ''),
    result => String(result?.code || '').startsWith('403'), result => String(result?.code || '').startsWith('409'), () => ({}), async () => [], ...componentNames.map(() => ({}))
  )
  const vm = {
    ...factory.data(),
    ctx: { currentRole: {}, dataScope: {} },
    $route: { params: { batchId: 'B1' }, query: { classId: 'CL1' }, fullPath: '/schedule/B1/edit?classId=CL1', path: '/schedule/B1/edit' },
    $router: { replace: async () => {} },
    $nextTick: async () => {},
    academicFlow: null
  }
  vm.taskGate = { begin: () => () => true, invalidate() {} }
  vm.classGate = { begin: () => () => true, invalidate() {} }
  vm.moveGate = { begin: () => () => true, invalidate() {} }
  Object.entries(factory.methods).forEach(([name, fn]) => { vm[name] = fn.bind(vm) })
  Object.entries(factory.computed || {}).forEach(([name, fn]) => Object.defineProperty(vm, name, { get: () => fn.call(vm) }))
  return vm
}

function ready(vm) {
  vm.routeBatchId = 'B1'
  vm.scheduleBatch = { status: 'DRAFT' }
  vm.classId = 'CL1'
  vm.readyTasks = [{ taskId: 'T1', classId: 'CL1', courseName: 'PLC应用基础' }]
  vm.add = { visible: true, submitting: false, taskId: 'T1', weekday: 1, slotNo: 2, weekParity: 'ALL', classroom: 'B201', startWeek: 1, endWeek: 18 }
  vm.preflight.result = { allowed: true }
}

test('T10 scheduling console exposes all five formerly missing workspaces as real tabs', () => {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaSchedulingConsoleView.vue', import.meta.url), 'utf8')
  for (const label of ['教室可用时间', '导入排课结果', '排课结果', '排课调整', '排课规则']) assert.match(source, new RegExp(label))
  assert.match(source, /AaResourceOccupancyView/)
  assert.match(source, /AaAuthoritativeImportDrawer/)
})

test('T10 schedule add shows success only after the formal class schedule contains the target slot', async () => {
  let writes = 0
  const vm = mount({ addScheduleItem: async () => { writes += 1; return ok({ itemId: 'I1', taskId: 'T1', batchId: 'B1', weekday: 1, slotNo: 2 }) } })
  ready(vm)
  vm.loadClass = async () => { vm.items = [{ itemId: 'I1', taskId: 'T1', batchId: 'B1', classId: 'CL1', weekday: 1, slotNo: 2, updatedAt: '2026-09-08T12:00:00' }] }
  await vm.doAdd()
  assert.equal(writes, 1)
  assert.equal(vm.receipt.pending, false)
  assert.equal(vm.receipt.status, '周1第2节')
})

test('T10 uncertain schedule command is read once and never automatically replayed', async () => {
  let writes = 0, reads = 0
  const vm = mount({ addScheduleItem: async () => { writes += 1; return { code: 503001, message: '超时' } } })
  ready(vm)
  vm.loadClass = async () => { reads += 1; vm.items = [] }
  await vm.doAdd()
  vm.add.visible = true
  await vm.doAdd()
  assert.equal(writes, 1)
  assert.equal(reads, 1)
  assert.equal(vm.receipt.pending, true)
  assert.match(vm.receipt.next, /不会自动重复排课/)
})

test('T10 409 preserves the frozen scheduling input and invalidates old preflight', async () => {
  const vm = mount({ addScheduleItem: async () => ({ code: 409001, message: '课位已被占用' }) })
  ready(vm)
  await vm.doAdd()
  assert.equal(vm.add.visible, true)
  assert.equal(vm.add.taskId, 'T1')
  assert.equal(vm.preflight.result, null)
  assert.match(vm.lastConflict, /占用/)
})

test('T10 403 removes stale schedule facts and receipt', async () => {
  const vm = mount({ addScheduleItem: async () => ({ code: 403001, message: '范围变化' }) })
  ready(vm); vm.items = [{ secret: true }]; vm.receipt = { secret: true }
  await vm.doAdd()
  assert.deepEqual(vm.items, [])
  assert.deepEqual(vm.readyTasks, [])
  assert.equal(vm.receipt, null)
  assert.match(vm.taskLoadError, /范围变化/)
})

test('T10 a pending schedule becomes confirmed through a later read without another POST', () => {
  const vm = mount()
  ready(vm)
  vm.pendingWrite = { itemId: 'I1', taskId: 'T1', batchId: 'B1', classId: 'CL1', weekday: 1, slotNo: 2, courseName: 'PLC应用基础', identity: vm.identityKey, acknowledged: true }
  vm.receipt = { pending: true }
  vm.items = [{ itemId: 'I1', taskId: 'T1', batchId: 'B1', classId: 'CL1', weekday: 1, slotNo: 2 }]
  vm.reconcilePendingWrite()
  assert.equal(vm.pendingWrite, null)
  assert.equal(vm.receipt.pending, false)
})

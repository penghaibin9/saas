import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormAllocationView.vue', import.meta.url), 'utf8')
function view(api = {}, resources = {}) {
  const names = []
  const script = parse(source).descriptor.script.content.replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => {
    names.push(...list.split(',').map(s => s.trim().split(/\s+as\s+/).at(-1)))
    return ''
  }).replace('export default', 'return')
  const component = new Function(...names, script)(...names.map(n => n === 'studentAffairsApi' ? api : n === 'resourceApi' ? resources : n === 'canCode' ? () => true : {}))
  const v = component.data()
  for (const [k, fn] of Object.entries(component.methods)) v[k] = fn.bind(v)
  for (const [k, fn] of Object.entries(component.computed)) Object.defineProperty(v, k, { get: fn.bind(v) })
  return v
}
const detail = () => ({ batch: { status: 'DRAFT', mode: 'ADMIN_AUTO', resourceScope: {} }, candidates: [{ studentId: '1', studentName: '张同学', studentNo: '001' }, { studentId: '2', studentName: '李同学', studentNo: '002' }], items: [{ studentId: '1', studentName: '张同学', studentNo: '001', status: 'PROPOSED', bedId: '10' }], missingIdentityCount: 1 })

test('draft review counts unresolved students and gates publishing on generated proposals', () => {
  const v = view(); v.detail = detail()
  assert.equal(v.proposedCount, 1)
  assert.equal(v.unresolvedCount, 2)
  assert.equal(v.publishReady, false)
  v.drySummary = { proposed: 1 }; assert.equal(v.publishReady, true)
  assert.match(v.publishMessage, /2 项尚未解决/)
  v.detail.items[0].status = 'CONFLICT'; assert.equal(v.publishReady, false)
  v.itemFilter = 'UNASSIGNED'; assert.equal(v.filteredItems.length, 2)
  v.searchText = '002'; assert.equal(v.filteredItems.length, 1)
})
test('late plan detail cannot replace newly selected plan or inherit its dry-run summary', async () => {
  const pending = {}; const v = view({ getDormAllocationBatch: id => new Promise(resolve => pending[id] = resolve) })
  const a = v.loadDetail('a'); const b = v.loadDetail('b')
  pending.b({ code: 0, data: detail() }); await b
  pending.a({ code: 0, data: { batch: { name: 'old', rules: { _dryRun: { proposed: 9 } } } } }); await a
  assert.equal(v.detail.batch.name, undefined); assert.equal(v.drySummary, null)
})
test('manual bed selection excludes occupied, locked and already proposed beds; conflict preserves selection', async () => {
  const v = view({ manualAssignDorm: async () => ({ code: 1, message: '该床位已被占用' }) })
  v.detail = detail(); v.openManual(v.detail.candidates[1]); v.manual.bedId = '11'
  assert.equal(v.bedAvailable({ bedId: '10', status: 'VACANT' }), false)
  assert.equal(v.bedAvailable({ bedId: '11', status: 'LOCKED' }), false)
  assert.equal(v.bedAvailable({ bedId: '11', status: 'VACANT' }), true)
  await v.manualAssign()
  assert.equal(v.manualVisible, true); assert.equal(v.manual.bedId, '11'); assert.match(v.manualError, /占用/)
})
test('student confirmation remains reserved until canonical housing reports actual check-in', () => {
  const v = view(); v.detail = detail(); v.detail.items[0].status = 'CONFIRMED'
  v.detail.items[0].housing = { housingStatus: 'RESERVED' }
  assert.equal(v.reservedCount, 1); assert.equal(v.activeCount, 0)
  v.detail.items[0].housing.housingStatus = 'ACTIVE'
  assert.equal(v.reservedCount, 0); assert.equal(v.activeCount, 1)
})

test('plan creation preserves large building identifiers exactly', async () => {
  let received
  const v = view({ createDormAllocationBatch: async payload => {
    received = payload
    return { code: 0, data: { batchId: '3' } }
  } })
  Object.assign(v.form, { name: 'New intake', orientationBatchId: '5', buildingIds: ['9007199254740993'] })
  v.load = async () => {}
  await v.createBatch()
  assert.deepEqual(received.resourceScope.buildingIds, ['9007199254740993'])
})

test('large plan review keeps every student and out-of-scope existing assignment once', () => {
  const v = view()
  v.detail = {
    batch: {},
    candidates: Array.from({ length: 5000 }, (_, i) => ({ studentId: String(i + 1) })),
    items: [{ studentId: 1, status: 'PROPOSED' }, { studentId: '5001', status: 'CONFLICT' }]
  }
  assert.equal(v.allItems.length, 5001)
  assert.equal(v.allItems[0].status, 'PROPOSED')
  assert.equal(v.allItems.at(-1).status, 'CONFLICT')
  assert.equal(new Set(v.allItems.map(row => String(row.studentId))).size, 5001)
})

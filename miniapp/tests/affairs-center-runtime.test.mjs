import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/student/affairs/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function mount(api = {}, sdk = {}, student = {}) {
  let generation = 1
  const notices = []
  const component = new Function('affairsContractApi', 'fileSdk', 'studentApi', 'currentSessionGeneration', 'normalizeError', 'toast', 'go', script)(api, sdk, student, () => generation, e => ({ text: e.message }), s => notices.push(s), () => {})
  const vm = { ...component.data(), ...component.methods, $nextTick: fn => fn() }
  return { vm, component, notices, switchAccount: () => { generation++ } }
}

test('material rows and overview ignore responses from a signed-out account', async () => {
  const pending = deferred()
  const { vm, switchAccount } = mount({ getMyMaterialRequirements: () => pending.promise }, {}, {
    getAffairsOverview: () => pending.promise, getMyDiscipline: async () => ({ activeCount: 1 })
  })
  const load = vm.load()
  switchAccount()
  pending.resolve({ items: [{ requirementId: '11' }], total: 1, studentName: 'old account' })
  await load
  assert.equal(vm.data, null)
  assert.deepEqual(vm.materials, [])
})

test('refresh supersedes pending next-page results; repeated load-more calls issue one request', async () => {
  const pending = deferred(); let calls = 0
  const { vm } = mount({ getMyMaterialRequirements: ({ page }) => { calls++; return page === 2 ? pending.promise : Promise.resolve({ items: [{ requirementId: 'fresh' }], total: 1 }) } })
  vm.materials = [{ requirementId: 'old' }]; vm.materialTotal = 30
  const more = vm.loadMoreMaterials()
  await vm.loadMoreMaterials()
  await vm.loadMaterials(false)
  pending.resolve({ items: [{ requirementId: 'stale' }], total: 30 })
  await more
  assert.equal(calls, 2)
  assert.deepEqual(vm.materials.map(x => x.requirementId), ['fresh'])
  assert.equal(vm.materialPage, 1)
})

test('material request failure and malformed response are not rendered as no missing materials', async () => {
  for (const reply of [() => Promise.reject(Error('网络中断')), () => Promise.resolve({})]) {
    const { vm } = mount({ getMyMaterialRequirements: reply })
    await vm.loadMaterials(false)
    assert.ok(vm.materialError)
    assert.equal(vm.materialLoading, false)
  }
})

test('pending teacher review is not counted as a material the student must supplement', () => {
  const { vm, component } = mount()
  vm.materials = ['MISSING', 'RETURNED', 'PENDING_REVIEW', 'ACCEPTED'].map(status => ({ status }))
  assert.equal(component.computed.openMaterials.call(vm).length, 2)
})

test('account change during upload or scan prevents follow-up business submission', async () => {
  for (const phase of ['upload', 'scan']) {
    const pending = deferred(); let submits = 0
    const { vm, switchAccount, notices } = mount({
      uploadMaterialFile: () => phase === 'upload' ? pending.promise : Promise.resolve({ fileId: '7' }),
      submitMaterialVersion: async () => { submits++ }
    }, { metadata: () => pending.promise })
    vm.selectedFiles['1'] = { path: '/proof.pdf' }
    if (phase === 'scan') vm.uploadedMaterials['1'] = { fileId: '7' }
    const submission = vm.submitMaterial({ requirementId: '1', version: 2 })
    switchAccount()
    pending.resolve({ fileId: '7', readyForBusiness: true })
    await submission
    assert.equal(submits, 0)
    assert.deepEqual(notices, [])
    assert.equal(vm.uploadedMaterials['1']?.readyForBusiness, undefined)
  }
})

test('page disposal ignores material results', async () => {
  const pending = deferred()
  const { vm } = mount({ getMyMaterialRequirements: () => pending.promise })
  const load = vm.loadMaterials(false)
  vm.pageDisposed = true
  pending.resolve({ items: [{ requirementId: '1' }], total: 1 })
  await load
  assert.deepEqual(vm.materials, [])
})

test('material preview uses the shared authorized viewer and reports failure without fake saved success', async () => {
  const ids = []
  const { vm, notices } = mount({}, { open: async id => { ids.push(id); throw Error('当前文件无法预览') } })
  await vm.downloadMaterial({ fileId: '9007199254740993' })
  assert.deepEqual(ids, ['9007199254740993'])
  assert.deepEqual(notices, ['当前文件无法预览'])
})

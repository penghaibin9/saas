import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const surfaces = [
  ['teacher-pc', '../src/modules/studentAffairs/views/funding/FundingEvidence.vue'],
  ['student-pc', '../../student-portal/src/views/affairs/FundingEvidence.vue'],
  ['student-mini', '../../miniapp/src/components/MobileFundingEvidence.vue'],
  ['teacher-mini', '../../miniapp/src/components/MobileFundingEvidence.vue']
]
function load(file, surface, fetch) {
  const raw = fs.readFileSync(new URL(file, import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1]
  const script = raw.replace(/^import .*\r?\n/gm, '')
  const props = { applicationId: '41', audience: surface.startsWith('teacher') ? 'teacher' : 'student' }
  const calls = [], routes = [], cleanup = []
  const request = params => { calls.push(params); return fetch(params) }
  const deps = {
    defineProps: () => props, ref: value => ({ value }), watch() {},
    onBeforeUnmount: fn => cleanup.push(fn), onUnmounted: fn => cleanup.push(fn),
    useRouter: () => ({ push: route => routes.push(route) }),
    uni: { navigateTo: route => routes.push(route) },
    fileSdk: { list: async () => [] }, normalizeError: e => ({ text: e.message }),
    affairsOperationsApi: { listRequirements: request },
    affairsFourEndApi: { myMaterialRequirements: request },
    affairsContractApi: { getMaterialRequirements: (status, page, pageSize, context) => request({ ...context, status, page, pageSize }), getMyMaterialRequirements: request }
  }
  const vm = new Function(...Object.keys(deps), script + '\nreturn { loadRequirements, openMaterials, requirements, requirementsTotal, requirementsPage, requirementsError, requirementsLoading, requirementsTargetPage }')(...Object.values(deps))
  return { ...vm, props, calls, routes, cleanup }
}

for (const [surface, file] of surfaces) {
  test(`${surface}: material pagination stays scoped to the application and uses server totals`, async () => {
    const vm = load(file, surface, async p => ({ total: 21, items: [{ requirementId: String(p.page), bizType: 'FUNDING', bizId: p.bizId, status: 'RETURNED' }] }))
    await vm.loadRequirements(2)
    assert.equal(vm.calls[0].bizType, 'FUNDING'); assert.equal(vm.calls[0].bizId, '41')
    assert.equal(vm.calls[0].page, 2); assert.equal(vm.calls[0].pageSize, 10)
    assert.equal(vm.requirementsTotal.value, 21); assert.equal(vm.requirementsPage.value, 2)
    vm.openMaterials('7')
    const route = vm.routes[0]
    if (surface.endsWith('mini')) {
      assert.match(route.url, /bizType=FUNDING&bizId=41&materialRequirementId=7/)
      assert.ok(route.url.includes(surface.startsWith('teacher') ? '/teacher/' : '/student/'))
    } else assert.deepEqual(route.query, { bizType: 'FUNDING', bizId: '41', materialRequirementId: '7' })
  })
  test(`${surface}: slow previous application responses and unmounted requests cannot overwrite current materials`, async () => {
    const pending = [], vm = load(file, surface, () => new Promise(resolve => pending.push(resolve)))
    const first = vm.loadRequirements(); vm.props.applicationId = '42'; const second = vm.loadRequirements()
    pending[1]({ total: 1, items: [{ bizType: 'FUNDING', bizId: '42' }] }); await second
    pending[0]({ total: 100, items: [{ bizType: 'FUNDING', bizId: '41' }] }); await first
    assert.equal(vm.requirements.value[0].bizId, '42'); assert.equal(vm.requirementsTotal.value, 1)
    const last = vm.loadRequirements(); vm.cleanup.forEach(fn => fn())
    pending[2]({ total: 0, items: [] }); await last
    assert.equal(vm.requirementsTotal.value, 1)
  })
  test(`${surface}: failed or mismatched reads stay errors and do not imply materials are complete`, async () => {
    let reject = false
    const vm = load(file, surface, async () => { if (reject) throw new Error('网络暂不可用'); return { total: 1, items: [{ bizType: 'AID', bizId: '41' }] } })
    await vm.loadRequirements(); assert.match(vm.requirementsError.value, /关联不一致/); assert.equal(vm.requirements.value.length, 0)
    reject = true; await vm.loadRequirements(2); assert.match(vm.requirementsError.value, /网络/); assert.equal(vm.requirementsLoading.value, false); assert.equal(vm.requirementsTargetPage.value, 2); assert.equal(vm.requirementsPage.value, 1)
  })
}

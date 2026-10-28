import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
const code = source.slice(source.indexOf('const activityPages ='), source.indexOf('const leaveForm ='))
function mount(api) {
  return new Function('reactive', 'portalApi', 'activities', 'viewActive', code + ';return {activities,activityPages,activityPageErrors,activityPageLoading,loadActivityPage,applyActivityFirstPage,activityNextStep,dispose:()=>{viewActive=false}}')(
    value => value, api, { value: { available: [{ activityId: 'open' }], mine: [{ activityId: 'old' }] } }, true)
}

test('my ongoing activities can reach page two without replacing available activities', async () => {
  let sent
  const vm = mount({ affairsActivitiesMy: async params => { sent = params; return { mine: [{ activityId: '21', status: 'ONGOING' }], mineTotal: 21, mineHasMore: false } } })
  await vm.loadActivityPage('mine', 2)
  assert.deepEqual(sent, { page: 2, pageSize: 20 })
  assert.equal(vm.activities.value.mine[0].activityId, '21')
  assert.equal(vm.activities.value.available[0].activityId, 'open')
  assert.equal(vm.activityPages.mine, 2)
  assert.match(vm.activityNextStep({ status: 'ONGOING' }), /签到/)
})

test('refresh invalidates an older page response and retains the refreshed history', async () => {
  let finish
  const vm = mount({ affairsActivitiesMy: () => new Promise(resolve => { finish = resolve }) })
  const pending = vm.loadActivityPage('mine', 2)
  vm.applyActivityFirstPage({ available: [], mine: [{ activityId: 'fresh' }] })
  finish({ mine: [{ activityId: 'late' }] }); await pending
  assert.equal(vm.activities.value.mine[0].activityId, 'fresh')
  assert.equal(vm.activityPages.mine, 1)
})

test('failed pagination preserves the original history and reports a retryable error', async () => {
  const vm = mount({ affairsActivitiesMy: async () => { throw Error('暂时无法读取') } })
  await vm.loadActivityPage('mine', 2)
  assert.equal(vm.activities.value.mine[0].activityId, 'old')
  assert.equal(vm.activityPages.mine, 1)
  assert.match(vm.activityPageErrors.mine, /无法读取/)
  assert.equal(vm.activityPageLoading.mine, false)
})

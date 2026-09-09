import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function profile(api = {}) {
  const source = readFileSync(new URL('../src/views/profile/ProfileView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const sandbox = {
    ref: value => ({ value }), reactive: value => value, computed: getter => ({ get value() { return getter() } }),
    onMounted() {}, onActivated() {}, onDeactivated() {}, onBeforeUnmount() {},
    portalApi: { affairsApplications: async () => ({}), listGuardians: async () => [], ...api },
    useUiStore: () => ({ notify() {} }),
  }
  vm.runInNewContext(script + '\ncomponent = {load, leaveProfile, confirmReveal, statusText, info, loading, error, reveal, reason, busy}', sandbox)
  return sandbox.component
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('a fresh enrollment read wins over an older response and clears stale plaintext', async () => {
  const old = deferred()
  let count = 0
  const state = profile({ profileEnrollment: () => ++count === 1 ? old.promise : Promise.resolve({ hasData: true, className: '转入班', studentStatus: 'REGISTERED' }) })
  state.reveal.phone = 'sensitive-old-value'
  const pending = state.load()
  assert.equal(state.reveal.phone, '')
  await state.load()
  old.resolve({ hasData: true, className: '转出班' })
  await pending
  assert.equal(state.info.value.className, '转入班')
  assert.equal(state.loading.value, false)
})

test('leaving prevents late enrollment or sensitive responses from becoming visible', async () => {
  const enrollment = deferred(), sensitive = deferred()
  const state = profile({ profileEnrollment: () => enrollment.promise, profileSensitive: () => sensitive.promise })
  const pending = state.load()
  state.reason.value = '核对信息'
  const revealing = state.confirmReveal('phone')
  state.leaveProfile()
  enrollment.resolve({ hasData: true, className: '过期班级' })
  sensitive.resolve({ value: 'late-sensitive-value' })
  await Promise.all([pending, revealing])
  assert.equal(state.info.value.className, undefined)
  assert.equal(state.reveal.phone, '')
})

test('failed refresh clears old enrollment and academic status labels retain their meaning', async () => {
  const state = profile({ profileEnrollment: async () => { throw new Error('暂时无法获取学籍') } })
  state.info.value = { hasData: true, className: '旧班级' }
  await state.load()
  assert.equal(state.info.value.className, undefined)
  assert.equal(state.error.value, '暂时无法获取学籍')
  assert.equal(state.statusText('PRESERVED'), '保留学籍')
  assert.equal(state.statusText('RETAINED'), '留级')
  assert.equal(state.statusText('REGISTERED'), '已注册')
  assert.equal(state.statusText('COMPLETED'), '结业')
  assert.equal(state.statusText('UNKNOWN'), '待确认')
})

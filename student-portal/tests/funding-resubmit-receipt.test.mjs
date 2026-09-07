import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const pc = readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
const pcBody = pc.split('async function submitReturnedFunding() {')[1].split('\nasync function submitModal()')[0].trim().replace(/\}$/, '')
const mobile = readFileSync(new URL('../../miniapp/src/pages/student/affairs/funding.vue', import.meta.url), 'utf8')
const mobileBody = mobile.split('async saveAndResubmit() {')[1].split('\n    async appeal(')[0].trim().replace(/\},$/, '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

for (const success of [true, false]) {
  test(`PC resubmit ${success ? 'opens exact server-backed result' : 'keeps failed edit instead of showing success'}`, async () => {
    const detail = { value: '' }, calls = [], busy = { value: false }
    const modal = { item: { applicationId: '9007199254740993', version: 3 }, form: { statement: '补充完整申请说明' } }
    const api = { updateReturnedFunding: async (...args) => { calls.push(args); return { version: 4 } }, resubmitFunding: async (...args) => calls.push(args) }
    const run = new AsyncFunction('busy', 'modal', 'affairsFourEndApi', 'submitUpdatedAndResubmit', 'fundingDetailId', pcBody)
    await run(busy, modal, api, async command => { const updated = await command.update(); await command.resubmit(updated.version); return success }, detail)
    assert.equal(detail.value, success ? '9007199254740993' : '')
    assert.deepEqual(calls[1], ['9007199254740993', 4])
    busy.value = true
    await run(busy, modal, api, () => assert.fail('busy blocks repeat'), detail)
  })
}

for (const success of [true, false]) {
  test(`mobile resubmit ${success ? 'shows exact original result' : 'retains saved version and correction text on failure'}`, async () => {
    let reads = 0
    const vm = { busy: false, editReason: '补充完整申请说明', editTarget: { applicationId: '9007199254740993', version: 3 }, editVisible: true, detailId: '', load: () => { reads++ }, showError: () => {} }
    const api = { updateFunding: async () => ({ version: 4 }), resubmitFunding: async (id, version) => { assert.equal(id, '9007199254740993'); assert.equal(version, 4); if (!success) throw new Error('版本冲突') } }
    const run = new AsyncFunction('affairsReturnedApi', 'toast', 'normalizeError', mobileBody)
    await run.call(vm, api, () => {}, error => ({ text: error.message }))
    assert.equal(vm.detailId, success ? '9007199254740993' : '')
    assert.equal(vm.editVisible, !success)
    assert.equal(vm.editReason, '补充完整申请说明')
    assert.equal(vm.editTarget.version, 4)
    assert.equal(reads, success ? 1 : 0)
    assert.equal(vm.busy, false)
  })
}

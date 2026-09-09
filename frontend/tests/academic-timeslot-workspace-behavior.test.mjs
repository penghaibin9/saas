import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

function component(path, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/${path}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = Object.assign(definition.data(), definition.methods, {
    ctx: { permissionPatterns: ['academicAffairs.*'] },
    $route: { query: {} }, $router: { replace() {} }, $emit() {}, disabled: false,
  }, extra)
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, definition }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const page = (dependencies, extra) => component('views/AaTimeSlotView', dependencies, extra)
const panel = (dependencies, extra) => component('components/AaTimeSlotTemplatePanel', dependencies, extra)

test('read-only roles cannot issue slot or band commands; band navigation needs its read permission', async () => {
  const { state } = page({}, { ctx: { permissionPatterns: ['academicAffairs.timeslot.view'] } })
  assert.equal(state.canManageSlots, false)
  assert.equal(state.canManageBands, false)
  assert.equal(state.tabs.length, 1)
  await state.addSlot()
  await state.submitEdit()
  await state.doDelete()
  await state.addBand()
  await state.toggleBandStatus({})
  await state.doDeleteBand()
  state.goBands({ slotId: 'a' })
  assert.equal(state.tab, 'periods')
})

test('slot and dated band forms validate pairs and ranges while retaining larger existing slot numbers', () => {
  const { state } = page()
  assert.match(state.validate({ slotNo: 1.5 }), /正整数/)
  assert.match(state.validate({ slotNo: 1, startTime: '08:00' }), /成对/)
  assert.match(state.validate({ slotNo: 1, startTime: '25:00', endTime: '26:00' }), /格式/)
  assert.equal(state.validate({ slotNo: 21 }), '')
  assert.match(state.validateBand({ startTime: '08:00', endTime: '08:45', effectiveStart: '2026-10-01', effectiveEnd: '2026-05-01' }), /生效结束/)
})

test('old requests cannot overwrite a newly selected slot and selection survives navigation', async () => {
  const replies = [deferred(), deferred()]
  let calls = 0, route, accepted
  const { state, definition } = page({ academicAffairsApi: { getTimeBands: () => replies[calls++].promise } }, {
    bandSlotId: 'a', $router: { replace(value) { route = value } },
  })
  const old = state.loadBands()
  state.bandSlotId = 'b'
  const current = state.loadBands()
  replies[1].resolve({ code: 0, data: [{ bandId: 'b-band' }] })
  await current
  replies[0].resolve({ code: 0, data: [{ bandId: 'a-band' }] })
  await old
  assert.equal(state.bandRows[0].bandId, 'b-band')
  state.load = () => {}
  state.goBands({ slotId: 'b' })
  assert.equal(route.query.slotId, 'b')
  assert.equal(route.query.tab, 'bands')
  state.bandSaving = true
  definition.beforeRouteUpdate.call(state, {}, {}, value => { accepted = value })
  assert.equal(accepted, false)
  definition.beforeRouteLeave.call(state, {}, {}, value => { accepted = value })
  assert.equal(accepted, false)
})

test('editing uses date-only values and sends explicit clears; a conflict preserves the form', async () => {
  let sent
  const { state } = page({ academicAffairsApi: { updateTimeBand: async (...args) => { sent = args; return { code: 409, message: '生效日期重叠' } } } })
  state.openEditBand({ bandId: 'a', effectiveStart: '2026-05-01T00:00:00Z', effectiveEnd: '2026-09-30T00:00:00Z', startTime: '08:00', endTime: '08:45' })
  assert.equal(state.editBandForm.effectiveStart, '2026-05-01')
  state.editBandForm.effectiveStart = ''
  state.editBandForm.effectiveEnd = ''
  await state.submitEditBand()
  assert.equal(sent[1].effectiveStart, null)
  assert.equal(sent[1].effectiveEnd, null)
  assert.equal(sent[1].campusCode, '')
  assert.equal(state.editBandVisible, true)
  assert.equal(state.editBandError, '生效日期重叠')
})

test('parallel clicks issue one status command', async () => {
  const response = deferred()
  let calls = 0
  const { state } = page({ academicAffairsApi: { updateTimeSlot: () => { calls++; return response.promise } } })
  state.load = () => {}
  const pending = state.toggleEnabled({ slotId: 'a', enabled: true })
  await state.toggleEnabled({ slotId: 'a', enabled: true })
  assert.equal(calls, 1)
  response.resolve({ code: 0 })
  await pending
  assert.equal(state.busy, false)
})

test('changing the template invalidates in-flight previews; parent writes prevent application', async () => {
  const response = deferred()
  const { state, definition } = panel({ termCalendarConvenienceApi: { previewTimeSlotTemplate: () => response.promise } })
  const pending = state.loadPreview()
  state.choose('STANDARD_10')
  response.resolve({ code: 0, data: { readyCount: 8 } })
  await pending
  assert.equal(state.preview, null)
  state.preview = { readyCount: 10 }
  state.disabled = true
  definition.watch.disabled.call(state, true)
  assert.equal(state.canApply, false)
  assert.equal(state.preview, null)
})

test('partial template creation keeps failure feedback and requires a fresh preview', async () => {
  const sent = [], events = []
  const { state } = panel({ academicAffairsApi: { createTimeSlot: async desired => {
    sent.push(desired.slotNo)
    state.choose('STANDARD_10')
    return sent.length === 1 ? { code: 0 } : { code: 409, message: '钟点重叠' }
  } } }, {
    preview: { readyCount: 2, items: [{ status: 'READY', desired: { slotNo: 1 } }, { status: 'READY', desired: { slotNo: 2 } }] },
    $emit: (...args) => events.push(args),
  })
  await state.applyTemplate()
  assert.deepEqual(sent, [1, 2])
  assert.equal(state.templateKey, 'STANDARD_8')
  assert.equal(state.preview, null)
  assert.equal(state.canApply, false)
  assert.equal(state.applying, false)
  assert.match(state.error, /已成功创建 1 项/)
  assert.match(state.error, /钟点重叠/)
  assert.equal(events[0][1], true)
  assert.equal(events[1][1], false)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'
import { matchPermission } from '../src/config/navPlan.js'

function page(api = {}, extra = {}) {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaTimeSlotView.vue', import.meta.url), 'utf8').split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm, '').replace(/components: \{[\s\S]*?\},/, 'components: {},').replace('export default', 'globalThis.definition =')
  const calls = []
  const sandbox = { matchPermission, academicAffairsApi: api, toast: { success() { calls.push('success') }, error() {}, warning() {} }, window: { __SAAS_DIRTY_FORM_GUARD__: { markSaved() { calls.push('saved') }, markDirty() { calls.push('dirty') } } } }
  vm.runInNewContext(source, sandbox)
  const definition = sandbox.definition
  const state = Object.assign(definition.data(), definition.methods, { ctx: { currentRole: { roleCode: 'ACADEMIC_ADMIN' }, permissionPatterns: ['academicAffairs.*'], dataScope: { scope: 'SCHOOL' } }, $refs: {}, $route: { query: { tab: 'periods', returnToken: 'origin', page: '2' } }, $router: { replace() { return Promise.resolve() } }, rows: [{ slotId: '1', slotNo: 1, slotName: 'existing', startTime: '08:00', endTime: '08:45', enabled: true }], loading: false, ...extra })
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state), configurable: true })
  state.initializeDraftBaselines?.(); state.load = () => calls.push('read'); state.loadBands = () => calls.push('bands-read')
  return { state, definition, calls }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('referenced slots explain the restriction and never submit disable or delete', async () => {
  let writes = 0
  const { state } = page({ updateTimeSlot: async () => { writes++ }, deleteTimeSlot: async () => { writes++ } })
  const row = { ...state.rows[0], referenceStatus: 'IN_USE', referenceCount: 3 }
  state.rows = [row]
  await state.toggleEnabled(row)
  assert.equal(writes, 0)
  assert.match(state.commandError, /不能停用/)
  state.confirmDelete(row)
  assert.equal(state.confirmVisible, false)
  state.pendingDelete = { ...row }; state.confirmVisible = true
  await state.doDelete()
  assert.equal(writes, 0)
  assert.match(state.commandError, /不能删除/)
})

test('reference count also protects renumbering while allowing a name correction', async () => {
  let writes = 0
  const { state } = page()
  state.rows[0].referenceCount = 2
  state.openEdit(state.rows[0]); state.editForm.slotNo = 7
  state.saveEditor = async () => { writes++ }
  await state.submitEdit()
  assert.equal(writes, 0)
  assert.match(state.editError, /不能修改节次编号/)
  state.editForm.slotNo = 1; state.editForm.slotName = '新的显示名称'
  await state.submitEdit()
  assert.equal(writes, 1)
})

test('unreferenced slots remain operable and referenced disabled slots can be enabled', async () => {
  const bodies = []
  const { state } = page({ updateTimeSlot: async (id, body) => { bodies.push(body); return { code: 0 } } })
  await state.toggleEnabled({ ...state.rows[0], referenceStatus: 'UNUSED', referenceCount: 0 })
  await state.toggleEnabled({ ...state.rows[0], enabled: false, referenceStatus: 'IN_USE' })
  assert.deepEqual(bodies.map(body => body.enabled), [false, true])
  state.confirmDelete(state.rows[0])
  assert.equal(state.confirmVisible, true)
  state.rows[0].slotNo = 9
  assert.equal(state.pendingDelete.slotNo, 1)
})
const slotAck = (id = '1') => ({ code: 0, data: { slotId: id, slotNo: 2, slotName: 'saved', startTime: '09:00', endTime: '09:45', campusCode: '', enabled: true, status: 'ENABLED', version: 1 } })
const bandAck = (id = 'b', parent = '1') => ({ code: 0, data: { bandId: id, slotId: parent, bandName: 'saved', campusCode: 'north', effectiveStart: '2026-10-01T00:00:00', effectiveEnd: null, startTime: '09:00', endTime: '09:45', status: 'ENABLED', version: 1 } })
const kinds = ['slotCreate', 'slotEdit', 'bandCreate', 'bandEdit']
const apiName = { slotCreate: 'createTimeSlot', slotEdit: 'updateTimeSlot', bandCreate: 'createTimeBand', bandEdit: 'updateTimeBand' }
const method = { slotCreate: 'addSlot', slotEdit: 'submitEdit', bandCreate: 'addBand', bandEdit: 'submitEditBand' }
const property = { slotCreate: 'draft', slotEdit: 'editForm', bandCreate: 'bandDraft', bandEdit: 'editBandForm' }
function prepare(state, kind) {
  state.bandSlotId = '1'
  if (kind === 'slotEdit') state.openEdit({ slotId: '1', slotNo: 1, slotName: 'old', startTime: '08:00', endTime: '08:45', enabled: true })
  if (kind === 'bandEdit') state.openEditBand({ bandId: 'b', bandName: 'old', campusCode: '', startTime: '08:00', endTime: '08:45' })
  const fields = kind.startsWith('slot') ? { slotNo: 2, slotName: 'saved', startTime: '09:00', endTime: '09:45' } : { bandName: 'saved', campusCode: ' north ', effectiveStart: '2026-10-01', effectiveEnd: '', startTime: '09:00', endTime: '09:45' }
  Object.assign(state[property[kind]], fields)
}

test('actual slot consumer uses shared dirty guard through cancel, aborted navigation and explicit discard', async () => {
  const previous = { window: globalThis.window, document: globalThis.document }
  const from = { name: 'aa-time-slots', path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots?tab=periods' }, to = { name: 'aa-terms', fullPath: '/admin/academic-affairs/terms' }
  let before, after, accepted = false
  globalThis.window = { addEventListener() {}, removeEventListener() {} }; globalThis.document = { addEventListener() {}, removeEventListener() {} }
  let dispose
  try {
    dispose = installDirtyFormGuard({ currentRoute: { value: from }, beforeEach(fn) { before = fn }, beforeResolve(fn) { this.resolveGuard = fn; return () => { if (this.resolveGuard === fn) this.resolveGuard = null } }, afterEach(fn) { after = fn } })
    const guard = window.__SAAS_DIRTY_FORM_GUARD__; assert.equal(guard.handlesRoute(from), true); guard.registerConfirmation(() => accepted)
    assert.equal(await before(to, from), true); guard.markDirty(); assert.equal(await before(to, from), false); assert.equal(guard.isDirty(), true)
    accepted = true; assert.equal(await before(to, from), true); after(to, from, new Error('aborted')); assert.equal(guard.isDirty(), true)
    assert.equal(await before(to, from), true); after(to, from); assert.equal(guard.isDirty(), false)
  } finally { dispose?.(); for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[key]; else globalThis[key] = value } }
})

test('same existing slot editor reopens its pending name and original baseline', () => {
  const { state } = page(); const row = state.rows[0]
  state.openEdit(row); state.editForm.slotName = 'pending'; state.editVisible = false
  const baseline = state.editorBaselines?.slotEdit
  state.openEdit(row); assert.equal(state.editForm.slotName, 'pending'); assert.equal(state.editVisible, true); assert.equal(state.editorBaselines?.slotEdit, baseline)
})

test('numeric stepper and time/date user emits mark dirty without marking initial hydration', () => {
  const { state, calls } = page(); assert.deepEqual(calls, [])
  state.updateEditorField('slotCreate', 'slotNo', 1); state.updateEditorField('slotCreate', 'startTime', '09:00'); state.updateEditorField('bandCreate', 'effectiveStart', '2026-10-01')
  assert.deepEqual(calls, ['dirty', 'dirty', 'dirty']); assert.equal(state.draft.slotNo, 1); assert.equal(state.bandDraft.effectiveStart, '2026-10-01')
  state.updateEditorField('slotCreate', 'slotNo', 1); assert.equal(calls.length, 3)
  state.adding = true; state.updateEditorField('slotCreate', 'slotName', 'late'); assert.equal(state.draft.slotName, '')
})

test('existing tab and slot query intents retain editors on cancel and adopt only actual successful route', async () => {
  const { state, definition } = page(); state.draft.slotName = 'hidden'; state.editVisible = true
  const requested = []; state.$router.replace = value => { requested.push(value); return Promise.resolve({ type: 'cancelled' }) }
  await state.switchTab('bands'); assert.equal(state.tab, 'periods'); assert.equal(state.editVisible, true); assert.equal(state.draft.slotName, 'hidden'); assert.equal(requested[0].query.returnToken, 'origin')
  await state.goBands(state.rows[0]); assert.equal(state.bandSlotId, ''); assert.equal(state.tab, 'periods'); assert.equal(requested[1].query.slotId, '1')
  state.$route.query = { tab: 'bands', slotId: '1', returnToken: 'origin', page: '2' }; definition.watch['$route.query.tab'].call(state, 'bands'); definition.watch['$route.query.slotId'].call(state, '1')
  assert.equal(state.tab, 'bands'); assert.equal(state.bandSlotId, '1'); assert.equal(state.editVisible, false)
  state.bandDraft.bandName = 'retained band'; state.rows.push({ slotId: '2', slotNo: 2 }); await state.onBandSlotChange('2'); assert.equal(state.bandSlotId, '1'); assert.equal(state.bandDraft.bandName, 'retained band')
  state.$router.replace = () => Promise.reject(new Error('unavailable')); await state.switchTab('periods'); assert.equal(state.tab, 'bands'); assert.equal(state.bandDraft.bandName, 'retained band')
})

test('four legal save acknowledgements clear only the saved editor and retain every other editor or template pending', async () => {
  for (const kind of kinds) for (const other of ['none', ...kinds.filter(value => value !== kind), 'template']) {
    const { state, calls } = page({ [apiName[kind]]: async () => kind.startsWith('slot') ? slotAck() : bandAck() }); prepare(state, kind)
    if (other === 'template') state.$refs.timeSlotTemplate = { preview: { items: [{ desired: { slotNo: 1 } }] }, loading: false, applying: false }
    else if (other !== 'none') prepare(state, other)
    await state[method[kind]]()
    assert.ok(calls.includes('success'), kind + ' legal ack')
    if (other === 'none') assert.ok(calls.includes('saved'), kind + ' sole editor clears')
    else { assert.equal(calls.includes('saved'), false, kind + ' must retain ' + other); assert.ok(calls.includes('dirty')) }
  }
})

test('four failed or malformed acknowledgements preserve inputs and never clear dirty', async () => {
  for (const kind of kinds) for (const response of [{ code: 409001, message: 'rejected' }, { code: 0, message: 'ok', data: { slotId: '1', bandId: 'b' } }, kind === 'slotEdit' ? slotAck('other') : kind.startsWith('band') ? bandAck('b', 'other') : { ...slotAck(), data: { ...slotAck().data, slotNo: 3 } }]) {
    const { state, calls } = page({ [apiName[kind]]: async () => response }); prepare(state, kind); const before = JSON.stringify(state[property[kind]])
    await state[method[kind]](); assert.equal(JSON.stringify(state[property[kind]]), before); assert.equal(calls.includes('saved'), false); assert.equal(calls.includes('success'), false)
  }
})

test('late response cannot clear a different identity, object, parent or newer local form', async () => {
  for (const kind of kinds) for (const change of [state => { state.ctx.permissionPatterns = ['academicAffairs.timeslot.view'] }, state => { state[property[kind]].startTime = '10:00' }, state => { state.disposed = true }, ...(kind.startsWith('band') ? [state => { state.bandSlotId = 'other' }] : kind === 'slotEdit' ? [state => { state.editForm.slotId = 'other' }] : [])]) {
    const reply = deferred(); const { state, calls } = page({ [apiName[kind]]: () => reply.promise }); prepare(state, kind)
    const pending = state[method[kind]](); change(state); const retained = JSON.stringify(state[property[kind]]); reply.resolve(kind.startsWith('slot') ? slotAck() : bandAck()); await pending
    assert.equal(JSON.stringify(state[property[kind]]), retained); assert.equal(calls.includes('saved'), false); assert.equal(calls.includes('success'), false)
  }
})

test('old out-of-scope editor replacement cannot make a later acknowledgement hide unresolved dirty', async () => {
  for (const kind of ['slotEdit', 'bandEdit']) {
    const { state, calls } = page({ createTimeSlot: async () => slotAck() }); prepare(state, kind)
    if (kind === 'slotEdit') state.openEdit({ slotId: 'other', slotNo: 3, slotName: 'clean', startTime: '', endTime: '', enabled: true })
    else state.openEditBand({ bandId: 'other', bandName: 'clean', campusCode: '', startTime: '08:00', endTime: '08:45' })
    prepare(state, 'slotCreate'); await state.addSlot(); assert.equal(calls.includes('saved'), false); assert.ok(calls.includes('dirty'))
  }
  const clean = page({ createTimeSlot: async () => slotAck() })
  clean.state.openEdit(clean.state.rows[0]); clean.state.openEdit({ ...clean.state.rows[0], slotId: 'other' }); prepare(clean.state, 'slotCreate'); await clean.state.addSlot(); assert.ok(clean.calls.includes('saved'), 'clean editor hydration does not invent unresolved dirty')
  const saved = page({ updateTimeSlot: async () => slotAck(), createTimeSlot: async () => slotAck() }); prepare(saved.state, 'slotEdit'); await saved.state.submitEdit(); saved.calls.length = 0
  saved.state.openEdit({ ...slotAck().data }); prepare(saved.state, 'slotCreate'); await saved.state.addSlot(); assert.ok(saved.calls.includes('saved'), 'same saved row reopening does not become phantom dirty')
})

test('empty submitted band dates require explicit nullable date keys in the acknowledgement', async () => {
  for (const kind of ['bandCreate', 'bandEdit']) for (const invalid of ['missing', undefined, '', 0]) {
    const response = bandAck(); response.data.effectiveStart = null; response.data.effectiveEnd = invalid
    if (invalid === 'missing') delete response.data.effectiveEnd
    const { state, calls } = page({ [apiName[kind]]: async () => response }); prepare(state, kind); state[property[kind]].effectiveStart = ''; state[property[kind]].effectiveEnd = ''
    const before = JSON.stringify(state[property[kind]]), baseline = state.editorBaselines[kind]
    await state[method[kind]](); assert.equal(JSON.stringify(state[property[kind]]), before); assert.equal(state.editorBaselines[kind], baseline); assert.equal(calls.includes('saved'), false); assert.equal(calls.includes('success'), false)
  }
})


test('requesting a different slot retains the old pending name, baseline and error until an explicit decision', () => {
  const first = { slotId: '1', slotNo: 1, slotName: 'existing first', startTime: '08:00', endTime: '08:45', enabled: true }
  const second = { slotId: '2', slotNo: 2, slotName: 'existing second', startTime: '08:55', endTime: '09:40', enabled: true }
  const { state } = page({}, { rows: [first, second] })
  state.openEdit(first)
  state.updateEditorField('slotEdit', 'slotName', 'A6 different-slot pending marker')
  state.editError = 'The original validation message must remain with the draft'
  state.editVisible = false
  const pending = { form: JSON.stringify(state.editForm), baseline: state.editorBaselines.slotEdit, error: state.editError }
  state.openEdit(second)
  assert.deepEqual({ form: JSON.stringify(state.editForm), baseline: state.editorBaselines.slotEdit, error: state.editError }, pending,
    'choosing another real slot must retain the first draft until the user decides to discard it')
})


function pendingSlotSwitchPage(extra = {}) {
  const first = { slotId: '1', slotNo: 1, slotName: 'first saved', startTime: '08:00', endTime: '08:45', enabled: true }
  const second = { slotId: '2', slotNo: 2, slotName: 'second saved', startTime: '08:55', endTime: '09:40', enabled: true }
  const fixture = page({}, { rows: [first, second], ...extra })
  fixture.state.openEdit(first)
  fixture.state.updateEditorField('slotEdit', 'slotName', 'retained pending first')
  fixture.state.editError = 'retained validation message'
  fixture.state.editVisible = false
  fixture.calls.length = 0
  return { ...fixture, first, second }
}

test('different-slot cancellation reopens the original draft with its unchanged baseline and error', () => {
  const { state, calls, first, second } = pendingSlotSwitchPage()
  const form = state.editForm, before = JSON.stringify(form), baseline = state.editorBaselines.slotEdit
  state.openEdit(second)
  assert.equal(state.slotSwitchVisible, true)
  assert.equal(state.editForm, form); assert.equal(JSON.stringify(state.editForm), before)
  assert.equal(state.editorBaselines.slotEdit, baseline); assert.equal(state.editError, 'retained validation message')
  state.cancelSlotSwitch()
  assert.equal(state.slotSwitchVisible, false); assert.equal(state.pendingSlotSwitch, null)
  assert.equal(state.editVisible, true); assert.equal(state.editForm, form)
  assert.equal(state.editForm.slotId, first.slotId); assert.equal(state.editForm.slotName, 'retained pending first')
  assert.equal(state.editorBaselines.slotEdit, baseline); assert.equal(state.editError, 'retained validation message')
  assert.equal(calls.includes('saved'), false)
})

test('explicit discard adopts only the selected current slot and retains each other hidden draft or template', () => {
  for (const other of ['none', 'slotCreate', 'bandCreate', 'bandEdit', 'template', 'historical unresolved']) {
    const { state, calls, second } = pendingSlotSwitchPage()
    if (other === 'template') state.$refs.timeSlotTemplate = { preview: { items: [] }, loading: false, applying: false }
    else if (other === 'historical unresolved') state.unresolvedEditorDirty = true
    else if (other !== 'none') prepare(state, other)
    state.openEdit(second); assert.equal(state.slotSwitchVisible, true)
    state.confirmSlotSwitch()
    assert.equal(state.slotSwitchVisible, false); assert.equal(state.pendingSlotSwitch, null)
    assert.equal(state.editForm.slotId, second.slotId); assert.equal(state.editForm.slotName, second.slotName)
    assert.equal(state.editorBaselines.slotEdit, state.editorSignature('slotEdit')); assert.equal(state.editError, '')
    assert.equal(state.editVisible, true)
    if (other === 'none') assert.deepEqual(calls, ['saved'])
    else { assert.equal(calls.includes('saved'), false, other); assert.ok(calls.includes('dirty'), other) }
  }
})

test('same pending slot and clean or acknowledged saved editors do not ask to discard unrelated input', async () => {
  const same = pendingSlotSwitchPage(); const baseline = same.state.editorBaselines.slotEdit
  same.state.openEdit(same.first)
  assert.equal(same.state.slotSwitchVisible, false); assert.equal(same.state.editVisible, true)
  assert.equal(same.state.editForm.slotName, 'retained pending first'); assert.equal(same.state.editorBaselines.slotEdit, baseline)
  const clean = page({}, { rows: [same.first, same.second] })
  clean.state.openEdit(same.first); clean.state.editVisible = false; clean.state.openEdit(same.second)
  assert.equal(clean.state.slotSwitchVisible, false); assert.equal(clean.state.editForm.slotId, same.second.slotId)
  const saved = page({ updateTimeSlot: async () => slotAck() }, { rows: [same.first, same.second] })
  prepare(saved.state, 'slotEdit'); await saved.state.submitEdit()
  saved.state.openEdit(same.second)
  assert.equal(saved.state.slotSwitchVisible, false); assert.equal(saved.state.editForm.slotId, same.second.slotId)
})

test('stale slot-switch decisions cannot discard a changed draft, context, identity, baseline, target or lifecycle', () => {
  const changes = [
    state => { state.ctx.currentRole.roleCode = 'OTHER_CONTEXT' },
    state => { state.academicFlow = { identity: () => 'different actual identity contract' } },
    state => { state.editForm.slotName = 'newer user input' },
    state => { state.editorBaselines.slotEdit = 'new baseline' },
    state => { state.rows = state.rows.filter(row => row.slotId !== '2') },
    state => { state.rows[1] = { ...state.rows[1], startTime: '10:00' } },
    state => { state.saving = true },
    state => { state.ctx.permissionPatterns = ['academicAffairs.timeslot.view'] },
    state => { state.disposed = true }
  ]
  for (const change of changes) {
    const { state, calls, second } = pendingSlotSwitchPage()
    state.openEdit(second); assert.equal(state.slotSwitchVisible, true)
    change(state)
    const before = JSON.stringify(state.editForm), baseline = state.editorBaselines.slotEdit, error = state.editError
    state.confirmSlotSwitch()
    assert.equal(JSON.stringify(state.editForm), before); assert.equal(state.editorBaselines.slotEdit, baseline)
    assert.equal(state.editError, error); assert.equal(state.slotSwitchVisible, false); assert.equal(state.pendingSlotSwitch, null)
    assert.equal(calls.includes('saved'), false)
  }
})

test('actual route adoption, context watcher and unmount invalidate local slot-switch intent', () => {
  // The legacy VM loader does not implement reactivity; call the real hooks and
  // watcher handler explicitly, rather than claiming a normal browser result.
  for (const transition of ['route', 'context', 'unmount']) {
    const { state, definition, calls, second } = pendingSlotSwitchPage()
    state.openEdit(second); assert.equal(state.slotSwitchVisible, true)
    if (transition === 'route') state.applyRouteSelection('bands', '1')
    else if (transition === 'context') {
      state.ctx.ctxKey = 'new context'
      definition.watch.slotEditorContextKey.handler.call(state)
    } else definition.beforeUnmount.call(state)
    assert.equal(state.slotSwitchVisible, false); assert.equal(state.pendingSlotSwitch, null)
    const before = JSON.stringify(state.editForm)
    state.confirmSlotSwitch(); assert.equal(JSON.stringify(state.editForm), before); assert.equal(calls.includes('saved'), false)
  }
})

test('busy, read-only, disposed or missing target cannot open a destructive slot-switch decision', () => {
  for (const deny of [state => { state.templateApplying = true }, state => { state.ctx.permissionPatterns = ['academicAffairs.timeslot.view'] }, state => { state.disposed = true }, state => { state.rows = [state.rows[0]] }]) {
    const { state, calls, second } = pendingSlotSwitchPage()
    deny(state)
    const before = JSON.stringify(state.editForm), baseline = state.editorBaselines.slotEdit
    state.openEdit(second)
    assert.equal(state.slotSwitchVisible, false); assert.equal(state.pendingSlotSwitch, null)
    assert.equal(JSON.stringify(state.editForm), before); assert.equal(state.editorBaselines.slotEdit, baseline)
    assert.equal(calls.includes('saved'), false)
  }
})


test('same existing time band reopens its pending name with original baseline and error', () => {
  const { state } = page({}, { tab: 'bands', bandSlotId: '1' })
  const row = { bandId: 'local-band-a', slotId: '1', bandName: '正式时间段名称', campusCode: '', effectiveStart: null, effectiveEnd: null, startTime: '08:00', endTime: '08:45', status: 'ENABLED', version: 0 }
  state.openEditBand(row)
  state.updateEditorField('bandEdit', 'bandName', '未保存的时间段名称')
  state.editBandError = '保留的编辑提示'
  const baseline = state.editorBaselines.bandEdit
  state.editBandVisible = false
  state.openEditBand(row)
  assert.equal(state.editBandForm.bandName, '未保存的时间段名称', 'same-record reopening must retain the unsaved band name')
  assert.equal(state.editorBaselines.bandEdit, baseline)
  assert.equal(state.editBandError, '保留的编辑提示')
  assert.equal(state.editBandVisible, true)
})

function ownedBandPage(api = {}, extra = {}) {
  const result = page(api, { tab: 'bands', bandSlotId: '1', ...extra })
  const row = { bandId: 'b', slotId: '1', bandName: '正式时间段', campusCode: '', effectiveStart: null, effectiveEnd: null, startTime: '08:00', endTime: '08:45', status: 'ENABLED', version: 0 }
  result.state.openEditBand(row)
  return { ...result, row }
}

test('same owned band reopening retains all six fields, error and authoritative baseline by reference', () => {
  const { state, row, calls } = ownedBandPage()
  const baseline = state.editorBaselines.bandEdit, owner = state.bandEditOwnerKey
  for (const [key, value] of Object.entries({ bandName: '未保存名称', campusCode: 'north', effectiveStart: '2027-10-01', effectiveEnd: '2027-12-31', startTime: '09:00', endTime: '09:45' })) state.updateEditorField('bandEdit', key, value)
  state.editBandError = '保留的失败提示'
  const form = state.editBandForm, draft = JSON.stringify(form)
  state.editBandVisible = false; calls.length = 0
  state.openEditBand(row)
  assert.equal(state.editBandVisible, true)
  assert.equal(state.editBandForm, form)
  assert.equal(JSON.stringify(state.editBandForm), draft)
  assert.equal(state.editorBaselines.bandEdit, baseline)
  assert.equal(state.bandEditOwnerKey, owner)
  assert.equal(state.editBandError, '保留的失败提示')
  assert.deepEqual(calls, [])
  assert.equal(state.unresolvedEditorDirty, false)
})

test('clean or legitimately saved band reopening hydrates fresh authoritative values without phantom dirty', async () => {
  const clean = ownedBandPage()
  clean.state.openEditBand({ ...clean.row, bandName: '最新正式名称' })
  assert.equal(clean.state.editBandForm.bandName, '最新正式名称')
  assert.equal(clean.state.editorBaselines.bandEdit, clean.state.editorSignature('bandEdit'))
  assert.equal(clean.state.bandEditOwnerKey, clean.state.bandEditorOwnerKey)
  assert.equal(clean.state.unresolvedEditorDirty, false)
  assert.deepEqual(clean.calls, [])
  const saved = ownedBandPage({ updateTimeBand: async () => bandAck() })
  prepare(saved.state, 'bandEdit')
  await saved.state.submitEditBand()
  assert.ok(saved.calls.includes('saved'))
  assert.equal(saved.state.bandEditOwnerKey, saved.state.bandEditorOwnerKey)
  saved.calls.length = 0
  saved.state.openEditBand({ ...bandAck().data, bandName: '回读的新正式名称' })
  assert.equal(saved.state.editBandForm.bandName, '回读的新正式名称')
  assert.equal(saved.state.editorBaselines.bandEdit, saved.state.editorSignature('bandEdit'))
  assert.equal(saved.state.unresolvedEditorDirty, false)
  assert.deepEqual(saved.calls, [])
})

test('invalid band ownership rejects requests before sending without reconstructing an owner from the form', async () => {
  for (const change of [state => { state.ctx.ctxKey = 'new-context' }, state => { state.academicFlow = { identity: () => 'new-identity' } }, state => { state.bandSlotId = '2' }, state => { state.tab = 'periods' }, state => state.invalidateBandEditOwner()]) {
    let requests = 0
    const { state, calls } = ownedBandPage({ updateTimeBand: async () => { requests++; return bandAck() } })
    state.updateEditorField('bandEdit', 'bandName', '当前未保存名称')
    const form = state.editBandForm, baseline = state.editorBaselines.bandEdit
    state.editBandError = '原编辑提示'; calls.length = 0
    change(state)
    await state.submitEditBand()
    assert.equal(requests, 0)
    assert.equal(state.editBandForm, form)
    assert.equal(state.editBandForm.bandName, '当前未保存名称')
    assert.equal(state.editorBaselines.bandEdit, baseline)
    assert.equal(state.editBandError, '原编辑提示')
    assert.deepEqual(calls, [])
  }
  let requests = 0
  const manual = page({ updateTimeBand: async () => { requests++; return bandAck() } }, { tab: 'bands', bandSlotId: '1' })
  manual.state.editBandForm = { bandId: 'b', bandName: '无归属输入', campusCode: '', effectiveStart: '', effectiveEnd: '', startTime: '08:00', endTime: '08:45' }
  await manual.state.submitEditBand()
  assert.equal(requests, 0)
  assert.equal(manual.state.bandEditOwnerKey, '')
  manual.state.bandSaving = true
  await manual.state.saveEditor('bandEdit', {}, async () => { requests++; return bandAck() }, 'b')
  assert.equal(requests, 0)
  assert.equal(manual.state.bandSaving, false)
  assert.equal(manual.calls.includes('saved'), false)
})

test('late band edit acknowledgement cannot adopt a changed identity, parent, tab or invalidated stored owner', async () => {
  for (const transition of ['context', 'identity', 'parent', 'tab', 'identity-back-after-watch']) {
    let finish, requests = 0, identity = 'identity-A'
    const { state, definition, calls } = ownedBandPage({ updateTimeBand: () => { requests++; return new Promise(resolve => { finish = resolve }) } }, { academicFlow: { identity: () => identity } })
    prepare(state, 'bandEdit')
    state.editBandError = '保留的编辑提示'
    const form = state.editBandForm, baseline = state.editorBaselines.bandEdit, draft = JSON.stringify(form)
    const pending = state.submitEditBand(); assert.equal(requests, 1)
    if (transition === 'context') state.ctx.ctxKey = 'new-context'
    else if (transition === 'identity') identity = 'identity-B'
    else if (transition === 'parent') state.bandSlotId = '2'
    else if (transition === 'tab') state.tab = 'periods'
    else {
      identity = 'identity-B'
      // This VM fixture has no reactive runtime: explicitly invoke the actual
      // synchronous watcher before restoring the provider's identity value.
      definition.watch.slotEditorContextKey.handler.call(state)
      identity = 'identity-A'
    }
    finish(bandAck()); await pending
    assert.equal(state.editBandForm, form)
    assert.equal(JSON.stringify(state.editBandForm), draft)
    assert.equal(state.editorBaselines.bandEdit, baseline)
    assert.equal(state.editBandError, '保留的编辑提示')
    assert.equal(calls.includes('success'), false)
    assert.equal(calls.includes('saved'), false)
    assert.equal(state.bandSaving, false)
  }
})

test('band owner is invalidated by real route, context and lifecycle hooks while open and submit guards remain fail closed', async () => {
  for (const transition of ['route', 'context', 'unmount']) {
    let requests = 0
    const { state, definition, calls } = ownedBandPage({ updateTimeBand: async () => { requests++; return bandAck() } })
    state.updateEditorField('bandEdit', 'bandName', '未保存名称'); calls.length = 0
    if (transition === 'route') state.applyRouteSelection('periods', '1')
    else if (transition === 'context') { state.ctx.ctxKey = 'different'; definition.watch.slotEditorContextKey.handler.call(state) }
    else definition.beforeUnmount.call(state)
    assert.equal(state.bandEditOwnerKey, '')
    assert.equal(state.editBandVisible, false)
    await state.submitEditBand(); assert.equal(requests, 0)
    assert.equal(calls.includes('saved'), false)
  }
  for (const change of [state => { state.ctx.permissionPatterns = [] }, state => { state.bandAdding = true }, state => { state.disposed = true }]) {
    const { state, row } = ownedBandPage()
    const form = state.editBandForm; change(state)
    state.openEditBand({ ...row, bandName: '不应采用的值' })
    assert.equal(state.editBandForm, form)
  }
  const foreign = ownedBandPage(); const form = foreign.state.editBandForm
  foreign.state.openEditBand({ ...foreign.row, slotId: '2', bandName: '另一父节次的名称' })
  assert.equal(foreign.state.editBandForm, form)
})

test('same band reopening and a valid save retain each other hidden editor and template draft', async () => {
  for (const other of ['slotCreate', 'slotEdit', 'bandCreate', 'template']) {
    const { state, row, calls } = ownedBandPage({ updateTimeBand: async () => bandAck() })
    prepare(state, 'bandEdit')
    if (other === 'template') state.$refs.timeSlotTemplate = { preview: { items: [] }, loading: false, applying: false }
    else prepare(state, other)
    const form = state.editBandForm, baseline = state.editorBaselines.bandEdit
    state.editBandVisible = false; calls.length = 0
    state.openEditBand(row)
    assert.equal(state.editBandForm, form)
    assert.equal(state.editorBaselines.bandEdit, baseline)
    assert.deepEqual(calls, [])
    await state.submitEditBand()
    assert.ok(calls.includes('success'))
    assert.equal(calls.includes('saved'), false)
    assert.ok(calls.includes('dirty'))
  }
})

test('local band order validation retains input and error across same record reopening with zero requests', async () => {
  let requests = 0
  const { state, row, calls } = ownedBandPage({ updateTimeBand: async () => { requests++; return bandAck() } })
  state.updateEditorField('bandEdit', 'bandName', '未保存的失败输入')
  state.updateEditorField('bandEdit', 'endTime', '08:00')
  const form = state.editBandForm, baseline = state.editorBaselines.bandEdit
  await state.submitEditBand()
  assert.equal(requests, 0)
  assert.equal(state.editBandError, '结束时间应晚于开始时间')
  state.editBandVisible = false; state.openEditBand(row)
  assert.equal(state.editBandForm, form)
  assert.equal(state.editBandForm.bandName, '未保存的失败输入')
  assert.equal(state.editBandForm.endTime, '08:00')
  assert.equal(state.editorBaselines.bandEdit, baseline)
  assert.equal(state.editBandError, '结束时间应晚于开始时间')
  assert.equal(calls.includes('saved'), false)
})


test('different existing time band retains the original pending name baseline and error until an explicit decision', () => {
  const { state, calls } = page({}, { tab: 'bands', bandSlotId: '1', academicFlow: { identity: () => 'ordinary-local-identity' } })
  // Declared local records exercise actual SFC methods; they are not normal API or IAM evidence.
  const source = { bandId: 'declared-source-band', slotId: '1', bandName: '原时间段正式名称', campusCode: '', effectiveStart: null, effectiveEnd: null, startTime: '08:00', endTime: '08:45', status: 'ENABLED', version: 0 }
  const target = { ...source, bandId: 'declared-target-band', bandName: '另一时间段正式名称', campusCode: 'V61-A6-LOCAL-B' }
  state.bandRows = [source, target]
  state.openEditBand(source)
  state.updateEditorField('bandEdit', 'bandName', '原时间段未保存名称')
  state.editBandError = '原草稿的校验提示'
  const form = state.editBandForm, baseline = state.editorBaselines.bandEdit, owner = state.bandEditOwnerKey
  state.editBandVisible = false; calls.length = 0
  state.openEditBand(target)
  assert.equal(state.editBandForm.bandName, '原时间段未保存名称', 'different-record request must keep the source draft until the user decides')
  assert.equal(state.editBandForm, form)
  assert.equal(state.editBandForm.bandId, source.bandId)
  assert.equal(state.editorBaselines.bandEdit, baseline)
  assert.equal(state.bandEditOwnerKey, owner)
  assert.equal(state.editBandError, '原草稿的校验提示')
  assert.equal(calls.includes('saved'), false)
})


function pendingDifferentBandPage(extra = {}) {
  const result = ownedBandPage({}, { academicFlow: { identity: () => 'ordinary-band-identity' }, ...extra })
  const target = { ...result.row, bandId: 'target-band', bandName: '目标正式名称', campusCode: 'V61-A6-LOCAL-B', version: 0 }
  result.state.bandRows = [result.row, target]
  result.state.updateEditorField('bandEdit', 'bandName', '原时间段未保存名称')
  result.state.updateEditorField('bandEdit', 'endTime', '08:00')
  result.state.editBandError = '结束时间应晚于开始时间'
  result.state.editBandVisible = false; result.calls.length = 0
  return { ...result, target }
}

test('different band request preserves all source fields baseline owner and error until cancel reopens the original', () => {
  const { state, row, calls, target } = pendingDifferentBandPage()
  const form = state.editBandForm, fields = JSON.stringify(form), baseline = state.editorBaselines.bandEdit, owner = state.bandEditOwnerKey
  state.openEditBand(target)
  assert.equal(state.bandSwitchVisible, true); assert.equal(state.editBandVisible, false)
  assert.equal(state.editBandForm, form); assert.equal(JSON.stringify(state.editBandForm), fields)
  assert.equal(state.editorBaselines.bandEdit, baseline); assert.equal(state.bandEditOwnerKey, owner)
  assert.equal(state.editBandError, '结束时间应晚于开始时间'); assert.equal(state.unresolvedEditorDirty, false)
  assert.equal(state.pendingBandSwitch.sourceId, row.bandId); assert.equal(state.pendingBandSwitch.targetId, target.bandId)
  assert.equal(state.pendingBandSwitch.targetVersion, target.version)
  state.cancelBandSwitch()
  assert.equal(state.bandSwitchVisible, false); assert.equal(state.pendingBandSwitch, null); assert.equal(state.editBandVisible, true)
  assert.equal(state.editBandForm, form); assert.equal(JSON.stringify(state.editBandForm), fields)
  assert.equal(state.editorBaselines.bandEdit, baseline); assert.equal(state.editBandError, '结束时间应晚于开始时间')
  assert.deepEqual(calls, [])
})

test('explicit different band discard adopts only the current target and retains other drafts templates and historical dirty', () => {
  for (const other of ['none', 'slotCreate', 'slotEdit', 'bandCreate', 'template', 'historical']) {
    const { state, calls, target } = pendingDifferentBandPage()
    if (other === 'template') state.$refs.timeSlotTemplate = { preview: { items: [] }, loading: false, applying: false }
    else if (other === 'historical') state.unresolvedEditorDirty = true
    else if (other !== 'none') prepare(state, other)
    calls.length = 0
    state.openEditBand(target); assert.equal(state.bandSwitchVisible, true)
    state.confirmBandSwitch()
    assert.equal(state.bandSwitchVisible, false); assert.equal(state.pendingBandSwitch, null); assert.equal(state.editBandVisible, true)
    assert.equal(state.editBandForm.bandId, target.bandId); assert.equal(state.editBandForm.bandName, target.bandName)
    assert.equal(state.editBandError, ''); assert.equal(state.editorBaselines.bandEdit, state.editorSignature('bandEdit'))
    assert.equal(state.bandEditOwnerKey, state.bandEditorOwnerKey)
    assert.equal(calls.includes('success'), false)
    if (other === 'none') { assert.ok(calls.includes('saved')); assert.equal(state.unresolvedEditorDirty, false) }
    else { assert.equal(calls.includes('saved'), false); assert.ok(calls.includes('dirty')) }
    if (other === 'historical') assert.equal(state.unresolvedEditorDirty, true)
    calls.length = 0; const form = state.editBandForm
    state.confirmBandSwitch(); assert.equal(state.editBandForm, form); assert.deepEqual(calls, [])
  }
})

test('stale band decisions reject changed actual ownership source fields baseline error and target fields or separate version', () => {
  for (const change of ['ctx', 'identity', 'parent', 'tab', 'stored owner', 'source name', 'source baseline', 'source error', 'source id', 'target name', 'target version', 'target parent', 'target removed']) {
    let identity = 'first-identity'
    const { state, calls, target } = pendingDifferentBandPage({ academicFlow: { identity: () => identity } })
    state.openEditBand(target)
    const form = state.editBandForm
    if (change === 'ctx') state.ctx.ctxKey = 'new-context'
    else if (change === 'identity') identity = 'changed-identity'
    else if (change === 'parent') state.bandSlotId = '2'
    else if (change === 'tab') state.tab = 'periods'
    else if (change === 'stored owner') state.bandEditOwnerKey = 'invalid-owner'
    else if (change === 'source name') state.editBandForm.bandName = 'newer input'
    else if (change === 'source baseline') state.editorBaselines.bandEdit = 'newer-baseline'
    else if (change === 'source error') state.editBandError = 'newer-error'
    else if (change === 'source id') state.editBandForm.bandId = 'different-source'
    else if (change === 'target name') target.bandName = 'changed-target'
    else if (change === 'target version') target.version++
    else if (change === 'target parent') target.slotId = '2'
    else state.bandRows = []
    const input = JSON.stringify(form), baseline = state.editorBaselines.bandEdit, error = state.editBandError
    state.confirmBandSwitch()
    assert.equal(state.editBandForm, form, change); assert.equal(JSON.stringify(state.editBandForm), input, change)
    assert.equal(state.editorBaselines.bandEdit, baseline, change); assert.equal(state.editBandError, error, change)
    assert.equal(state.bandSwitchVisible, false); assert.equal(state.pendingBandSwitch, null)
    assert.deepEqual(calls, [], change)
  }
})

test('permission busy and disposed band handlers never replace drafts or reopen a stale owner', () => {
  for (const handler of ['confirmBandSwitch', 'cancelBandSwitch']) for (const change of ['permission', 'busy', 'disposed']) {
    const { state, calls, target } = pendingDifferentBandPage()
    state.openEditBand(target); const form = state.editBandForm, baseline = state.editorBaselines.bandEdit
    if (change === 'permission') state.ctx.permissionPatterns = []
    else if (change === 'busy') state.bandSaving = true
    else state.disposed = true
    state[handler]()
    assert.equal(state.editBandForm, form); assert.equal(state.editorBaselines.bandEdit, baseline)
    assert.equal(state.editBandError, '结束时间应晚于开始时间'); assert.equal(state.editBandVisible, false)
    assert.equal(state.bandSwitchVisible, false); assert.equal(state.pendingBandSwitch, null); assert.deepEqual(calls, [])
  }
})

test('real owner watcher route adoption and unmount invalidate band-switch intent and prevent late re-adoption', () => {
  // This existing VM harness calls actual hooks explicitly; it does not emulate Vue reactivity or normal IAM changes.
  for (const transition of ['context', 'route', 'unmount']) {
    const { state, definition, calls, target } = pendingDifferentBandPage()
    state.openEditBand(target); assert.equal(state.bandSwitchVisible, true)
    if (transition === 'context') { state.ctx.ctxKey = 'changed'; definition.watch.slotEditorContextKey.handler.call(state) }
    else if (transition === 'route') { state.$route.query = { tab: 'bands', slotId: '2' }; state.applyRouteSelection('bands', '2') }
    else definition.beforeUnmount.call(state)
    assert.equal(state.bandSwitchVisible, false); assert.equal(state.pendingBandSwitch, null)
    const form = state.editBandForm, before = JSON.stringify(form); calls.length = 0
    state.confirmBandSwitch(); state.cancelBandSwitch()
    assert.equal(state.editBandForm, form); assert.equal(JSON.stringify(state.editBandForm), before); assert.deepEqual(calls, [])
  }
})

test('clean and legitimately saved band editors switch directly while same-row pending and current intent resist extra opens', async () => {
  const clean = ownedBandPage(); const target = { ...clean.row, bandId: 'target', bandName: '直接打开目标', version: 0 }
  clean.state.bandRows = [clean.row, target]
  clean.state.openEditBand(target)
  assert.equal(clean.state.bandSwitchVisible, false); assert.equal(clean.state.editBandForm.bandId, target.bandId)
  assert.equal(clean.state.editorBaselines.bandEdit, clean.state.editorSignature('bandEdit')); assert.deepEqual(clean.calls, [])
  const saved = ownedBandPage({ updateTimeBand: async () => bandAck() }); prepare(saved.state, 'bandEdit'); await saved.state.submitEditBand()
  saved.state.bandRows = [saved.row, target]; saved.calls.length = 0; saved.state.openEditBand(target)
  assert.equal(saved.state.bandSwitchVisible, false); assert.equal(saved.state.editBandForm.bandId, target.bandId); assert.deepEqual(saved.calls, [])
  const pending = pendingDifferentBandPage(); const form = pending.state.editBandForm
  pending.state.openEditBand(pending.row); assert.equal(pending.state.bandSwitchVisible, false); assert.equal(pending.state.editBandForm, form)
  pending.state.editBandVisible = false; pending.state.openEditBand(pending.target); const intent = pending.state.pendingBandSwitch
  pending.state.openEditBand(pending.row); assert.equal(pending.state.pendingBandSwitch, intent); assert.equal(pending.state.editBandForm, form)
  pending.state.cancelBandSwitch(); assert.equal(pending.state.editBandVisible, true); assert.equal(pending.state.editBandForm, form)
})

// Public error presentation uses the actual adapter and shared components. These
// are declared transport errors shaped like client159-174, not live HTTP faults.
import { createRequire as slotTypedCreateRequire } from 'node:module'
import { setImmediate as slotTypedSetImmediate } from 'node:timers'
import { normalizeUiError as slotTypedNormalize } from '../src/utils/presentationSafety.js'
import { academicIdentity as slotTypedIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import * as slotTypedDialog from '../src/services/systemDialog.js'
const slotTypedRequire = slotTypedCreateRequire(import.meta.url)
const slotTypedVue = slotTypedRequire('vue')
const { parse: slotTypedParse, compileTemplate: slotTypedCompileTemplate } = slotTypedRequire('@vue/compiler-sfc')
const slotTypedRead = relative => fs.readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
function slotTypedCompile(relative, scope = {}) {
  const { descriptor, errors } = slotTypedParse(slotTypedRead(relative), { filename: relative }); assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const result = slotTypedCompileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } }); assert.deepEqual(result.errors, [])
  component.render = new Function('Vue', result.code)(slotTypedVue)
  return component
}
const slotTypedNode = (type, value = '') => ({ type, tagName: type.toUpperCase(), value, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } })
const slotTypedWalk = node => [node, ...node.children.flatMap(slotTypedWalk)]
const slotTypedText = node => node.type === '#comment' ? '' : node.value + node.children.map(slotTypedText).join('')
const slotTypedTick = async () => { await new Promise(resolve => slotTypedSetImmediate(resolve)); await slotTypedVue.nextTick() }
const slotTypedClasses = (root, name) => slotTypedWalk(root).filter(node => String(node.props.class || '').split(/\s+/).includes(name))
const slotTypedVisual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => slotTypedVue.h('section', {}, [slots.actions?.(), slots.default?.()]) } })
async function slotTypedFixture(t, { status, code, bizCode, message, traceId, details = null }) {
  const previous = { window: Object.getOwnPropertyDescriptor(globalThis, 'window'), document: Object.getOwnPropertyDescriptor(globalThis, 'document') }
  const body = slotTypedNode('body'), requests = [], responses = [], errors = [], warnings = []
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await slotTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(slotTypedDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const { h, reactive, createRenderer } = slotTypedVue
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = reactive({ ctxKey: 'DECLARED_TIMESLOT_ERROR_SCOPE', permissionPatterns: ['academicAffairs.timeslot.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  const payload = { code, bizCode, message, traceId }
  const normalized = slotTypedNormalize(payload), transportError = new Error(normalized.userMessage)
  Object.assign(transportError, { biz: true, httpStatus: status, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    assert.equal(path, '/academic-affairs/time-slots'); assert.deepEqual(options.params, {})
    requests.push({ path, params: options.params, method: options.method || 'GET' }); assert.ok(requests.length <= 2)
    if (requests.length === 1) throw transportError
    return { items: [] }
  }
  const prohibited = () => { throw new Error('只读错误状态回归禁止业务动作/模板/权限修改/其他API') }
  const apiSource = slotTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const originalAPI = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const api = { ...originalAPI, getTimeSlots(includeDisabled) { assert.equal(includeDisabled, false); return originalAPI.getTimeSlots(includeDisabled).then(response => { responses.push(structuredClone(response)); return response }) } }
  const Global = slotTypedCompile('components/common/AppGlobalState.vue', { normalizeUiError: slotTypedNormalize })
  const ErrorState = slotTypedCompile('components/business/ErrorState.vue', { AppGlobalState: Global, normalizeUiError: slotTypedNormalize })
  const Loading = slotTypedCompile('components/business/LoadingState.vue', { AppGlobalState: Global }), Empty = slotTypedCompile('components/business/EmptyState.vue', { AppGlobalState: Global })
  const Button = slotTypedCompile('components/ui/AppButton.vue'), Drawer = slotTypedCompile('components/ui/AppDrawer.vue')
  const TimeSlot = slotTypedCompile('modules/academicAffairs/views/AaTimeSlotView.vue', {
    ModulePageShell: slotTypedVisual('DeclaredSlotErrorShell'), DataTable: slotTypedVisual('DeclaredUnrelatedSlotRows'), StatusTag: slotTypedVisual('DeclaredUnusedSlotStatus'), LoadingState: Loading, ErrorState, EmptyState: Empty,
    AppButton: Button, AppDrawer: Drawer, AppSectionCard: slotTypedVisual('DeclaredSlotErrorCardWithoutCheckboxHeader'), AppTextInput: slotTypedVisual('DeclaredUnopenedName'), AppNumberInput: slotTypedVisual('DeclaredUnopenedNumber'), AppFormItem: slotTypedVisual('DeclaredUnopenedForm'), AppDatePicker: slotTypedVisual('DeclaredUnopenedDate'), AppTimePicker: slotTypedVisual('DeclaredUnopenedTime'), AppTimeSlotPicker: slotTypedVisual('DeclaredUnopenedPicker'), AppConfirmDialog: slotTypedVisual('DeclaredUnopenedObjectDialog'), AppInlineAlert: slotTypedVisual('DeclaredUnrelatedAlert'), AaTimeSlotTemplatePanel: slotTypedVisual('DeclaredUnopenedTemplate'),
    academicAffairsApi: api, toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission, systemConfirm: slotTypedDialog.systemConfirm
  })
  const renderer = createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => slotTypedNode(type), createText: value => slotTypedNode('#text', value), createComment: value => slotTypedNode('#comment', value), setText(node, value) { node.value = value }, setElementText(node, value) { node.value = value; node.children = [] }, parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp(node, key, _old, value) { node.props[key] = value }, insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(node); else parent.children.splice(i, 0, node) }, remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } } })
  const root = slotTypedNode('root'); app = renderer.createApp({ render: () => h(TimeSlot, { ctx }) })
  app.provide('academicFlow', { identity: () => slotTypedIdentity(claims, ctx) })
  app.config.globalProperties.$route = reactive({ path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots', query: {} })
  app.config.globalProperties.$router = { options: { history: { state: {} } }, push: prohibited, replace: prohibited, back: prohibited }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root); await slotTypedTick()
  assert.equal(requests.length, 1); assert.deepEqual(responses[0], { code, data: null, message: normalized.userMessage, bizCode, details, httpStatus: status, traceId })
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(slotTypedDialog.systemDialogState.visible, false)
  const buttons = label => slotTypedWalk(root).filter(node => node.type === 'button' && slotTypedText(node) === label)
  const retry = async () => {
    const matches = buttons('重试'); assert.equal(matches.length, 1); assert.equal(!!matches[0].props.disabled, false)
    const handlers = matches[0].props.onClick; assert.ok(handlers); const event = { type: 'click', target: matches[0], currentTarget: matches[0] }
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    await slotTypedTick(); assert.equal(requests.length, 2); assert.deepEqual(responses[1], { code: 0, data: [], message: 'ok' })
    assert.equal(slotTypedClasses(root, 'ags-error').length, 0); assert.equal(slotTypedClasses(root, 'ags-forbidden').length, 0); assert.equal(slotTypedClasses(root, 'ags-loading').length, 0); assert.equal(slotTypedClasses(root, 'ags-empty').length, 1)
  }
  return { root, requests, responses, buttons, retry, classes: name => slotTypedClasses(root, name), text: () => slotTypedText(root) }
}

test('timeslot actual typed HTTP500 overrides stale denial and its public retry recovers a healthy empty list', async t => {
  const f = await slotTypedFixture(t, { status: 500, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_SLOT_ERROR_500' })
  assert.equal(f.classes('ags-error').length, 1); assert.equal(f.classes('ags-forbidden').length, 0); assert.equal(f.classes('ags-empty').length, 0); assert.equal(f.classes('ags-loading').length, 0)
  assert.equal(f.buttons('重试').length, 1); assert.ok(f.text().includes('操作未完成，请稍后重试')); assert.ok(f.text().includes('DECLARED_SLOT_ERROR_500'))
  await f.retry()
})

test('timeslot actual typed HTTP403 keeps the real forbidden state without an ordinary retry or permission mutation', async t => {
  const f = await slotTypedFixture(t, { status: 403, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_SLOT_FORBIDDEN' })
  assert.equal(f.classes('ags-forbidden').length, 1); assert.equal(f.classes('ags-error').length, 0); assert.equal(f.classes('ags-empty').length, 0); assert.equal(f.classes('ags-loading').length, 0)
  assert.equal(f.buttons('重试').length, 0); assert.equal(f.buttons('返回').length, 1); assert.ok(f.text().includes('暂无访问权限')); assert.ok(f.text().includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')); assert.equal(f.requests.length, 1)
})

test('timeslot actual typed HTTP404 is a failed read with safe record-not-found feedback instead of an empty list', async t => {
  const f = await slotTypedFixture(t, { status: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', message: '读取失败', traceId: 'DECLARED_SLOT_NOT_FOUND' })
  assert.equal(f.classes('ags-error').length, 1); assert.equal(f.classes('ags-forbidden').length, 0); assert.equal(f.classes('ags-empty').length, 0); assert.equal(f.classes('ags-loading').length, 0)
  assert.equal(f.buttons('重试').length, 1); assert.ok(f.text().includes('记录不存在或已被删除'))
  assert.equal(f.classes('ags-code').length, 1); assert.ok(slotTypedText(f.classes('ags-code')[0]).includes('DECLARED_SLOT_NOT_FOUND')); assert.equal(f.requests.length, 1)
})

test('timeslot technical HTTP500 renders safe support feedback without SQL or stack details and public retry remains usable', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await slotTypedFixture(t, { status: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_SLOT_TECH_500', details })
  assert.equal(f.classes('ags-error').length, 1); assert.equal(f.classes('ags-forbidden').length, 0); assert.equal(f.classes('ags-empty').length, 0)
  assert.ok(f.text().includes('操作未完成，请稍后重试')); assert.equal(f.classes('ags-code').length, 1); assert.ok(slotTypedText(f.classes('ags-code')[0]).includes('DECLARED_SLOT_TECH_500'))
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(f.text().includes(raw), false)
  assert.deepEqual(f.responses[0].details, details); await f.retry()
})


// Selected-band error outlets use the entire actual TimeSlot/Shared/API producer.
// Transport and read-only slot101/102 are declarations, not a real permission failure.
async function bandTypedFixture(t, { status, code, bizCode, message, traceId, details = null }) {
  const previous = { window: Object.getOwnPropertyDescriptor(globalThis, 'window'), document: Object.getOwnPropertyDescriptor(globalThis, 'document') }
  const body = slotTypedNode('body'), requests = [], responses = [], slotResponses = [], errors = [], warnings = []
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await slotTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(slotTypedDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const { h, reactive, createRenderer } = slotTypedVue
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = reactive({ ctxKey: 'DECLARED_TIMESLOT_BAND_ERROR_SCOPE', permissionPatterns: ['academicAffairs.timeslot.view', 'academicAffairs.classTimeBand.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  const payload = { code, bizCode, message, traceId }
  const normalized = slotTypedNormalize(payload), transportError = new Error(normalized.userMessage)
  Object.assign(transportError, { biz: true, httpStatus: status, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.timeslot.manage'), false)
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.classTimeBand.manage'), false)
  // Established independent12-field slot grammar, not real DB or authorization facts.
  const slotsDTO = ['101', '102'].map((slotId, index) => ({ slotId, slotNo: index + 1, slotName: `声明独立节次${slotId}`, startTime: '', endTime: '', campusCode: '', enabled: true, status: 'ENABLED', version: 0, timeBandCount: 0, referenceCount: 0, referenceStatus: 'UNUSED' }))
  const counts = { slots: 0, bands: 0 }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    requests.push({ path, params: options.params ?? null, method: options.method || 'GET' }); assert.ok(requests.length <= 3)
    if (path === '/academic-affairs/time-slots') {
      assert.equal(++counts.slots, 1); assert.deepEqual(options.params, { includeDisabled: true }); return { items: structuredClone(slotsDTO) }
    }
    assert.equal(path, '/academic-affairs/time-slots/101/time-bands'); assert.equal(options.params, undefined)
    assert.ok(++counts.bands <= 2)
    if (counts.bands === 1) throw transportError
    return { items: [] }
  }
  const prohibited = () => { throw new Error('只读错误状态回归禁止业务动作/模板/权限修改/其他API') }
  const apiSource = slotTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const originalAPI = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const api = { ...originalAPI,
    getTimeSlots(includeDisabled) { assert.equal(includeDisabled, true); return originalAPI.getTimeSlots(includeDisabled).then(response => { slotResponses.push(structuredClone(response)); return response }) },
    getTimeBands(id) { assert.equal(String(id), '101'); return originalAPI.getTimeBands(id).then(response => { responses.push(structuredClone(response)); return response }) }
  }
  const Global = slotTypedCompile('components/common/AppGlobalState.vue', { normalizeUiError: slotTypedNormalize })
  const ErrorState = slotTypedCompile('components/business/ErrorState.vue', { AppGlobalState: Global, normalizeUiError: slotTypedNormalize })
  const Loading = slotTypedCompile('components/business/LoadingState.vue', { AppGlobalState: Global }), Empty = slotTypedCompile('components/business/EmptyState.vue', { AppGlobalState: Global })
  const Button = slotTypedCompile('components/ui/AppButton.vue'), Drawer = slotTypedCompile('components/ui/AppDrawer.vue')
  const TimeSlot = slotTypedCompile('modules/academicAffairs/views/AaTimeSlotView.vue', {
    ModulePageShell: slotTypedVisual('DeclaredSlotErrorShell'), DataTable: slotTypedVisual('DeclaredUnrelatedSlotRows'), StatusTag: slotTypedVisual('DeclaredUnusedSlotStatus'), LoadingState: Loading, ErrorState, EmptyState: Empty,
    AppButton: Button, AppDrawer: Drawer, AppSectionCard: slotTypedVisual('DeclaredSlotErrorCardWithoutCheckboxHeader'), AppTextInput: slotTypedVisual('DeclaredUnopenedName'), AppNumberInput: slotTypedVisual('DeclaredUnopenedNumber'), AppFormItem: slotTypedVisual('DeclaredUnopenedForm'), AppDatePicker: slotTypedVisual('DeclaredUnopenedDate'), AppTimePicker: slotTypedVisual('DeclaredUnopenedTime'), AppTimeSlotPicker: slotTypedVisual('DeclaredUnopenedPicker'), AppConfirmDialog: slotTypedVisual('DeclaredUnopenedObjectDialog'), AppInlineAlert: slotTypedVisual('DeclaredUnrelatedAlert'), AaTimeSlotTemplatePanel: slotTypedVisual('DeclaredUnopenedTemplate'),
    academicAffairsApi: api, toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission, systemConfirm: slotTypedDialog.systemConfirm
  })
  const renderer = createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => slotTypedNode(type), createText: value => slotTypedNode('#text', value), createComment: value => slotTypedNode('#comment', value), setText(node, value) { node.value = value }, setElementText(node, value) { node.value = value; node.children = [] }, parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp(node, key, _old, value) { node.props[key] = value }, insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(node); else parent.children.splice(i, 0, node) }, remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } } })
  const root = slotTypedNode('root'); app = renderer.createApp({ render: () => h(TimeSlot, { ctx }) })
  app.provide('academicFlow', { identity: () => slotTypedIdentity(claims, ctx) })
  app.config.globalProperties.$route = reactive({ path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots?tab=bands&slotId=101', query: { tab: 'bands', slotId: '101' } })
  app.config.globalProperties.$router = { options: { history: { state: {} } }, push: prohibited, replace: prohibited, back: prohibited }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root)
  for (let i = 0; i < 8; i++) { await slotTypedTick(); if (responses.length === 1 && !slotTypedClasses(root, 'ags-loading').length) break }
  assert.deepEqual(counts, { slots: 1, bands: 1 }); assert.equal(requests.length, 2)
  assert.deepEqual(slotResponses, [{ code: 0, data: slotsDTO, message: 'ok' }])
  const activeTab = slotTypedWalk(root).filter(node => node.type === 'button' && slotTypedText(node) === '上课时间段' && node.props['aria-current'] === 'page')
  assert.equal(activeTab.length, 1); assert.ok(slotTypedText(root).includes('节次 101'))
  for (const label of ['新增节次', '添加节次', '添加时间段']) assert.equal(slotTypedWalk(root).filter(node => node.type === 'button' && slotTypedText(node) === label).length, 0)
  assert.deepEqual(responses[0], { code, data: null, message: normalized.userMessage, bizCode, details, httpStatus: status, traceId })
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(slotTypedDialog.systemDialogState.visible, false)
  const buttons = label => slotTypedWalk(root).filter(node => node.type === 'button' && slotTypedText(node) === label)
  const retry = async () => {
    const matches = buttons('重试'); assert.equal(matches.length, 1); assert.equal(!!matches[0].props.disabled, false)
    const handlers = matches[0].props.onClick; assert.ok(handlers); const event = { type: 'click', target: matches[0], currentTarget: matches[0] }
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    await slotTypedTick(); assert.deepEqual(counts, { slots: 1, bands: 2 }); assert.equal(requests.length, 3)
    assert.deepEqual(slotResponses, [{ code: 0, data: slotsDTO, message: 'ok' }]); assert.ok(slotTypedText(root).includes('节次 101')); assert.ok(slotTypedText(root).includes('该节次尚未配置上课时间段'))
    assert.deepEqual(responses[1], { code: 0, data: [], message: 'ok' })
    assert.equal(slotTypedClasses(root, 'ags-error').length, 0); assert.equal(slotTypedClasses(root, 'ags-forbidden').length, 0); assert.equal(slotTypedClasses(root, 'ags-loading').length, 0); assert.equal(slotTypedClasses(root, 'ags-empty').length, 1)
  }
  const assertState = state => {
    assert.equal(slotTypedClasses(root, `ags-${state}`).length, 1)
    for (const other of ['error', 'forbidden', 'empty', 'loading'].filter(value => value !== state)) assert.equal(slotTypedClasses(root, `ags-${other}`).length, 0)
  }
  const support = () => {
    const codes = slotTypedClasses(root, 'ags-code'); assert.equal(codes.length, 1); assert.equal(slotTypedText(codes[0]), `实施人员使用错误码：${traceId}`)
    const descriptions = slotTypedClasses(root, 'ags-desc'); assert.equal(descriptions.length, 1)
    if (status === 404 && bizCode === 'RECORD_NOT_FOUND') assert.equal(slotTypedText(descriptions[0]), '记录不存在或已被删除')
    else assert.equal(slotTypedText(descriptions[0]), '操作未完成，请稍后重试')
  }
  return { root, requests, responses, buttons, retry, assertState, support, classes: name => slotTypedClasses(root, name), text: () => slotTypedText(root) }
}


test('time bands actual HTTP500 overrides stale denial and public retry rereads only selected bands', async t => {
  const f = await bandTypedFixture(t, { status: 500, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_BAND_ERROR_500' })
  f.assertState('error'); f.support(); assert.equal(f.buttons('重试').length, 1)
  await f.retry()
})

test('time bands actual HTTP403 remains forbidden without ordinary retry or permission mutation', async t => {
  const f = await bandTypedFixture(t, { status: 403, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_BAND_FORBIDDEN' })
  f.assertState('forbidden'); assert.equal(f.buttons('重试').length, 0); assert.equal(f.buttons('返回').length, 1)
  assert.ok(f.text().includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')); assert.equal(f.requests.length, 2)
})

test('time bands actual HTTP404 keeps record-not-found feedback distinct from healthy empty bands', async t => {
  const f = await bandTypedFixture(t, { status: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', message: '读取失败', traceId: 'DECLARED_BAND_NOT_FOUND' })
  f.assertState('error'); f.support(); assert.equal(f.buttons('重试').length, 1); assert.equal(f.requests.length, 2)
})

test('time bands actual technical HTTP500 keeps full adapter details private and public retry recovers', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await bandTypedFixture(t, { status: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_BAND_TECH_500', details })
  f.assertState('error'); f.support(); assert.deepEqual(f.responses[0].details, details); assert.equal(f.buttons('重试').length, 1)
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(f.text().includes(raw), false)
  await f.retry()
})

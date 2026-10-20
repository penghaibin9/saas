import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'

const frameSource = fs.readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue', import.meta.url), 'utf8')
const shellGuardSource = frameSource.slice(frameSource.indexOf('async function confirmUnsubmitted('), frameSource.indexOf('onBeforeRouteLeave(confirmUnsubmitted)'))

test('prefilled position forms leave without confirmation while real changes still use the authoritative guard', async () => {
  const savedWindow = globalThis.window, savedDocument = globalThis.document, savedElement = globalThis.Element
  let before, after, input, accept = false, confirmations = 0
  const from = { name: 'internship-position-edit', path: '/admin/internship/positions/4/edit', fullPath: '/admin/internship/positions/4/edit?batchId=1' }
  const to = { name: 'internship-position-detail', path: '/admin/internship/positions/4', fullPath: '/admin/internship/positions/4?batchId=1' }
  globalThis.Element = class { matches() { return true } closest() { return null } }
  globalThis.window = { addEventListener() {}, removeEventListener() {}, confirm() { throw new Error('native confirmation must not run') } }
  globalThis.document = { addEventListener(name, fn) { if (name === 'input') input = fn }, removeEventListener() {}, querySelectorAll: () => [{ value: '已有工作内容', readOnly: false, disabled: false, getClientRects: () => [1] }] }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, afterEach(fn) { after = fn } }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    window.__SAAS_DIRTY_FORM_GUARD__.registerConfirmation(() => { confirmations++; return Promise.resolve(accept) })
    const shellGuard = new Function('window', 'document', 'systemConfirm', `${shellGuardSource}; return confirmUnsubmitted`)(window, document, () => { confirmations++; return Promise.resolve(accept) })
    assert.equal(window.__SAAS_DIRTY_FORM_GUARD__.handlesRoute(from), true)
    assert.equal(await before(to, from), true); assert.equal(await shellGuard(to, from), true); assert.equal(confirmations, 0)
    input({ isTrusted: false, target: new Element() })
    assert.equal(await before(to, from), true)
    input({ isTrusted: true, target: new Element() })
    assert.equal(await before(to, from), false); assert.equal(confirmations, 1)
    accept = true; assert.equal(await before(to, from), true); assert.equal(await shellGuard(to, from), true); assert.equal(confirmations, 2)
    after(to, from, new Error('navigation cancelled')); assert.equal(window.__SAAS_DIRTY_FORM_GUARD__.isDirty(), true)
    window.__SAAS_DIRTY_FORM_GUARD__.markSaved(); assert.equal(await before(to, from), true); assert.equal(await shellGuard(to, from), true); assert.equal(confirmations, 2)
  } finally {
    dispose?.()
    if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow
    if (savedDocument === undefined) delete globalThis.document; else globalThis.document = savedDocument
    if (savedElement === undefined) delete globalThis.Element; else globalThis.Element = savedElement
  }
})

test('unmanaged forms keep the shared-shell fallback confirmation', async () => {
  let calls = 0
  const browser = { __SAAS_DIRTY_FORM_GUARD__: { handlesRoute: () => false }, confirm() { throw new Error('native confirmation must not run') } }
  const document = { querySelectorAll: () => [{ value: '未提交内容', readOnly: false, disabled: false, getClientRects: () => [1] }] }
  const guard = new Function('window', 'document', 'systemConfirm', `${shellGuardSource}; return confirmUnsubmitted`)(browser, document, () => { calls++; return Promise.resolve(false) })
  assert.equal(await guard({ path: '/other' }, { path: '/form' }), false); assert.equal(calls, 1)
  delete browser.__SAAS_DIRTY_FORM_GUARD__
  assert.equal(await guard({ path: '/other' }, { path: '/form' }), false); assert.equal(calls, 2)
})

test('campaign draft cancellation and failed navigation preserve dirty state until successful save or discard', async () => {
  const savedWindow = globalThis.window, savedDocument = globalThis.document
  let before, after, accept = false, confirmations = 0
  const from = { name: 'internship-recruitment-campaign-edit', fullPath: '/admin/internship/recruitment-campaigns/1/edit?batchId=23' }
  const to = { name: 'internship-recruitment-campaign-detail', fullPath: '/admin/internship/recruitment-campaigns/1?batchId=23' }
  globalThis.window = { addEventListener() {}, removeEventListener() {}, confirm() { throw new Error('native confirmation must not run') } }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, afterEach(fn) { after = fn } }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    const dirty = window.__SAAS_DIRTY_FORM_GUARD__
    dirty.registerConfirmation(() => { confirmations++; return Promise.resolve(accept) })
    dirty.markDirty()
    assert.equal(await before(to, from), false); assert.equal(dirty.isDirty(), true)
    accept = true
    assert.equal(await before(to, from), true); after(to, from, new Error('另一守卫拒绝导航'))
    assert.equal(dirty.isDirty(), true)
    assert.equal(await before(to, from), true); after(to, from, undefined)
    assert.equal(dirty.isDirty(), false); assert.equal(confirmations, 3)
    dirty.markDirty(); dirty.markSaved()
    assert.equal(await before(to, from), true); assert.equal(confirmations, 3)
  } finally {
    dispose?.()
    if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow
    if (savedDocument === undefined) delete globalThis.document; else globalThis.document = savedDocument
  }
})

test('plan draft guard allows workspace tabs but protects batch switch and refresh', async () => {
  const savedWindow = globalThis.window, savedDocument = globalThis.document
  let before, unload, confirmations = 0
  const from = { name: 'internship-plans', path: '/admin/internship/plans', fullPath: '/admin/internship/plans?batchId=1', query: { batchId: '1' } }
  globalThis.window = { addEventListener(name, fn) { if (name === 'beforeunload') unload = fn }, removeEventListener() {}, confirm() { throw new Error('native confirmation must not run') } }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, afterEach() {} }
  let dispose
  try {
    dispose = installDirtyFormGuard(router); const guard = window.__SAAS_DIRTY_FORM_GUARD__; guard.registerConfirmation(() => { confirmations++; return Promise.resolve(false) }); guard.markDirty()
    assert.equal(await before({ ...from, fullPath: from.fullPath + '&panel=tasks', query: { batchId: '1', panel: 'tasks' } }, from), true)
    assert.equal(await before({ ...from, fullPath: '/admin/internship/plans?batchId=2', query: { batchId: '2' } }, from), false)
    let prevented = false; unload({ preventDefault() { prevented = true } }); assert.equal(prevented, true)
    guard.markSaved(); assert.equal(await before({ ...from, fullPath: '/admin/internship/plans?batchId=2', query: { batchId: '2' } }, from), true)
    assert.equal(confirmations, 1)
  } finally {
    dispose?.()
    if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow
    if (savedDocument === undefined) delete globalThis.document; else globalThis.document = savedDocument
  }
})

test('in-page discard confirmation preserves drafts on cancel, dialog failure, and rejected navigation', async () => {
  const savedWindow = globalThis.window, savedDocument = globalThis.document
  const from = { name: 'internship-agreement-template-edit', fullPath: '/admin/internship/agreement-templates/5/edit?batchId=1' }
  const to = { name: 'internship-agreement-template-detail', fullPath: '/admin/internship/agreement-templates/5?batchId=1' }
  let before, after, unload, nativeCalls = 0, resolveDialog
  globalThis.window = { addEventListener(name, fn) { if (name === 'beforeunload') unload = fn }, removeEventListener() {}, confirm() { nativeCalls++; return false } }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, afterEach(fn) { after = fn } }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    const unregister = guard.registerConfirmation(() => new Promise(resolve => { resolveDialog = resolve }))
    guard.markDirty()
    const cancel = before(to, from); resolveDialog(false)
    assert.equal(await cancel, false); assert.equal(guard.isDirty(), true)
    const rejected = before(to, from); resolveDialog(true)
    assert.equal(await rejected, true); after(to, from, new Error('权限守卫拒绝'))
    assert.equal(guard.isDirty(), true)
    let prevented = false; unload({ preventDefault() { prevented = true } })
    assert.equal(prevented, true)
    const accepted = before(to, from); resolveDialog(true)
    assert.equal(await accepted, true); after(to, from)
    assert.equal(guard.isDirty(), false); assert.equal(nativeCalls, 0)
    guard.markDirty(); unregister(); guard.registerConfirmation(() => false)
    assert.equal(await before(to, from), false); assert.equal(nativeCalls, 0)
    guard.registerConfirmation(() => Promise.reject(new Error('dialog unavailable')))
    assert.equal(await before(to, from), false); assert.equal(guard.isDirty(), true)
  } finally {
    dispose?.()
    if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow
    if (savedDocument === undefined) delete globalThis.document; else globalThis.document = savedDocument
  }
})

test('unmounting an earlier confirmation host cannot remove a newer handler', async () => {
  const savedWindow = globalThis.window, savedDocument = globalThis.document
  const from = { name: 'internship-agreement-new', fullPath: '/admin/internship/agreements/new' }
  let before
  globalThis.window = { addEventListener() {}, removeEventListener() {}, confirm() { throw new Error('native fallback must not run') } }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, afterEach() {} }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    const removeOld = guard.registerConfirmation(() => false)
    guard.registerConfirmation(() => Promise.resolve(true)); removeOld(); guard.markDirty()
    assert.equal(await before({ fullPath: '/admin/internship/agreements' }, from), true)
    assert.equal(guard.isDirty(), true)
  } finally {
    dispose?.()
    if (savedWindow === undefined) delete globalThis.window; else globalThis.window = savedWindow
    if (savedDocument === undefined) delete globalThis.document; else globalThis.document = savedDocument
  }
})

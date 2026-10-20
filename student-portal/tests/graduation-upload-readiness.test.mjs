import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import {
  createGraduationUploadMonitor,
  graduationUploadPhase,
  graduationUploadReady,
  readGraduationUpload
} from '../src/services/graduationUploadReadiness.js'

const pending = (fileId = '101') => ({ fileId, fileName: '论文.pdf', scanStatus: 'PENDING', readyForBusiness: false, allowedActions: [] })
const clean = (fileId = '101') => ({ ...pending(fileId), scanStatus: 'CLEAN', readyForBusiness: true, allowedActions: ['preview', 'download'] })
const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function harness(t, options) {
  const files = []
  const states = []
  const listeners = new Map()
  const monitor = createGraduationUploadMonitor({
    intervalMs: 2,
    maxWaitMs: 1_000,
    requestTimeoutMs: 500,
    ...options,
    onFile: (file) => files.push({ ...file }),
    onState: (state) => {
      states.push(state)
      for (const listener of listeners.get(state.phase) || []) listener(state)
      listeners.delete(state.phase)
    }
  })
  t.after(() => monitor.stop())
  return {
    monitor, files, states,
    waitFor(phase) {
      if (states.at(-1)?.phase === phase) return Promise.resolve(states.at(-1))
      return new Promise((resolve) => listeners.set(phase, [...(listeners.get(phase) || []), resolve]))
    }
  }
}

test('scan status and server readiness are both required; absent or blocked facts fail closed', () => {
  for (const file of [null, {}, pending(), { ...clean(), readyForBusiness: false },
    { ...clean(), scanStatus: 'INFECTED' }, { ...clean(), scanStatus: 'ERROR' },
    { ...clean(), scanStatus: 'PENDING' }, { ...clean(), scanStatus: undefined },
    { ...clean(), readyForBusiness: 'true' }]) {
    assert.equal(graduationUploadReady(file), false)
  }
  assert.equal(graduationUploadReady(clean()), true)
  assert.equal(graduationUploadReady({ ...clean(), scanStatus: 'NOT_REQUIRED' }), true)
  assert.equal(graduationUploadPhase({ ...clean(), scanStatus: 'INFECTED' }), 'blocked')
})

test('metadata refresh cannot retain stale upload preview or download grants', async () => {
  const old = { ...clean(), canPreview: true, canDownload: true }
  const fresh = await readGraduationUpload(old, async () => ({ ...clean(), allowedActions: [] }))
  assert.equal(fresh.readyForBusiness, true)
  assert.equal(fresh.canPreview, false)
  assert.equal(fresh.canDownload, false)
  const waiting = await readGraduationUpload(old, async () => pending())
  assert.equal(waiting.readyForBusiness, false)
  assert.equal(waiting.canPreview, false)
})

test('metadata must match the exact uploaded file, immutable version and hash', async () => {
  await assert.rejects(readGraduationUpload(pending(), async () => clean('202')), /文件身份不一致/)
  await assert.rejects(readGraduationUpload(pending(), async () => null), /文件身份不一致/)
  await assert.rejects(readGraduationUpload({ ...pending(), fileVersionId: '5' }, async () => ({ ...clean(), fileVersionId: '6' })), /文件版本发生变化/)
  await assert.rejects(readGraduationUpload({ ...pending(), sha256: 'old' }, async () => ({ ...clean(), sha256: 'new' })), /文件版本发生变化/)
})

test('pending scan becomes ready from metadata without uploading or submitting again', { timeout: 3_000 }, async (t) => {
  let calls = 0
  const h = harness(t, { readMetadata: async (id) => { calls += 1; return calls === 1 ? pending(id) : clean(id) } })
  const ready = h.waitFor('ready')
  await h.monitor.start(pending())
  await ready
  assert.equal(calls, 2)
  assert.equal(h.files.at(-1).fileId, '101')
  assert.equal(h.files.at(-1).readyForBusiness, true)
  assert.equal(h.files.at(-1).canPreview, true)
  assert.ok(h.states.some((state) => state.phase === 'waiting'))
})

test('infected file stops polling and stays unavailable', async (t) => {
  let calls = 0
  const h = harness(t, { readMetadata: async () => { calls += 1; return { ...clean(), scanStatus: 'INFECTED' } } })
  await h.monitor.start(pending())
  assert.equal(calls, 1)
  assert.equal(h.states.at(-1).phase, 'blocked')
  assert.equal(h.files.at(-1).readyForBusiness, false)
  assert.equal(h.files.at(-1).canPreview, false)
})

test('bounded polling stops with a recheck state instead of endless requests', async (t) => {
  let clock = 0
  let calls = 0
  const h = harness(t, {
    maxWaitMs: 20,
    now: () => clock,
    readMetadata: async () => { calls += 1; clock = 21; return pending() }
  })
  await h.monitor.start(pending())
  assert.equal(calls, 1)
  assert.equal(h.states.at(-1).phase, 'timeout')
  assert.equal(h.files.at(-1).readyForBusiness, false)
})

test('network failure offers a same-file recheck without granting preview', async (t) => {
  let calls = 0
  const ids = []
  const h = harness(t, { readMetadata: async (id) => {
    ids.push(id)
    calls += 1
    if (calls === 1) throw new Error('offline')
    return clean(id)
  } })
  await h.monitor.start(pending())
  assert.equal(h.states.at(-1).phase, 'error')
  assert.equal(h.files.at(-1).canPreview, false)
  await h.monitor.recheck()
  assert.equal(h.states.at(-1).phase, 'ready')
  assert.deepEqual(ids, ['101', '101'])
})

test('a hanging metadata request has a finite local deadline', { timeout: 3_000 }, async (t) => {
  const h = harness(t, { requestTimeoutMs: 10, readMetadata: () => new Promise(() => {}) })
  await h.monitor.start(pending())
  assert.equal(h.states.at(-1).phase, 'error')
  assert.equal(h.files.at(-1).readyForBusiness, false)
})

test('repeated recheck clicks share the one active read', async (t) => {
  const response = deferred()
  let calls = 0
  const h = harness(t, { readMetadata: () => { calls += 1; return response.promise } })
  const first = h.monitor.start(pending())
  const second = h.monitor.recheck()
  const third = h.monitor.recheck()
  assert.equal(first, second)
  assert.equal(second, third)
  await Promise.resolve()
  response.resolve(clean())
  await first
  assert.equal(calls, 1)
})

test('changing the selected file prevents a late old response from unlocking the new file', async (t) => {
  const response = deferred()
  const h = harness(t, { readMetadata: (id) => id === '101' ? response.promise : Promise.resolve(clean(id)) })
  const old = h.monitor.start(pending('101'))
  await Promise.resolve()
  await h.monitor.start(pending('202'))
  response.resolve(clean('101'))
  await old
  assert.equal(h.files.at(-1).fileId, '202')
  assert.equal(h.files.at(-1).readyForBusiness, true)
  assert.equal(h.files.some((file) => file.fileId === '101' && file.readyForBusiness), false)
})

test('unmount cleanup prevents any later read result from changing parent state', async (t) => {
  const response = deferred()
  const h = harness(t, { readMetadata: () => response.promise })
  const running = h.monitor.start(pending())
  await Promise.resolve()
  h.monitor.stop()
  const count = h.files.length
  response.resolve(clean())
  await running
  assert.equal(h.files.length, count)
  assert.equal(h.files.at(-1).readyForBusiness, false)
})

test('first submission, materials and feedback use the shared recovery UI plus a final metadata check', async () => {
  for (const name of ['GraduationWorkbenchView', 'GraduationMaterialsView', 'GraduationFeedbackResubmitView']) {
    const source = await readFile(new URL(`../src/views/graduation/${name}.vue`, import.meta.url), 'utf8')
    assert.match(source, /GraduationUploadStatus/, name)
    assert.match(source, /v-model:file=/, name)
    assert.match(source, /readGraduationUpload\(/, name)
    assert.match(source, /fileSdk\.metadata\(fileId\)/, name)
    assert.match(source, /graduationUploadReady\(/, name)
  }
  const component = await readFile(new URL('../src/components/graduation/GraduationUploadStatus.vue', import.meta.url), 'utf8')
  assert.match(component, /aria-live="polite"/)
  assert.match(component, /重新检查文件状态/)
  assert.match(component, /onBeforeUnmount\(\(\) => monitor\.stop\(\)\)/)
  assert.match(component, /props\.locked/)
})

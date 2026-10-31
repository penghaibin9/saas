import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { emptyConflict } from '../src/modules/internship/composables/conflictGuard.js'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import { buildPreviewDescriptorFromFile } from '../src/components/file/viewer/viewer-contract.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const file = { fileId: '9007199254741004', fileName: '合成巡访.png', mimeType: 'image/png', readyForBusiness: true, canPreview: true }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(sdk = {}, api = {}) {
  let generation = 1
  const source = fs.readFileSync(new URL('../src/modules/internship/views/GuidanceVisitView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*? from [^\n]+\n/gm, '').replace('export default', 'return')
  const imports = [...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([, names]) => names.replace(/[{}]/g, '').split(',').map(name => name.trim()))
  const store = { selectedBatchId: '9007199254741001' }
  const deps = { emptyConflict, normalizeUiError, buildPreviewDescriptorFromFile, formatDateTime, fileSdk: sdk, guidanceVisitApi: api,
    currentSessionGeneration: () => generation, useInternshipBatchStore: () => store }
  const component = new Function(...imports, script)(...imports.map(name => deps[name] ?? {}))
  const vm = { ...component.data(), ctx: { ctxKey: '合成学校' } }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: getter.bind(vm) })
  vm.tab = 'visit'; vm.detail.data = { id: '9007199254741003', attachment: { fileId: file.fileId } }
  return { vm, store, component, switchAccount: () => generation++ }
}

test('巡访时间按学校所在时区展示跨日时间，原始时间不改写',()=>{
  const prior=process.env.TZ;process.env.TZ='Asia/Shanghai'
  try{const p=page();p.vm.detail.data.visitAt='2026-10-18T23:50:55Z';assert.equal(p.vm.detailItems.find(row=>row.label==='巡访时间').value,'2026-10-19 07:50');assert.equal(p.vm.detail.data.visitAt,'2026-10-18T23:50:55Z')}
  finally{if(prior===undefined)delete process.env.TZ;else process.env.TZ=prior}
})

test('巡访照片先核验正式授权与安全状态，再通过当前原单读取真实字节', async () => {
  const reads = [], bytes = new Uint8Array([1, 2, 3])
  const p = page({ metadata: async id => { reads.push(id); return file }, blob: async id => { reads.push(id); return bytes } })
  await p.vm.previewAtt()
  assert.equal(p.vm.previewDescriptor.fileId, file.fileId)
  assert.deepEqual(await p.vm.previewProvider.fetchBytes({ fileId: file.fileId }), bytes)
  assert.deepEqual(reads, [file.fileId, file.fileId])
  for (const changed of [{ readyForBusiness: false }, { canPreview: false }, { fileId: 'other' }]) {
    const denied = page({ metadata: async () => ({ ...file, ...changed }) })
    await denied.vm.previewAtt(); assert.equal(denied.vm.previewFile, null); assert.ok(denied.vm.fileError)
  }
})

test('迟到照片元信息及字节不能带入另一学生、批次、学校或账号，也不能恢复卸载页面', async () => {
  const changes = [p => p.vm.resetDetail(), p => { p.store.selectedBatchId = 'other' },
    p => { p.vm.ctx.ctxKey = 'other' }, p => p.switchAccount(), p => p.component.beforeUnmount.call(p.vm)]
  for (const change of changes) {
    const meta = deferred(), p = page({ metadata: () => meta.promise })
    const reading = p.vm.previewAtt(); change(p); meta.resolve(file); await reading
    assert.equal(p.vm.previewFile, null)
    const bytes = deferred(), q = page({ metadata: async () => file, blob: () => bytes.promise })
    await q.vm.previewAtt(); const loading = q.vm.previewProvider.fetchBytes({ fileId: file.fileId })
    change(q); bytes.resolve(new Uint8Array([1]))
    await assert.rejects(loading, error => /失效/.test(error.message))
  }
})

function locationRow(p) {
  Object.assign(p.vm.detail.data, { batchId: p.store.selectedBatchId, version: 3, hasLocation: true, canViewLocation: true })
}

test('学校查看巡访位置须按原单留痕，权限与上下文错误明确显示且不留下旧坐标', async () => {
  const calls = [], coords = { latitude: 28.1, longitude: 112.2, accuracyM: 8 }
  const p = page({}, { getVisitLocation: async (...args) => {
    calls.push(args); return { code: 0, data: { visitId: args[0], batchId: args[1].batchId, location: coords } }
  } })
  await p.vm.readLocation(); assert.equal(calls.length, 0)
  locationRow(p); await p.vm.readLocation(); assert.deepEqual(p.vm.locationData, coords)
  assert.deepEqual(calls[0], ['9007199254741003', { batchId: '9007199254741001', expectedVersion: 3, reason: '学校核对本次巡访发生位置' }])
  for (const request of [async () => { throw { status: 403 } }, async () => { throw { status: 409 } },
    async () => { throw { code: 'ERR_NETWORK' } }, async () => ({ code: 0, data: { visitId: 'other', batchId: 'other' } })]) {
    const q = page({}, { getVisitLocation: request }); locationRow(q)
    q.vm.locationData = coords; await q.vm.readLocation()
    assert.equal(q.vm.locationData, null); assert.ok(q.vm.locationError); assert.equal(q.vm.locationBusy, false)
  }
})

test('学校迟到位置响应不能进入另一原单、批次、学校、账号或卸载页', async () => {
  for (const change of [p => p.vm.resetDetail(), p => { p.store.selectedBatchId = 'other' },
    p => { p.vm.ctx.ctxKey = 'other' }, p => p.switchAccount(), p => p.component.beforeUnmount.call(p.vm)]) {
    const later = deferred(), p = page({}, { getVisitLocation: () => later.promise }); locationRow(p)
    const original = { ...p.vm.detail.data }, reading = p.vm.readLocation(); change(p)
    later.resolve({ code: 0, data: { visitId: original.id, batchId: original.batchId, location: { latitude: 28.1 } } }); await reading
    assert.equal(p.vm.locationData, null)
  }
})

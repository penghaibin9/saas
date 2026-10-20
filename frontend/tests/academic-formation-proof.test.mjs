import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { randomUUID } from 'node:crypto'
import test from 'node:test'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

const url = new URL('../src/modules/academicAffairs/components/teaching-tasks/AaFormationProof.vue', import.meta.url)
const fingerprint = 'a'.repeat(64)
const source = (canConfirm = true) => ({ programCourseId: '1000000000000000099', programName: '软件技术培养方案', programVersion: 2, courseName: '计算机基础', sourceFingerprint: fingerprint, canConfirm, confirmationBlockers: canConfirm ? [] : [{ code: 'SCHOOL_ONLY', message: '请由校教务责任人确认' }], proof: null })
function component(api, fileSdk = {}) {
  const text = readFileSync(url, 'utf8')
  const ctx = { teachingTaskWorkbenchApi: api, FileUploader: {}, FilePreviewer: {}, AppConfirmDialog: {}, fileSdk, crypto: { randomUUID } }
  vm.runInNewContext(text.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component ='), ctx)
  return ctx.component
}
function state(c, extra = {}) {
  const props = { programCourseId: '1000000000000000099', contextKey: 'school:52:47' }
  const s = Object.assign(props, c.data.call(props), c.methods, { $emit: (...args) => s.events.push(args), events: [] }, extra)
  for (const [key, fn] of Object.entries(c.computed)) Object.defineProperty(s, key, { enumerable: true, get: () => fn.call(s) })
  return s
}
function fill(s) { s.form = { formationMode: 'ADMIN_FIXED', evidenceLocator: '第3页第2节', reason: '学校正式文件明确为固定行政班' }; s.onUploaded({ fileId: '1000000000000000088', readyForBusiness: true, fileName: '开课依据.pdf' }) }

test('已有历史证明失效后仍显示有效性及全部中文阻断，不开放再次确认', async () => {
  for (const message of ['原来源已变化，既有证明不能解释当前来源字段', '证据文件内容或安全状态已变化，既有确认依据失效']) {
    const result = { ...source(false), proofValid: false, proofValidityLabel: '既有确认已失效', formationModeLabel: '既有确认已失效，需核对来源依据',
      proof: { formationModeLabel: '固定行政班', evidenceLocator: '第3页', reason: '原正式确认说明', evidence: null }, confirmationBlockers: [{ code: 'PROOF_CHANGED', message }] }
    let writes = 0
    const c = component({ getFormationProof: async () => ({ code: 0, data: result }), confirmFormationProof: async () => { writes++ } })
    const s = state(c); await s.load(); fill(s); s.openConfirmation(); await s.confirmProof()
    assert.equal(writes, 0)
    const text = readFileSync(url, 'utf8')
    const render = new Function('Vue', compile(text.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
    const visible = { ...s }; delete visible.$emit
    const empty = { render: () => null }
    const html = await renderToString(Vue.createSSRApp({ render, components: { FileUploader: empty, FilePreviewer: empty, AppConfirmDialog: empty }, setup: () => visible }))
    assert.match(html, /历史确认记录：固定行政班/)
    assert.match(html, /依据有效性：既有确认已失效/)
    assert.ok(html.includes(message))
    assert.doesNotMatch(html, /选择形成方式|PROOF_CHANGED/)
  }
})

test('学院或非严格授权只展示学校责任及阻断，不能提交', async () => {
  let writes = 0
  const c = component({ getFormationProof: async () => ({ code: 0, data: source(false) }), confirmFormationProof: async () => { writes++ } })
  const s = state(c)
  await s.load()
  fill(s); s.openConfirmation(); await s.confirmProof()
  assert.equal(writes, 0)
  const text = readFileSync(url, 'utf8')
  const render = new Function('Vue', compile(text.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const visible = { ...s }; delete visible.$emit
  const empty = { render: () => null }
  const html = await renderToString(Vue.createSSRApp({ render, components: { FileUploader: empty, FilePreviewer: empty, AppConfirmDialog: empty }, setup: () => visible }))
  assert.match(html, /请由校教务责任人确认/)
  assert.doesNotMatch(html, /选择形成方式|SCHOOL_ONLY|1000000000000000099/)
  s.result.canConfirm = 'true'
  assert.equal(s.canConfirm, false)
})

test('默认空表单、必填和扫描未完成阻断；就绪附件才允许打开具体确认', async () => {
  const c = component({ getFormationProof: async () => ({ code: 0, data: source() }) })
  const s = state(c); await s.load()
  assert.equal(s.form.formationMode, '')
  s.openConfirmation(); assert.equal(s.confirmVisible, false)
  fill(s)
  s.onUploaded({ fileId: '88', readyForBusiness: false })
  s.openConfirmation(); assert.equal(s.confirmVisible, false); assert.match(s.uploadMessage, /扫描|安全/)
  s.onUploaded({ fileId: '1000000000000000088', readyForBusiness: true })
  s.openConfirmation(); assert.equal(s.confirmVisible, true)
  assert.match(s.confirmMessage, /第2版.*计算机基础.*固定行政班/)
})

test('材料定位与依据说明必填，未知形成方式及无文件编号不产生写入', async () => {
  let writes = 0
  const c = component({ getFormationProof: async () => ({ code: 0, data: source() }), confirmFormationProof: async () => { writes++ } })
  const s = state(c); await s.load()
  for (const [key, value] of [['evidenceLocator', ' '], ['reason', '短'], ['formationMode', 'UNKNOWN']]) {
    fill(s); s.form[key] = value; s.openConfirmation(); await s.confirmProof()
    assert.equal(s.confirmVisible, false)
    assert.ok(s.error)
  }
  fill(s); s.onUploaded({ readyForBusiness: true }); s.openConfirmation(); await s.confirmProof()
  assert.equal(writes, 0)
})

test('大号对象正式提交带读取指纹与幂等键，防重提交后回读回执及通知当前核对', async () => {
  let reads = 0, finish
  const calls = []
  const c = component({ getFormationProof: async () => ({ code: 0, data: { ...source(), proofValid: reads > 0, proof: reads++ ? { proofId: '1', formationModeLabel: '固定行政班', reason: '已确认依据', confirmedAt: '2026-10-05' } : null } }), confirmFormationProof: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) } })
  const s = state(c); await s.load(); fill(s); s.openConfirmation()
  const saving = s.confirmProof(); await s.confirmProof()
  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], '1000000000000000099')
  assert.equal(calls[0][1].evidenceFileId, '1000000000000000088')
  assert.equal(calls[0][1].expectedSourceFingerprint, fingerprint)
  assert.ok(calls[0][1].idempotencyKey.length >= 8)
  finish({ code: 0, data: { ...source(), proof: { proofId: '1', formationModeLabel: '固定行政班', confirmedAt: '2026-10-05' } } })
  await saving
  assert.equal(reads, 2)
  assert.equal(s.result.proof.proofId, '1')
  assert.match(s.receipt, /正式确认/)
  assert.equal(s.events[0][0], 'confirmed')
})

test('提交后回读到失效历史记录或缺少有效性时，回执不能冒充有效确认', async () => {
  for (const proofValid of [false, undefined]) {
    let reads = 0
    const c = component({ getFormationProof: async () => ({ code: 0, data: reads++ ? { ...source(false), proofValid, proof: { proofId: '1' } } : source() }), confirmFormationProof: async () => ({ code: 0 }) })
    const s = state(c); await s.load(); fill(s); s.openConfirmation(); await s.confirmProof()
    assert.equal(s.canConfirm, false)
    assert.equal(s.result.proof.proofId, '1')
    assert.match(s.receipt, proofValid === false ? /当前依据已失效/ : /有效性尚未证明/)
    assert.doesNotMatch(s.receipt, /已正式确认|有效的正式回执/)
  }
})

test('冲突保留表单和附件不自动重读换指纹，重新核对后才能另行确认', async () => {
  let reads = 0
  const c = component({ getFormationProof: async () => { reads++; return { code: 0, data: source() } }, confirmFormationProof: async () => ({ code: 'DATA_CONFLICT', httpStatus: 409, message: '来源已变化' }) })
  const s = state(c); await s.load(); fill(s); s.openConfirmation(); await s.confirmProof()
  assert.equal(reads, 1)
  assert.equal(s.form.evidenceLocator, '第3页第2节')
  assert.equal(s.uploadedFile.fileId, '1000000000000000088')
  assert.equal(s.needsReload, true)
  assert.equal(s.canConfirm, false)
  assert.match(s.error, /重新读取/)
  await s.load(); assert.equal(s.needsReload, false)
  assert.equal(s.form.evidenceLocator, '第3页第2节')
})

test('学校与对象切换清空输入及旧结果，销毁及迟到读取/提交不覆盖新上下文', async () => {
  let finish
  const c = component({ getFormationProof: () => new Promise(resolve => { finish = resolve }) })
  const s = state(c); const loading = s.load(); const oldFinish = finish; s.contextKey = 'other-school'; c.watch.scopeKey.handler.call(s); oldFinish({ code: 0, data: source() }); await loading
  assert.equal(s.result, null); assert.equal(s.form.formationMode, '')
  c.beforeUnmount.call(s)
  assert.equal(s.result, null)
})

test('补证客户端只读和正式确认各一次，15秒超时并保真对象和请求', async () => {
  const text = readFileSync(new URL('../src/modules/academicAffairs/api/teaching-task-workbench.api.js', import.meta.url), 'utf8')
  const calls = [], ctx = { request: async (...args) => { calls.push(args); return source() } }
  vm.runInNewContext(text.replace(/^import .*$/gm, '').replace('export const teachingTaskWorkbenchApi =', 'api ='), ctx)
  await ctx.api.getFormationProof('1000000000000000099')
  await ctx.api.confirmFormationProof('1000000000000000099', { reason: '正常核对来源依据' })
  assert.equal(calls.length, 2)
  assert.equal(calls[0][0], '/academic-affairs/programs/courses/1000000000000000099/formation-proof')
  assert.equal(calls[0][1].timeoutMs, 15000)
  assert.equal(calls[1][1].timeoutMs, 15000)
  assert.equal(calls[1][1].method, 'POST')
  assert.equal(calls[1][1].body.reason, '正常核对来源依据')
})

test('上传后的安全状态正常回读，未就绪不放行，旧文件迟到状态不覆盖新文件', async () => {
  let finish, checkedId
  const c = component({ getFormationProof: async () => ({ code: 0, data: source() }) }, { metadata: id => { checkedId = id; return new Promise(resolve => { finish = resolve }) } })
  const s = state(c); await s.load(); fill(s)
  s.onUploaded({ fileId: '1000000000000000088', readyForBusiness: false })
  const pending = s.refreshFile()
  assert.equal(checkedId, '1000000000000000088')
  finish({ fileId: checkedId, readyForBusiness: true }); await pending
  s.openConfirmation(); assert.equal(s.confirmVisible, true)
  s.onUploaded({ fileId: '1000000000000000088', readyForBusiness: false })
  const old = s.refreshFile(); s.onUploaded({ fileId: '99', readyForBusiness: false })
  finish({ fileId: checkedId, readyForBusiness: true }); await old
  assert.equal(s.uploadedFile.fileId, '99')
  assert.equal(s.uploadedFile.readyForBusiness, false)
})

test('迟到确认不能发事件或写入新学校回执；网络失败保留同一请求幂等键', async () => {
  let finish
  const calls = []
  const c = component({ getFormationProof: async () => ({ code: 0, data: source() }), confirmFormationProof: (_id, body) => { calls.push(body); return new Promise(resolve => { finish = resolve }) } })
  const s = state(c); await s.load(); fill(s); s.openConfirmation()
  const saving = s.confirmProof(); s.contextKey = 'school-b'; c.watch.scopeKey.handler.call(s)
  finish({ code: 0 }); await saving
  assert.equal(s.receipt, '')
  assert.equal(s.events.length, 0)
  assert.equal(s.form.formationMode, '')
  let attempts = 0
  const retry = component({ getFormationProof: async () => ({ code: 0, data: source() }), confirmFormationProof: async (_id, body) => { calls.push(body); attempts++; return { code: 503, message: '网络暂不可用' } } })
  const r = state(retry); await r.load(); fill(r); r.openConfirmation(); await r.confirmProof()
  assert.equal(attempts, 1)
  assert.equal(r.form.reason, '学校正式文件明确为固定行政班')
  await r.confirmProof()
  assert.equal(calls.at(-1).idempotencyKey, calls.at(-2).idempotencyKey)
})

test('确认成功但正式回执未读回时不冒充回读成功，也不再次开放写入', async () => {
  let reads = 0
  const c = component({ getFormationProof: async () => ++reads === 1 ? { code: 0, data: source() } : { code: 503, message: '正式回执暂未读取' }, confirmFormationProof: async () => ({ code: 0 }) })
  const s = state(c); await s.load(); fill(s); s.openConfirmation(); await s.confirmProof()
  assert.equal(s.result, null)
  assert.equal(s.canConfirm, false)
  assert.match(s.receipt, /回执尚未读回/)
  assert.doesNotMatch(s.receipt, /已重新读取正式回执/)
  assert.match(s.error, /正式回执暂未读取/)
})

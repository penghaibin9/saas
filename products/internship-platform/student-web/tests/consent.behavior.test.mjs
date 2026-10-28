import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'

const context = { batchId: '9007199254741001', recordId: '9007199254741002' }
const task = { id: '9007199254741003', internshipId: context.recordId, consentType: 'STUDENT', status: 'PENDING', version: 0, contentVersion: '合成正文第一版', contentHash: 'saved-hash', contentSnapshot: '本地合成联调正文，不构成法律承诺。' }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const flush = async () => { await nextTick(); await Promise.resolve(); await Promise.resolve() }
async function page(t, overrides = {}, confirm = async () => true) {
  let generation = 1, saved = { ...task }
  const props = reactive({ context: { ...context } }), session = reactive({ token: 'synthetic', user: { tenantId: '11', userId: '18' } })
  const scope = effectScope(), lifecycle = {}, calls = []
  const document = { hidden: false, addEventListener: (_, fn) => { lifecycle.visibility = fn }, removeEventListener() {} }
  const api = {
    consents: async batch => { calls.push(['list', batch]); return [saved] },
    consentDetail: async id => { calls.push(['detail', id]); return { ...saved } },
    consentView: async id => { calls.push(['view', id]); saved = { ...saved, version: 1, viewedAt: '2026-10-06' }; return { ...saved } },
    consentConfirm: async (id, body) => { calls.push(['confirm', id, body]); saved = { ...saved, status: 'VALID', version: 2 }; const result = { ...saved }; delete result.contentSnapshot; return result },
    consentReject: async (id, body) => { calls.push(['reject', id, body]); saved = { ...saved, status: 'REJECTED', version: 2 }; const result = { ...saved }; delete result.contentSnapshot; return result },
    ...overrides
  }
  const deps = { computed, nextTick, ref, watch, defineProps: () => props, useSessionStore: () => session, document, api, systemConfirm: confirm, currentSessionGeneration: () => generation,
    onMounted: fn => { lifecycle.mount = fn }, onBeforeUnmount: fn => { lifecycle.unmount = fn } }
  const script = parse(fs.readFileSync(new URL('../src/views/internship/InternshipConsentPanel.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '')
  const names = ['items', 'selected', 'detail', 'loading', 'reading', 'busy', 'error', 'actionError', 'reason', 'conflict', 'receipt', 'canAct', 'loadList', 'openTask', 'submit', 'statusText', 'formatTime']
  const vm = scope.run(() => new Function(...Object.keys(deps), script + '\nreturn {' + names.join(',') + '}')(...Object.values(deps)))
  lifecycle.mount(); t.after(() => { lifecycle.unmount(); scope.stop() }); await flush()
  return { vm, calls, props, api, lifecycle, switchAccount: () => { generation++; session.user = { tenantId: '12', userId: '19' } }, hide: () => { document.hidden = true; lifecycle.visibility() } }
}

test('正文已渲染才登记阅读，确认使用新版并从服务端同单回读', async t => {
  const p = await page(t); let rendered = false
  const stop = watch(p.vm.detail, () => { rendered = true }, { flush: 'post' }); t.after(stop)
  p.api.consentView = async id => { assert.ok(rendered); assert.equal(id, task.id); assert.equal(p.vm.detail.value.contentSnapshot, task.contentSnapshot); return { ...task, version: 1, viewedAt: '2026-10-06' } }
  await p.vm.openTask(task); assert.ok(rendered); await p.vm.submit('confirm')
  const sent = p.calls.find(x => x[0] === 'confirm')
  assert.deepEqual(sent.slice(1), [task.id, { expectedVersion: 1, contentVersion: task.contentVersion, contentHash: task.contentHash, deviceDigest: 'student-portal' }])
  assert.equal(p.vm.detail.value.status, 'VALID'); assert.equal(p.vm.detail.value.contentSnapshot, task.contentSnapshot)
  assert.equal(p.vm.receipt.value.readback, true); assert.equal(p.vm.canAct.value, false)
  assert.ok(p.calls.filter(x => x[0] === 'list').every(x => x[1] === context.batchId))
  assert.equal(p.vm.formatTime('2026-10-05T23:17:10'), p.vm.formatTime('2026-10-06T07:17:10+08:00'))
  assert.ok(p.vm.formatTime('2026-10-05T23:17:10').includes('07:17'))
})

test('阅读响应在途时两项写动作都不发送，弹框前锁定防重复', async t => {
  const read = deferred(), modal = deferred()
  const p = await page(t, { consentView: () => read.promise }, () => modal.promise)
  const opening = p.vm.openTask(task); await flush(); p.vm.reason.value = '合成原因说明'
  await p.vm.submit('confirm'); await p.vm.submit('reject'); assert.equal(p.calls.filter(x => ['confirm', 'reject'].includes(x[0])).length, 0)
  read.resolve({ ...task, version: 1, viewedAt: '2026-10-06' }); await opening
  const submitting = p.vm.submit('confirm'); assert.equal(p.vm.busy.value, true)
  await p.vm.submit('confirm'); modal.resolve(true); await submitting
  assert.equal(p.calls.filter(x => x[0] === 'confirm').length, 1)
})

test('原版本冲突保留正文和原因，必须主动重读且不泄露内部错误', async t => {
  const p = await page(t, { consentReject: async () => { throw { code: 1, bizCode: 'DATA_CONFLICT', message: 'RAW_INTERNAL' } } })
  await p.vm.openTask(task); p.vm.reason.value = '请核实当前企业安排'; await p.vm.submit('reject')
  assert.equal(p.vm.detail.value.version, 1); assert.equal(p.vm.reason.value, '请核实当前企业安排')
  assert.equal(p.vm.conflict.value, true); assert.equal(p.vm.canAct.value, false)
  assert.equal(p.calls.filter(x => x[0] === 'detail').length, 1); assert.ok(p.vm.actionError.value.includes('原版本'))
  assert.ok(!p.vm.actionError.value.includes('RAW_INTERNAL')); await p.vm.openTask(task)
  assert.equal(p.vm.conflict.value, false); assert.equal(p.vm.reason.value, '请核实当前企业安排')
})

test('切记录和账号使迟到正文失效，不写阅读回执或回填旧对象', async t => {
  const response = deferred(); const p = await page(t, { consentDetail: () => response.promise })
  const opening = p.vm.openTask(task); p.props.context.recordId = 'another'; p.switchAccount()
  response.resolve(task); await opening; await flush()
  assert.equal(p.vm.detail.value, null); assert.equal(p.vm.selected.value, null)
  assert.equal(p.calls.filter(x => x[0] === 'view').length, 0); assert.deepEqual(p.vm.items.value, [])
})

test('隐藏页面或卸载后旧弹窗结果不能提交到新上下文', async t => {
  const modal = deferred(); const p = await page(t, {}, () => modal.promise)
  await p.vm.openTask(task); const submitting = p.vm.submit('confirm')
  p.hide(); p.lifecycle.unmount(); modal.resolve(true); await submitting
  assert.equal(p.calls.filter(x => x[0] === 'confirm').length, 0); assert.equal(p.vm.receipt.value, null)
})

test('两任务乱序响应不覆盖当前正文，旧请求不会提前结束新加载', async t => {
  const first = deferred(), second = deferred(); const other = { ...task, id: '9007199254741004' }
  const p = await page(t, { consentDetail: id => id === task.id ? first.promise : second.promise, consentView: async id => ({ ...(id === task.id ? task : other), version: 1, viewedAt: '2026-10-06' }) })
  const a = p.vm.openTask(task), b = p.vm.openTask(other)
  first.resolve(task); await a; assert.equal(p.vm.reading.value, true); assert.equal(p.vm.detail.value, null)
  second.resolve(other); await b; assert.equal(p.vm.detail.value.id, other.id); assert.equal(p.vm.reading.value, false)
})

test('历史记录、监护人和未知终态均不发送学生办理写请求', async t => {
  const p = await page(t)
  await p.vm.openTask({ ...task, consentType: 'GUARDIAN' }); assert.equal(p.calls.filter(x => x[0] === 'detail').length, 0)
  p.props.context.historyMode = true; await flush(); await p.vm.openTask(task)
  await p.vm.submit('confirm'); p.vm.reason.value = '历史不能提交原因'; await p.vm.submit('reject')
  assert.equal(p.calls.filter(x => ['view', 'confirm', 'reject'].includes(x[0])).length, 0)
  assert.equal(p.vm.statusText('UNRECOGNIZED_INTERNAL'), '状态待学校核实')
  const current = await page(t, { consentDetail: async () => ({ ...task, status: 'UNRECOGNIZED_INTERNAL', viewedAt: '2026-10-06', version: 1 }) })
  await current.vm.openTask(task); current.vm.reason.value = '未知状态需要核实'
  await current.vm.submit('confirm'); await current.vm.submit('reject')
  assert.equal(current.vm.canAct.value, false)
  assert.equal(current.calls.filter(x => ['view', 'confirm', 'reject'].includes(x[0])).length, 0)
  assert.equal(current.vm.statusText(current.vm.detail.value.status), '状态待学校核实')
})

test('拒绝校验及请求失败保留原因，提交成功后回读失败明确部分完成', async t => {
  const p = await page(t); await p.vm.openTask(task); p.vm.reason.value = '短'
  await p.vm.submit('reject'); assert.equal(p.calls.filter(x => x[0] === 'reject').length, 0)
  p.vm.reason.value = '学校请核实具体安排'
  p.api.consentReject = async () => { throw { network: true } }; await p.vm.submit('reject')
  assert.equal(p.vm.reason.value, '学校请核实具体安排'); assert.equal(p.vm.busy.value, false)
  p.api.consentReject = async () => ({ ...task, status: 'REJECTED', version: 2 })
  p.api.consentDetail = async () => { throw { network: true } }; await p.vm.submit('reject')
  assert.equal(p.vm.receipt.value.readback, false); assert.equal(p.vm.detail.value.status, 'REJECTED')
  assert.ok(p.vm.actionError.value.includes('办理已提交')); assert.equal(p.vm.canAct.value, false)
})

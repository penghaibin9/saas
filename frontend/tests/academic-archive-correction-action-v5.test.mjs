import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { academicFlowText } from '../src/modules/academicAffairs/config/academicFlowRegistry.js'

const ok = data => ({ code: 0, data })
const batchId = '9007199254740993', caseId = '9007199254740995'
const batch = extra => ({ batchId, status: 'ARCHIVED', correctionAction: { allowed: true }, ...extra })
const detail = extra => ({ caseId, archiveBatchId: batchId, status: 'PENDING_SECOND_APPROVAL', reviewAction: { allowed: true }, originalOfficialFact: { score: 59 }, proposedOfficialFact: { score: 65 }, correction: { score: 65 }, evidenceManifest: { refs: ['正式证据'] }, ...extra })
const form = () => ({ businessType: 'GRADE', targetRef: '9007199254740997', reason: '原成绩录入有误需复核', correctionText: '{"score":65}', evidenceText: '{"refs":["正式证据"]}', riskLevel: 'HIGH' })
function instance(api = {}, archiveApi = {}, dependencies = {}) {
  const emitted = []
  const value = page('../components/AaArchiveCorrectionWorkspace', { academicFlowText,
    academicArchiveCorrectionApi: { list: async () => ok({ items: [] }), verifyManifest: async () => ok({ ok: true, versions: [] }), detail: async () => ok(detail()), ...api },
    academicAffairsArchiveApi: { getBatch: async () => ok(batch()), ...archiveApi }, ...dependencies
  }, { batch: batch(), items: [], emptyCreateForm: form, $emit: name => emitted.push(name) })
  value.state.detail = detail(); value.state.selectedCaseId = caseId; value.state.detailVisible = true
  return { ...value, emitted }
}

test('发起及二审只消费严格服务端许可，未知、角色文本、非布尔值都不可写', async () => {
  let writes = 0
  for (const action of [undefined, null, {}, { allowed: false }, { allowed: 'true' }, { allowed: 1 }]) {
    const { state } = instance({ create: async () => { writes++ }, approve: async () => { writes++ }, reject: async () => { writes++ } })
    state.batch = batch({ correctionAction: action }); state.detail = detail({ reviewAction: action })
    assert.equal(state.canCreate, false); assert.equal(state.canReview, false)
    await state.openCreate(); await state.submitCreate(); await state.askApprove(); await state.askReject(); await state.submitApprove(); await state.submitReject({ reason: '证据不足需重新核对' })
    assert.equal(state.createVisible, false); assert.equal(state.approveConfirmVisible, false); assert.equal(state.rejectConfirmVisible, false)
  }
  assert.equal(writes, 0)
})

test('发起开框与发送前回读同批次许可，撤权不写且保留输入', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ create: async () => { writes++ } }, { getBatch: async () => ok(batch({ correctionAction: ++reads === 1 ? { allowed: true } : { allowed: false, reason: '学校归档责任任职已失效' } })) })
  await state.openCreate(); state.createForm = form(); const before = JSON.stringify(state.createForm)
  await state.submitCreate()
  assert.equal(reads, 2); assert.equal(writes, 0); assert.equal(state.createVisible, true)
  assert.equal(JSON.stringify(state.createForm), before); assert.match(state.formError, /责任任职已失效/)
})

test('当前批次资格读取失败或错单不沿用缓存许可', async () => {
  for (const kind of ['error', 'wrong', 'denied']) {
    const { state } = instance({}, { getBatch: async () => { if (kind === 'error') throw new Error('读取失败'); return kind === 'wrong' ? ok(batch({ batchId: 'other' })) : { code: 403, message: '无归档办理权限' } } })
    await state.openCreate(); assert.equal(state.createVisible, false); assert.equal(state.canCreate, false); assert.ok(state.actionError); assert.equal(state.checking, false)
  }
})

test('二审开框前按同单详情核对本人及当前责任，拒绝原因可见', async () => {
  const { state } = instance({ detail: async () => ok(detail({ reviewAction: { allowed: false, reason: '归档后纠错必须由不同操作人二次复核' } })) })
  await state.askApprove(); await state.askReject()
  assert.equal(state.approveConfirmVisible, false); assert.equal(state.rejectConfirmVisible, false); assert.match(state.actionError, /不同操作人/)
})

test('批准与驳回发送前二次回读，撤权或读取失败不写，原驳回理由保留', async () => {
  for (const action of ['approve', 'reject']) for (const kind of ['revoked', 'error']) {
    let reads = 0, writes = 0
    const { state } = instance({ detail: async () => { if (++reads === 2 && kind === 'error') throw new Error('详情读取失败'); return ok(detail({ reviewAction: reads === 1 ? { allowed: true } : { allowed: false, reason: '当前学校责任已撤销' } })) }, approve: async () => { writes++ }, reject: async () => { writes++ } })
    if (action === 'approve') { await state.askApprove(); await state.submitApprove() }
    else { await state.askReject(); await state.submitReject({ reason: '证据不足需要重新核对' }) }
    assert.equal(reads, 2); assert.equal(writes, 0); assert.equal(state.busy, false); assert.ok(state.actionError || state.detailError)
    assert.equal(action === 'approve' ? state.approveConfirmVisible : state.rejectConfirmVisible, true)
    assert.equal(state.canReview, false)
  }
})

test('已确认写回执后正式列表、清单、同单详情全回读才报告完成', async () => {
  for (const kind of ['create', 'approve', 'reject']) {
    let writes = 0, reads = 0
    const { state, emitted } = instance({
      detail: async id => { assert.equal(id, caseId); reads++; return ok(detail(writes && kind !== 'create' ? { status: kind === 'approve' ? 'APPLIED' : 'REJECTED', reviewAction: { allowed: false } } : {})) },
      create: async (id, body) => { assert.equal(id, batchId); assert.equal(body.targetRef, '9007199254740997'); writes++; return ok({ caseId }) },
      approve: async id => { assert.equal(id, caseId); writes++; return ok({}) },
      reject: async (id, reason) => { assert.equal(id, caseId); assert.equal(reason, '证据不足需要重新核对'); writes++; return ok({}) }
    })
    if (kind === 'create') { state.createForm = form(); await state.submitCreate() }
    else if (kind === 'approve') { await state.askApprove(); await state.submitApprove() }
    else { await state.askReject(); await state.submitReject({ reason: '证据不足需要重新核对' }) }
    assert.equal(writes, 1); assert.ok(reads >= 1); assert.equal(state.pendingCommand, null); assert.ok(emitted.includes('refresh-batch'))
    assert.equal(state.busy, false); assert.equal(state.saving, false)
  }
})

test('未知写回执仅在原命令目标结果核对完成后解锁，绝不重放写', async () => {
  for (const kind of ['create', 'approve', 'reject']) {
    let writes = 0
    const fail = async () => { writes++; throw new Error('回执连接中断') }
    const { state } = instance({ create: fail, approve: fail, reject: fail, detail: async () => ok(detail(writes ? { status: 'APPLIED', reviewAction: { allowed: false } } : {})) })
    if (kind === 'create') { state.createForm = form(); await state.submitCreate() }
    if (kind === 'approve') await state.submitApprove()
    if (kind === 'reject') await state.submitReject({ reason: '证据不足需要重新核对' })
    assert.equal(state.pendingCommand.sent, true); assert.equal(writes, 1)
    await state.refreshServerState(); await state.submitApprove(); await state.submitReject({ reason: '证据不足需要重新核对' })
    assert.equal(writes, 1)
    if (kind === 'approve') { assert.equal(state.pendingCommand, null); assert.match(state.actionNotice, /核对完成.*已应用/); assert.equal(state.canCreate, true) }
    else assert.ok(state.pendingCommand)
    if (kind === 'create') { await state.submitCreate(); assert.equal(writes, 1); assert.match(state.actionError, /无法仅凭纠错列表/) }
  }
})

test('批准与驳回的原单目标终态及归档清单通过后，即使已关详情也可只读恢复', async () => {
  for (const kind of ['approve', 'reject']) {
    let writes = 0, reads = 0
    const { state } = instance({ detail: async id => { reads++; assert.equal(id, caseId); return ok(detail({ status: kind === 'approve' ? 'APPLIED' : 'REJECTED', reviewAction: { allowed: false } })) }, approve: async () => { writes++ }, reject: async () => { writes++ } })
    state.pendingCommand = { kind, batchId, caseId, sent: true }; state.detailVisible = false; state.selectedCaseId = ''
    await state.refreshServerState()
    assert.equal(reads, 1); assert.equal(writes, 0); assert.equal(state.pendingCommand, null)
    assert.match(state.actionNotice, /核对完成.*归档清单完整性校验通过.*未重复发送命令/)
  }
})

test('创建已确认单号但首次回读失败，恢复时精确核对原单并解锁，绝不重发', async () => {
  for (const failure of ['list', 'detail', 'manifest']) {
    let writes = 0, recovering = false, preciseReads = 0
    const { state: rawState } = instance({
      create: async () => { writes++; return ok({ caseId }) },
      list: async () => failure === 'list' && !recovering ? { code: 503 } : ok({ items: [] }),
      detail: async id => { preciseReads++; assert.equal(id, caseId); return failure === 'detail' && !recovering ? { code: 503 } : ok(detail()) },
      verifyManifest: async () => ok({ ok: failure !== 'manifest' || recovering })
    })
    const state = Vue.reactive(rawState)
    state.createForm = form(); await state.submitCreate()
    assert.equal(writes, 1); assert.equal(state.pendingCommand.caseId, caseId); assert.equal(state.pendingCommand.acknowledged, true)
    recovering = true; await state.refreshServerState()
    assert.equal(writes, 1); assert.equal(state.pendingCommand, null); assert.ok(preciseReads >= 2)
    assert.match(state.actionNotice, /核对完成.*已创建.*待二审/)
  }
})

test('恢复时待二审、未知状态、错单、清单异常或未确认值均保持原锁', async () => {
  for (const outcome of ['pending', 'unknown', 'wrong-case', 'wrong-batch', 'bad-manifest', 'unknown-manifest', 'string-manifest', 'read-error']) {
    const { state } = instance({
      detail: async () => {
        if (outcome === 'read-error') throw new Error('原纠错单读取失败')
        return ok(detail({ status: outcome === 'pending' ? 'PENDING_SECOND_APPROVAL' : outcome === 'unknown' ? null : 'APPLIED', caseId: outcome === 'wrong-case' ? 'other' : caseId, archiveBatchId: outcome === 'wrong-batch' ? 'other' : batchId }))
      },
      verifyManifest: async () => ok({ ok: outcome === 'bad-manifest' ? false : outcome === 'unknown-manifest' ? null : outcome === 'string-manifest' ? 'true' : true })
    })
    const command = { kind: 'approve', batchId, caseId, sent: true }; state.pendingCommand = command
    await state.refreshServerState()
    assert.equal(state.pendingCommand, command); assert.equal(state.actionNotice, ''); assert.ok(state.actionError)
    if (outcome.includes('manifest')) assert.match(state.actionError, /部分完成/)
  }
})

test('恢复期间命令替换或身份失效时，旧终态响应不能解除新锁', async () => {
  for (const change of ['command', 'identity']) {
    const pending = deferred(); let reached
    const reading = new Promise(resolve => { reached = resolve })
    const { state } = instance({ detail: () => { reached(); return pending.promise } })
    state.pendingCommand = { kind: 'approve', batchId, caseId, sent: true }
    const recovering = state.refreshServerState(); await reading
    const replacement = { kind: 'reject', batchId, caseId: 'another', sent: true }
    if (change === 'identity') state.clearContext()
    state.pendingCommand = replacement
    pending.resolve(ok(detail({ status: 'APPLIED' }))); await recovering
    assert.equal(state.pendingCommand, replacement); assert.equal(state.actionNotice, '')
  }
})

test('正式写回执成功但清单校验失败只能报告部分完成，不能成功提示或丢弃锁', async () => {
  for (const kind of ['create', 'approve', 'reject']) {
    const successes = []
    let writes = 0
    const { state, emitted } = instance({
      create: async () => { writes++; return ok({ caseId }) }, approve: async () => { writes++; return ok({}) }, reject: async () => { writes++; return ok({}) },
      detail: async () => ok(detail(writes && kind !== 'create' ? { status: kind === 'approve' ? 'APPLIED' : 'REJECTED', reviewAction: { allowed: false } } : {})),
      verifyManifest: async () => ok({ ok: false, reason: '归档清单关联不完整' })
    }, {}, { toast: { success: message => successes.push(message), error() {} } })
    if (kind === 'create') { state.createForm = form(); await state.submitCreate() }
    else if (kind === 'approve') await state.submitApprove()
    else await state.submitReject({ reason: '证据不足需要重新核对' })
    assert.equal(writes, 1); assert.equal(successes.length, 0); assert.ok(state.pendingCommand)
    assert.match(state.actionError, /部分完成.*归档清单完整性/); assert.equal(emitted.length, 0)
  }
})

test('同单读取失败或返回别的归档批次立即清除旧证据和办理许可', async () => {
  for (const result of [{ code: 403, message: '当前无权查看纠错证据' }, ok(detail({ archiveBatchId: 'other' })), ok(detail({ caseId: 'other' }))]) {
    const { state } = instance({ detail: async () => result })
    await state.openDetail(caseId); assert.equal(state.detail, null); assert.equal(state.canReview, false); assert.ok(state.detailError); assert.equal(state.detailVisible, true)
  }
})

test('换身份、换归档批次、路由离开及卸载后的迟到许可不能开框和写入', async () => {
  for (const kind of ['create', 'approve']) for (const change of ['identity', 'batch', 'route', 'unmount']) {
    const pending = deferred(); let actor = 'one', writes = 0
    const { state, definition } = instance({ detail: () => pending.promise, approve: async () => { writes++ } }, { getBatch: () => pending.promise }, { currentUserFromToken: () => ({ userId: actor }) })
    const running = kind === 'create' ? state.openCreate() : state.askApprove()
    if (change === 'identity') actor = 'two'
    if (change === 'batch') state.batch = batch({ batchId: 'other' })
    if (change === 'route') state.$route.fullPath = '/other'
    if (change === 'unmount') definition.beforeUnmount.call(state)
    else state.clearContext()
    pending.resolve(ok(kind === 'create' ? batch() : detail())); await running
    assert.equal(state.createVisible, false); assert.equal(state.approveConfirmVisible, false); assert.equal(writes, 0); assert.equal(state.checking, false)
  }
})

test('真实模板无资格禁用发起、隐藏二审动作且展示原因，中文事实摘要保留证据', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue', import.meta.url), 'utf8')
  const render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const { state } = instance(); state.activeTab = 'corrections'; state.batch.correctionAction = { allowed: false, reason: '当前无学校纠错发起责任' }; state.detail.reviewAction = { allowed: false, reason: '申请人本人不能二次复核' }
  delete state.$route; delete state.$router; delete state.$emit
  const app = Vue.createSSRApp({ render, setup: () => state, components: {
    AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) },
    AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
    AppDrawer: { props: ['visible'], setup: (props, { slots }) => () => props.visible ? Vue.h('section', [slots.default?.(), slots.footer?.()]) : null },
    AppConfirmDialog: { render: () => null }, LoadingState: { render: () => null }, EmptyState: { render: () => null }, DataTable: { render: () => null }, StatusTag: { render: () => null }
  } })
  const html = await renderToString(app)
  assert.match(html, /<button disabled[^>]*>发起归档后纠错/)
  assert.doesNotMatch(html, /<button[^>]*>二审通过|<button[^>]*>驳回/)
  assert.match(html, /申请人本人不能二次复核/); assert.match(html, /当前无学校纠错发起责任/)
  assert.match(html, /成绩：59/); assert.match(html, /成绩：65/); assert.match(html, /已登记 1 项证据引用/)
  assert.match(html, /<details><summary>实施人员使用/); assert.doesNotMatch(html, /<details open/)
  assert.doesNotMatch(html, /Manifest|REJECTED|HIGH|supersedes/)
})

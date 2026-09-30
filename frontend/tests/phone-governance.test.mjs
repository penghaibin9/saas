import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createPhoneGovernance, phoneGovernanceState } from '../src/modules/system/utils/phoneGovernance.js'
import { presentAuditRecord } from '../src/utils/presentationSafety.js'

const page = { list: [{ userId: '90071992547409930', candidateVersion: 3, allowedActions: { candidate: true } }], total: 1, page: 1, pageSize: 20 }
test('phone critical events have distinct business labels in the original audit view', () => {
  assert.equal(presentAuditRecord({ action: 'PHONE_BINDING_CHANGE' }).displayAction, '手机号登录凭据变更')
  assert.equal(presentAuditRecord({ action: 'PHONE_LEDGER_EXPORT' }).displayAction, '手机号脱敏台账导出')
})
test('late school response is discarded and sensitive edit input cleared on disposal', async () => {
  let resolve
  const state = phoneGovernanceState(), api = { query: () => new Promise(r => { resolve = r }) }
  const flow = createPhoneGovernance(state, api, () => ({}))
  const loading = flow.load(); flow.dispose(); resolve(page); await loading
  assert.equal(state.rows.length, 0); assert.equal(state.edit, null)
})
test('conflict preserves phone/reason/version and blocks an automatic retry', async () => {
  const state = phoneGovernanceState(); let calls = 0
  const api = { query: async () => page, candidate: async () => { calls++; throw Error('版本冲突') } }
  const flow = createPhoneGovernance(state, api, () => ({}))
  await flow.load(); flow.edit(state.rows[0]); state.edit.phone = '13800138000'; state.edit.reason = '虚构测试登记原因'
  await flow.save(); await flow.save()
  assert.equal(calls, 1); assert.equal(state.edit.expectedCandidateVersion, 3)
  assert.equal(state.edit.phone, '13800138000'); assert.equal(state.uncertain, true)
})

test('original account, exception, policy and phone governance surfaces compile', () => {
  for (const name of ['components/PhoneGovernancePanel.vue', 'views/SystemUserListView.vue', 'views/SystemAccountExceptionView.vue', 'views/SystemLoginPolicyView.vue']) {
    const filename = new URL('../src/modules/system/' + name, import.meta.url)
    const { descriptor, errors } = parse(fs.readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [])
    compileScript(descriptor, { id: name })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: name, id: name }).errors, [])
  }
})

test('batch confirmation uses frozen preview and cannot resend after ambiguous failure', async () => {
  const state = phoneGovernanceState(); let confirms = 0
  const api = { preview: async body => ({ previewId: 'frozen', action: body.action, count: 1 }),
    confirm: async body => { assert.deepEqual(body, { previewId: 'frozen' }); confirms++; throw Error('连接中断') } }
  const flow = createPhoneGovernance(state, api, () => ({ state: 'PENDING' }))
  state.batchReason = '通知本人完成号码验证'
  await flow.preview('REMIND'); await flow.confirm(); await flow.confirm()
  assert.equal(confirms, 1); assert.equal(state.uncertain, true)
  assert.equal(state.preview.previewId, 'frozen')
  flow.dispose(); assert.equal(state.preview, null)
})

test('administrative revoke freezes target/version and clears password on failure', async () => {
  const state = phoneGovernanceState(); let calls = 0
  const flow = createPhoneGovernance(state, { revoke: async (id, body) => {
    calls++; assert.equal(id, '7000000000000000001'); assert.equal(body.expectedBindingVersion, 4)
    assert.equal(body.currentPassword, 'synthetic'); throw Error('响应丢失')
  } }, () => ({}))
  flow.editRevoke({ userId: '7000000000000000001', bindingVersion: 4, allowedActions: { revoke: true } })
  state.edit.reason = '核对误绑撤销手机号'; state.edit.currentPassword = 'synthetic'
  await flow.save(); await flow.save()
  assert.equal(calls, 1); assert.equal(state.edit.currentPassword, '')
  assert.equal(state.uncertain, true)
})

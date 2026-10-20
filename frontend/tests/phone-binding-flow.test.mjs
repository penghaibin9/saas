import test from 'node:test'
import assert from 'node:assert/strict'
import { createPhoneBindingFlow, phoneBindingState } from '../../shared/phoneBindingFlow.mjs'

const binding = { state: 'UNBOUND', bindingVersion: 0, candidateVersion: 0, allowedActions: { verify: true, registerCandidate: true } }
const receipt = { runtimeMaterialized: true, state: 'VERIFIED', bindingVersion: 1, reloginRequired: true }

test('unknown candidate write requires readback before another mutation', async () => {
  let writes = 0
  const { state, flow } = setup(async path => {
    if (path.endsWith('/candidate')) { writes++; throw Error('response lost') }
    return binding
  })
  await flow.load(); state.phone = '13800138000'; state.currentPassword = 'test-password'
  await flow.registerCandidate()
  state.currentPassword = 'test-password'; await flow.registerCandidate()
  assert.equal(writes, 1); assert.equal(state.step, 'READ_REQUIRED')
  await flow.begin('BIND_PHONE'); assert.equal(state.step, 'READ_REQUIRED')
  await flow.load(); assert.equal(state.step, 'READY')
})
function setup(request) {
  const state = phoneBindingState(); let generation = 1
  const flow = createPhoneBindingFlow(state, { request, sessionKey: () => generation, random: async () => 'secure-synthetic-nonce-123456789' })
  return { state, flow, changeSession() { generation++ } }
}
test('late binding read cannot populate a new school or an unmounted page', async () => {
  let finish
  const { state, flow, changeSession } = setup(() => new Promise(resolve => { finish = resolve }))
  const pending = flow.load(); changeSession(); finish(binding); await pending
  assert.equal(state.binding, null); assert.equal(state.currentPassword, '')
})
test('only server allowed actions start proof and no client verified field is sent', async () => {
  const calls = []; const { state, flow } = setup(async (path, options) => {
    calls.push({ path, options }); return path.endsWith('reauthenticate') ? { operationId: 'op', reauthTicket: 'ticket', receiptToken: 'receipt', expiresAt: 4000000000 } : binding
  })
  await flow.load(); state.phone = '13800138000'; state.currentPassword = 'test-password'
  await flow.begin('CHANGE_PHONE'); assert.equal(calls.length, 1)
  await flow.begin('BIND_PHONE'); assert.equal(calls.length, 2)
  assert.equal(state.currentPassword, '')
  assert.equal(calls[1].options.body.expectedBindingVersion, 0)
  assert.equal('phoneVerified' in calls[1].options.body, false)
})
test('lost confirm response queries only its original receipt, never replays a mutation', async () => {
  const calls = []; const { state, flow } = setup(async (path, options) => {
    calls.push({ path, options })
    if (path.endsWith('reauthenticate')) return { operationId: 'op', reauthTicket: 'ticket', receiptToken: 'receipt', expiresAt: 4000000000 }
    if (path.endsWith('challenges')) return { accepted: true, challengeId: 'challenge', expiresAt: 4000000000 }
    if (path.endsWith('/verify')) return { verified: true, verificationGrant: 'grant', expiresAt: 4000000000 }
    if (path.endsWith('/confirm')) throw Error('网络中断')
    if (path.endsWith('operation-status')) return receipt
    return binding
  })
  await flow.load(); state.phone = '13800138000'; state.currentPassword = 'test-password'
  await flow.begin('BIND_PHONE'); await flow.send(); state.code = '123456'; await flow.verify()
  await flow.confirm(); await flow.confirm()
  assert.equal(state.step, 'UNCERTAIN'); assert.equal(calls.filter(x => x.path.endsWith('/confirm')).length, 1)
  await flow.checkResult(); assert.equal(state.step, 'COMMITTED')
  const check = calls.at(-1); assert.equal(check.options.auth, false)
  assert.deepEqual(check.options.body, { receiptToken: 'receipt', clientNonce: 'secure-synthetic-nonce-123456789' })
  assert.equal(state.phone, ''); assert.equal(state.code, '')
})
test('expired challenge cannot send or verify and disposal erases inputs', async () => {
  const calls = []; const { state, flow } = setup(async path => {
    calls.push(path); return path.endsWith('reauthenticate') ? { operationId: 'op', reauthTicket: 'ticket', receiptToken: 'receipt', expiresAt: 1 } : binding
  })
  await flow.load(); state.phone = '13800138000'; state.currentPassword = 'test-password'
  await flow.begin('BIND_PHONE'); await flow.send(); state.code = '123456'; await flow.verify()
  assert.equal(calls.length, 2); flow.dispose(); assert.equal(state.phone, ''); assert.equal(state.code, '')
})

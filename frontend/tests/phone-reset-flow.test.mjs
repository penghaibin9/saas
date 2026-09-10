import test from 'node:test'
import assert from 'node:assert/strict'
import { resetFlowState, createResetFlow } from '../../shared/passwordResetFlow.mjs'

function setup(request) {
  const state = resetFlowState({ loginName: '13800138000', tenantCode: 'school', identifierType: 'PHONE' })
  const flow = createResetFlow(state, { request, clientType: 'PC', random: async () => 'secure-nonce-12345678901234567890' })
  return { state, flow }
}
test('changed identity discards a late captcha and its old proof', async () => {
  let finish
  const { state, flow } = setup(() => new Promise(resolve => { finish = resolve }))
  const pending = flow.loadCaptcha(); await Promise.resolve(); await Promise.resolve()
  state.form.tenantCode = 'another'; flow.identityChanged()
  finish({ captchaId: 'old', imageDataUrl: 'old' }); await pending
  assert.equal(state.captcha.id, ''); assert.equal(state.step, 1)
})
test('PHONE reset uses typed identifier, unknown confirmation only checks receipt', async () => {
  const calls = []
  const { state, flow } = setup(async (path, options) => {
    calls.push({ path, options })
    if (path.endsWith('/captcha')) return { captchaId: 'cap', imageDataUrl: 'image' }
    if (path.endsWith('/request')) return { requestId: 'request', retryAfter: 60, expiresIn: 300 }
    if (path.endsWith('/verify')) return { verified: true, resetToken: 'reset-secret', expiresIn: 300 }
    if (path.endsWith('/confirm')) throw Error('response lost')
    return { runtimeMaterialized: true, success: true, reloginRequired: true }
  })
  await flow.loadCaptcha(); state.captcha.code = '123456'; await flow.requestCode()
  assert.equal(calls[1].options.body.identifierType, 'PHONE')
  assert.equal(calls[1].options.body.identifier, '13800138000')
  assert.equal('loginName' in calls[1].options.body, false)
  state.form.smsCode = '123456'; await flow.verifyCode()
  state.form.newPassword = 'Password-123!'; state.form.confirmPassword = 'Password-123!'
  await flow.confirmReset(); await flow.confirmReset()
  assert.equal(state.step, 4); assert.equal(calls.filter(x => x.path.endsWith('/confirm')).length, 1)
  assert.equal(state.form.newPassword, '')
  await flow.checkResult(); assert.equal(state.step, 5)
  assert.deepEqual(calls.at(-1).options.body, { resetToken: 'reset-secret', clientNonce: 'secure-nonce-12345678901234567890' })
  assert.equal(calls.at(-1).options.noAuthRetry, true)
})

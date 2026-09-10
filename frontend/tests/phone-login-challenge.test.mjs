import test from 'node:test'
import assert from 'node:assert/strict'
import { createIdentityCaptcha } from '../../shared/identityCaptcha.mjs'

test('identity change discards late captcha and clears code, image and nonce', async () => {
  let finish
  const box = { required: true, code: '123456', id: 'old', image: 'old', nonce: 'old' }
  const flow = createIdentityCaptcha(box, { identity: () => ({ identifierType: 'PHONE', identifier: '13800138000' }),
    issue: () => new Promise(resolve => { finish = resolve }), random: async () => 'secure-nonce-123456789', error() {} })
  const pending = flow.load(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  flow.invalidate(); finish({ captchaId: 'late', imageDataUrl: 'late' }); await pending
  assert.equal(box.id, ''); assert.equal(box.image, ''); assert.equal(box.code, ''); assert.equal(box.nonce, '')
})
test('two refreshes cannot install older challenge over the newest one', async () => {
  const pending = [], box = {}
  const flow = createIdentityCaptcha(box, { identity: () => ({}), issue: () => new Promise(resolve => pending.push(resolve)),
    random: async () => 'secure-nonce-123456789', error() {} })
  const first = flow.load(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  const second = flow.load(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  pending[1]({ captchaId: 'new', imageDataUrl: 'new' }); await second
  pending[0]({ captchaId: 'old', imageDataUrl: 'old' }); await first
  assert.equal(box.id, 'new')
})

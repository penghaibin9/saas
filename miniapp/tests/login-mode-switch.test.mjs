import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/login/MiniLoginAuthPanel.vue', import.meta.url), 'utf8')
  .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const component = new Function(source)()

test('login mode rejects invalid values and switching while either login is pending', () => {
  for (const flags of [{ accLoading: true }, { wxLoading: true }, {}]) {
    const state = { account: { identifierType: 'ACCOUNT' }, identifierOptions: component.computed.identifierOptions(), ...flags }
    component.methods.onIdentifierTypeChange.call(state, 'INVALID')
    assert.equal(state.account.identifierType, 'ACCOUNT')
    component.methods.onIdentifierTypeChange.call(state, 'PHONE')
    assert.equal(state.account.identifierType, flags.accLoading || flags.wxLoading ? 'ACCOUNT' : 'PHONE')
  }
})

test('changing identity mode clears both credentials and invalidates the old captcha', () => {
  let invalidated = 0
  const state = { account: { loginName: 'test-account', password: 'test-password' }, accountCaptchaFlow: { invalidate() { invalidated++ } } }
  component.watch['account.identifierType'].handler.call(state)
  assert.equal(state.account.loginName, '')
  assert.equal(state.account.password, '')
  assert.equal(invalidated, 1)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

for (const boundary of ['hide', 'school']) test(`late profile cannot refill phone security after ${boundary}`, async () => {
  const source = readFileSync(new URL('../src/pages/common/account-security/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
  let finish, generation = 1
  const component = new Function('useSessionStore', 'enrichProfileReal', 'go', 'relaunch', 'PhoneBindingPanel', 'currentSessionGeneration', source)(
    () => ({ identity: { userId: '1' }, side: 'student', currentRole: 'STUDENT', mockUser: {} }),
    () => new Promise(resolve => { finish = resolve }), () => {}, () => {}, {}, () => generation)
  const instance = { ...component.data() }
  component.onShow.call(instance)
  if (boundary === 'hide') component.onHide.call(instance)
  else generation++
  finish({ base: { name: 'old-school-person' }, contact: { phone: '138****8000' } })
  await Promise.resolve(); await Promise.resolve()
  assert.equal(instance.info.name, undefined)
})

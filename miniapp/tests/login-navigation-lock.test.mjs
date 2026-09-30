import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('login redirection reports a busy route and proceeds after it completes', () => {
  const calls = []
  const context = vm.createContext({
    uni: { reLaunch: options => calls.push(options), showToast() {} },
    forcePasswordChangeRequired: () => false
  })
  vm.runInContext(readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/import[\s\S]*?from[^\n]+\n/, '')
    .replace(/export default[^\n]+/, '').replace(/export /g, ''), context)
  assert.equal(context.relaunch('/pages/teacher/workbench/index'), true)
  assert.equal(context.relaunch('/pages/login/index'), false)
  assert.equal(calls.length, 1)
  calls[0].complete()
  assert.equal(context.relaunch('/pages/login/index'), true)
  assert.equal(calls[1].url, '/pages/login/index')
})

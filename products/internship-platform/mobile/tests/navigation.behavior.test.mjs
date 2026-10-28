import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function navigation(uni, forced = false) {
  const source = fs.readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*/gm, '')
    .replace(/export default[^\n]+/g, '').replace(/export function /g, 'function ')
  return new Function('uni', 'forcePasswordChangeRequired', 'FORCE_PASSWORD_CHANGE_ROUTE',
    'isForcePasswordChangeRoute', 'getCurrentPages', source + '\nreturn {go,relaunch,back,goSibling}')(
    uni, () => forced, '/forced-password', url => url === '/forced-password', () => [])
}

test('navigation preserves pending lock and fallback until the final callback', () => {
  const calls = [], uni = Object.fromEntries(['navigateTo', 'reLaunch', 'navigateBack', 'redirectTo']
    .map(method => [method, options => calls.push({method, options})]))
  const nav = navigation(uni)
  nav.go('/selected?batchId=9007199254740993')
  nav.go('/must-wait')
  assert.equal(calls.length, 1)
  calls[0].options.fail()
  calls[0].options.complete()
  nav.go('/still-wait')
  assert.equal(calls.length, 2)
  assert.equal(calls[1].method, 'reLaunch')
  assert.equal(calls[1].options.url, '/selected?batchId=9007199254740993')
  calls[1].options.complete()
  nav.go('/next')
  calls[0].options.complete()
  nav.go('/old-callback-cannot-unlock')
  assert.equal(calls.length, 3)
  calls[2].options.complete()
  nav.relaunch('/after')
  assert.equal(calls[3].options.url, '/after')
})

test('navigation keeps password gate and releases lock after a host exception', () => {
  const calls = [], messages = []
  const uni = {navigateTo() {throw new Error('host failed')}, showToast: options => messages.push(options.title),
    reLaunch: options => calls.push(options), navigateBack() {}, redirectTo() {}}
  const nav = navigation(uni, true)
  nav.go('/private-business')
  assert.deepEqual(messages, ['页面暂时无法打开，请稍后重试'])
  nav.relaunch('/private-business')
  assert.equal(calls[0].url, '/forced-password')
})

import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const ROOT = process.cwd()

function read(relativePath) {
  return readFileSync(path.join(ROOT, relativePath), 'utf8')
}

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

test('Vue 3 source contains no removed this.$set / this.$delete calls', () => {
  const offenders = walk(path.join(ROOT, 'src'))
    .filter((file) => /\.(?:vue|js)$/.test(file))
    .filter((file) => /this\.\$(?:set|delete)\s*\(/.test(readFileSync(file, 'utf8')))
    .map((file) => path.relative(ROOT, file))
  assert.deepEqual(offenders, [])
})
test('production role switching fails closed while real API is offline', () => {
  const session = read('src/stores/session.js')
  assert.match(session, /else if \(ENV\.allowMockFallback\)\s*\{\s*this\.currentRole = roleKey/)
  assert.match(session, /throw \{ code: 'NETWORK', message: '网络不可用，无法安全切换身份' \}/)
})

test('every Vue entry that directly invokes a WeChat private media API mounts the privacy gate', () => {
  const directPrivateApi = /(?:chooseSingleFile|fileSdk\.choose|uni\.(?:chooseMessageFile|chooseImage|scanCode|getLocation))\s*\(/
  const offenders = walk(path.join(ROOT, 'src'))
    .filter((file) => file.endsWith('.vue'))
    .filter((file) => directPrivateApi.test(readFileSync(file, 'utf8')))
    .filter((file) => !readFileSync(file, 'utf8').includes('MobilePrivacyGate'))
    .map((file) => path.relative(ROOT, file))
  assert.deepEqual(offenders, [])
})

test('privacy gate registers one runtime listener and chooses one current UI owner', () => {
  const gate = read('src/components/MobilePrivacyGate.vue')
  assert.equal((gate.match(/^\s*wx\.onNeedPrivacyAuthorization\(/gm) || []).length, 1)
  assert.match(gate, /let privacyListenerInstalled = false/)
  assert.match(gate, /privacyGateInstances\[privacyGateInstances\.length - 1\]/)
})

test('graduation delay timeline keeps all four rows on the same visual contract', () => {
  const panel = read('src/components/MobileGraduationExtensionPanel.vue')
  assert.equal((panel.match(/class="gdex__timeline-item"/g) || []).length, 4)
  assert.doesNotMatch(panel, /:class="\{ done:/)
})

test('page deep-link text uses the malformed-percent-safe query decoder', () => {
  const offenders = walk(path.join(ROOT, 'src/pages'))
    .filter((file) => file.endsWith('.vue'))
    .filter((file) => /decodeURIComponent\s*\(/.test(readFileSync(file, 'utf8')))
    .map((file) => path.relative(ROOT, file))
  assert.deepEqual(offenders, [])

  const nav = read('src/utils/nav.js')
  assert.match(nav, /export function decodeQueryText/)
  assert.match(nav, /try \{ return decodeURIComponent\(source\) \} catch \(e\) \{ return source \}/)
})

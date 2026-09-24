import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')
const gate = read('src/security/platformAccessGate.js')
const router = read('src/router/index.js')
const login = read('src/views/PlatformLoginView.vue')
const layout = read('src/layouts/BasePortalLayout.vue')

test('P-02 platform entry is principal-first and capability-second', () => {
  assert.match(gate, /export function isPlatformPrincipal\(\)/)
  assert.match(gate, /request\('\/platform\/context', \{ forceProbe: true \}\)/)
  assert.match(gate, /principalPlane/)
  assert.match(gate, /context\?\.subjectId/)
  assert.match(gate, /setPermissionPatterns\(platformDutyPatterns\(context\?\.duties\)\)/)
  assert.match(router, /isPlatformPrincipal/)
  assert.match(router, /ensurePlatformAccessContext/)
  assert.doesNotMatch(router, /isPlatformSuperAdmin/)
  assert.match(login, /if \(!isPlatformPrincipal\(\)\)/)
  assert.match(login, /resolvePlatformHome\(context\)/)
})

test('P-02 delegated homes map to exact supported duties', () => {
  for (const pair of [
    ["access.review", '/admin/platform/access'],
    ["commercial.view", '/admin/platform/orders'],
    ["audit.view", '/admin/platform/audit'],
    ["tenant.view", '/admin/platform/tenants'],
  ]) {
    assert.ok(gate.includes(`duties.has('${pair[0]}')`))
    assert.ok(gate.includes(`return '${pair[1]}'`))
  }
  assert.match(gate, /normalized\.has\('\*'\).*return \['platform\.\*'\]/s)
})

test('P-02 platform rail lands on the first duty-authorized workspace', () => {
  assert.match(layout, /const firstAllowed = this\.menus\.find\(\(item\) => item\?\.path\)\?\.path/)
  assert.match(layout, /path: firstAllowed \|\| this\.\$route\?\.path \|\| '\/security\/403'/)
  assert.doesNotMatch(layout, /label: '平台运营', path: '\/admin\/platform\/overview'/)
})

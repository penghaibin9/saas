import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('newcomer can verify, set password, bind WeChat and enter orientation', () => {
  const page = read('src/pages/student/orientation/activate/index.vue')
  const login = read('src/components/login/MiniLoginAuthPanel.vue')
  const pages = JSON.parse(read('src/pages.json'))

  assert.match(login, /openOrientationActivation/)
  assert.match(page, /orientation-activation\/verify/)
  assert.match(page, /orientation-activation\/complete/)
  assert.match(page, /bindAnother:\s*true/)
  assert.match(page, /commitNewSessionTokens/)
  assert.match(page, /pages\/student\/orientation\/index/)
  assert.match(page, /sceneTenant\(options\?\.scene\)/)
  assert.ok(pages.subPackages.some((pkg) =>
    pkg.root === 'pages/student' && pkg.pages.some((item) => item.path === 'orientation/activate/index')
  ))
})

test('pre-arrival collection reuses masked stored phones without forcing re-entry', () => {
  const page = read('src/pages/student/orientation/collect/index.vue')
  assert.match(page, /useExistingPhone/)
  assert.match(page, /useExistingEmergencyPhone/)
  assert.match(page, /留空沿用/)
  assert.doesNotMatch(page, /if \(!\(\/\^\\d\{6,20\}\$\/\.test\(phone\)\)\)/)
})

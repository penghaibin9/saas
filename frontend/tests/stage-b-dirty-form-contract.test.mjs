import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')
const guard = fs.readFileSync(new URL('../src/router/dirtyFormGuard.js', import.meta.url), 'utf8')

test('Stage B B4 installs one global dirty-form guard', () => {
  assert.match(main, /import \{ installDirtyFormGuard \} from '\.\/router\/dirtyFormGuard'/)
  assert.match(main, /installDirtyFormGuard\(router\)/)
  assert.match(guard, /router\.beforeEach/)
  assert.match(guard, /import \{ systemConfirm \} from '\.\.\/services\/systemDialog\.js'/)
  assert.match(guard, /await systemConfirm/)
  assert.match(guard, /beforeunload/)
  assert.doesNotMatch(guard, /window\.confirm|window\.alert|window\.prompt/)
})

test('Stage B B4 covers internship batch/company and same-domain long forms', () => {
  for (const name of [
    'internship-recruitment-campaign-new', 'internship-recruitment-campaign-edit',
    'internship-batch-new', 'internship-batch-edit',
    'internship-enterprise-new', 'internship-enterprise-edit',
    'internship-position-new', 'internship-position-edit',
    'internship-guidance-new', 'internship-enterprise-eval-new',
    'internship-agreement-template-new', 'internship-agreement-template-edit'
  ]) {
    assert.match(guard, new RegExp(name))
  }
})

test('Stage B B4 is fail-closed: save and failed navigation never create a bypass window', () => {
  assert.match(guard, /真正导航成功后才在 afterEach 清理/)
  assert.match(guard, /let pendingDiscardApprovals = new WeakMap\(\)/)
  assert.match(guard, /pendingDiscardApprovals\.set\(to, \{ fromPath: String\(from\?\.fullPath \|\| ''\) \}\)/)
  assert.match(guard, /router\.afterEach\(\(to, from, failure\)/)
  assert.match(guard, /const approval = pendingDiscardApprovals\.get\(to\)/)
  assert.match(guard, /!failure && approval && approval\.fromPath === fromPath && toPath !== fromPath/)
  assert.match(guard, /pendingDiscardApprovals\.delete\(to\)/)
  const afterEach = guard.slice(guard.indexOf('const removeAfter = router.afterEach'), guard.indexOf('// 页面在真实保存成功回调'))
  assert.match(afterEach, /pendingDiscardApprovals\.delete\(to\)/)
  assert.doesNotMatch(afterEach, /pendingDiscardApprovals = new WeakMap/)
  assert.match(guard, /markSaved:\s*\(\) => \{[\s\S]*dirty = false[\s\S]*pendingDiscardApprovals = new WeakMap\(\)/)
  assert.doesNotMatch(guard, /submitWindowUntil|SAVE_TEXT_RE|Date\.now\(\) \+ 5000/)
})

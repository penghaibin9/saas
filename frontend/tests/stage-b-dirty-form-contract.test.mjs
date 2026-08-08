import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')
const guard = fs.readFileSync(new URL('../src/router/dirtyFormGuard.js', import.meta.url), 'utf8')

test('Stage B B4 installs one global dirty-form guard', () => {
  assert.match(main, /import \{ installDirtyFormGuard \} from '\.\/router\/dirtyFormGuard'/)
  assert.match(main, /installDirtyFormGuard\(router\)/)
  assert.match(guard, /router\.beforeEach/)
  assert.match(guard, /beforeunload/)
  assert.match(guard, /window\.confirm/)
})

test('Stage B B4 covers internship batch/company and same-domain long forms', () => {
  for (const name of [
    'internship-batch-new', 'internship-batch-edit',
    'internship-enterprise-new', 'internship-enterprise-edit',
    'internship-position-new', 'internship-position-edit',
    'internship-guidance-new', 'internship-enterprise-eval-new',
    'internship-agreement-template-new', 'internship-agreement-template-edit'
  ]) {
    assert.match(guard, new RegExp(name))
  }
})

test('Stage B B4 does not clear dirty state merely because a save button was clicked', () => {
  assert.match(guard, /submitWindowUntil = Date\.now\(\) \+ 5000/)
  assert.match(guard, /若请求失败留在原页，dirty 仍保持/)
  assert.match(guard, /markSaved/)
})

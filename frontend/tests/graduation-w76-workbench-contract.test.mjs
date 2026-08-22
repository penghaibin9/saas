import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..')

function text(relative) {
  return fs.readFileSync(path.join(ROOT, relative), 'utf8')
}

test('W7.6 T9 reviewer workbench consumes formal review UnifiedTodo', () => {
  const installer = text('src/modules/workbench/config/graduationW76Workbench.js')
  const main = text('src/main.js')
  const routes = text('src/modules/graduation/routes.js')

  assert.match(installer, /GD_FORMAL_REVIEW/)
  assert.match(installer, /正式评阅待办/)
  assert.match(installer, /\/admin\/graduation\/review-tasks\?caseType=FORMAL_REVIEW/)
  assert.match(installer, /RECIPES\.GD_REVIEWER/)
  assert.match(installer, /TODO_TYPE_ROUTES\[FORMAL_REVIEW_TODO\]/)
  assert.match(main, /installGraduationW76Workbench\(\)/)
  assert.match(routes, /path: 'review-tasks'/)
  assert.match(routes, /name: 'graduation-review-tasks'/)
})

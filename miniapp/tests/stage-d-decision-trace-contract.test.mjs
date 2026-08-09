import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('Stage D request transport preserves top-level decisionTrace', () => {
  const source = read('src/services/request.js')
  assert.match(source, /decisionTrace:\s*body\.decisionTrace/)
})

test('student selection renders backend DecisionTrace instead of inventing remedies', () => {
  const source = read('src/pages/student/academic-affairs/selection.vue')
  assert.match(source, /MobileAcademicDecisionCard/)
  assert.match(source, /decisionError/)
  assert.match(source, /e\.decisionTrace/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student graduation renders explanation from the shared evaluator response', () => {
  const source = read('src/pages/student/academic-affairs/graduation.vue')
  assert.match(source, /MobileAcademicDecisionCard/)
  assert.match(source, /data\.decisionTrace/)
  assert.match(source, /data\.decisionText/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student decision card hides audit metadata unless audience is teacher/admin', () => {
  const source = read('src/components/MobileAcademicDecisionCard.vue')
  assert.match(source, /audience:\s*\{\s*type:\s*String,\s*default:\s*'student'/)
  assert.match(source, /this\.audience === 'teacher' \|\| this\.audience === 'admin'/)
  assert.match(source, /trace\.availableResolutions/)
  assert.doesNotMatch(source, /tenantId|rawScope|permissionCodes|sql/i)
})

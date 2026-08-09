import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('Stage D student portal transport preserves top-level decisionTrace', () => {
  const source = read('src/services/request.js')
  assert.match(source, /e\.decisionTrace\s*=\s*payload\.decisionTrace/)
})

test('student selection renders backend DecisionTrace without inventing remedies', () => {
  const source = read('src/views/academic/StudentSelectionView.vue')
  assert.match(source, /AcademicDecisionTraceCard/)
  assert.match(source, /decisionError/)
  assert.match(source, /e\?\.decisionTrace/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student decision card only renders student-safe business explanation fields', () => {
  const source = read('src/components/academic/AcademicDecisionTraceCard.vue')
  assert.match(source, /trace\?\.availableResolutions/)
  assert.match(source, /content\?\.nextStep/)
  assert.doesNotMatch(source, /traceId|tenantId|rawScope|permissionCodes|evaluatedAt|ruleVersion|sql/i)
})

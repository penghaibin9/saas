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
  assert.match(source, /规则校验/)
  assert.match(source, /办理后回读/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student graduation has a dedicated polished view but keeps the same route and server truth', () => {
  const route = read('src/router/academicRoutes.js')
  const source = read('src/views/academic/StudentGraduationAuditView.vue')
  assert.match(route, /path:\s*'graduation'/)
  assert.match(route, /StudentGraduationAuditView\.vue/)
  assert.match(source, /portalApi\.academicGraduationAudit\(\)/)
  assert.match(source, /progress\.decisionTrace/)
  assert.match(source, /progress\.decisionText/)
  assert.match(source, /AcademicDecisionTraceCard/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
  assert.doesNotMatch(source, /evaluate_student|GraduationEvaluationRun|GraduationDecisionFact/)
})

test('student decision card only renders student-safe business explanation fields', () => {
  const source = read('src/components/academic/AcademicDecisionTraceCard.vue')
  assert.match(source, /trace\?\.availableResolutions/)
  assert.match(source, /content\?\.nextStep/)
  assert.match(source, /结果来自学校业务规则实时校验/)
  assert.doesNotMatch(source, /traceId|tenantId|rawScope|permissionCodes|evaluatedAt|ruleVersion|sql/i)
})

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
  assert.match(source, /e && e\.decisionTrace/)
  assert.match(source, /实时余量/)
  assert.match(source, /规则校验/)
  assert.match(source, /办理后回读/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student graduation always shows shared evaluator self-check even before formal audit', () => {
  const source = read('src/pages/student/academic-affairs/graduation.vue')
  assert.match(source, /MobileAcademicDecisionCard/)
  assert.match(source, /data\.decisionTrace/)
  assert.match(source, /data\.decisionText/)
  assert.match(source, /尚未纳入正式预审/)
  assert.match(source, /items\(\).*data\.items/s)
  assert.doesNotMatch(source, /v-if="!data\.hasAudit"/)
  assert.doesNotMatch(source, /availableResolutions\s*=|availableResolutions\.push/)
})

test('student decision card hides audit metadata and technical details require advanced audience', () => {
  const source = read('src/components/MobileAcademicDecisionCard.vue')
  assert.match(source, /audience:\s*\{\s*type:\s*Object|audience:\s*\{\s*type:\s*String/)
  assert.match(source, /showRuleMeta\(\) \{ return this\.audience !== 'student' \}/)
  assert.match(source, /this\.audience === 'admin' \|\| this\.audience === 'platformAdmin'/)
  assert.match(source, /this\.trace\.availableResolutions/)
  assert.match(source, /结果来自学校业务规则实时校验/)
  assert.match(source, /v-if="showRuleMeta"/)
  assert.match(source, /canViewTechnicalMeta && technicalOpen/)
  assert.doesNotMatch(source, /tenantId|rawScope|permissionCodes|sql/i)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  EXCLUDED_LEGACY_HELP_IDS,
  LEGACY_HELP_EXCLUSIONS,
  VERIFIED_HELP_FLOW_OVERRIDES
} from '../help/legacyHelpPolicy.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

test('legacy policy quarantines confirmed stale generic docs and flows', () => {
  for (const id of [
    'doc-student-affairs',
    'doc-orientation',
    'doc-campus-leave',
    'doc-academic',
    'doc-graduation',
    'doc-internship',
    'flow-academic-warning',
    'flow-graduation',
    'flow-internship'
  ]) {
    assert.equal(EXCLUDED_LEGACY_HELP_IDS.has(id), true, id)
  }

  assert.match(LEGACY_HELP_EXCLUSIONS.docs['doc-academic'], /真实代码|推翻|成绩组成/)
  assert.match(LEGACY_HELP_EXCLUSIONS.flows['flow-academic-warning'], /失真/)
})

test('runtime removes quarantined ids from search arrays and sidebar sections', () => {
  assert.match(runtimeSource, /removeIdsInPlace\(HELP_DOCS, docIds\)/)
  assert.match(runtimeSource, /removeIdsInPlace\(HELP_FLOWS, flowIds\)/)
  assert.match(runtimeSource, /BASE_HELP_SECTIONS\.forEach/)
  assert.match(runtimeSource, /EXCLUDED_LEGACY_HELP_IDS\.has/)
})

test('internship score flow is corrected instead of silently deleted', () => {
  const flow = VERIFIED_HELP_FLOW_OVERRIDES['flow-in-score']
  const text = JSON.stringify(flow)

  assert.match(text, /打卡/)
  assert.match(text, /周报/)
  assert.match(text, /月报总结/)
  assert.match(text, /已审核企业评价/)
  assert.match(text, /学校评价/)
  assert.match(text, /严格合计 100/)
  assert.match(text, /待复核/)
  assert.match(text, /撤回/)
  assert.match(text, /已归档成绩不能直接重算/)
  assert.doesNotMatch(text, /学生自评/)
  assert.doesNotMatch(text, /指导教师评价按权重合成/)
})

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
    'flow-orientation',
    'flow-academic-warning',
    'flow-graduation',
    'flow-internship'
  ]) {
    assert.equal(EXCLUDED_LEGACY_HELP_IDS.has(id), true, id)
  }

  assert.deepEqual(LEGACY_HELP_EXCLUSIONS.cards, {})
  assert.match(LEGACY_HELP_EXCLUSIONS.docs['doc-academic'], /真实代码|推翻|成绩组成/)
  assert.match(LEGACY_HELP_EXCLUSIONS.flows['flow-orientation'], /未逐项核验|设计阶段/)
  assert.match(LEGACY_HELP_EXCLUSIONS.flows['flow-academic-warning'], /失真/)
})

test('runtime removes quarantined card, doc and flow ids from search arrays and sidebar sections', () => {
  assert.match(runtimeSource, /removeIdsInPlace\(BASE_HELP_CARDS, cardIds\)/)
  assert.match(runtimeSource, /removeIdsInPlace\(HELP_DOCS, docIds\)/)
  assert.match(runtimeSource, /removeIdsInPlace\(HELP_FLOWS, flowIds\)/)
  assert.match(runtimeSource, /BASE_HELP_SECTIONS\.forEach/)
  assert.match(runtimeSource, /EXCLUDED_LEGACY_HELP_IDS\.has/)
})

test('leave flow is corrected to current 3 and 7 day workflow thresholds with return follow-up', () => {
  const flow = VERIFIED_HELP_FLOW_OVERRIDES['flow-leave']
  const text = JSON.stringify(flow).toLowerCase()

  assert.match(text, /≤3天仅辅导员/)
  assert.match(text, />3且≤7天为辅导员→学院/)
  assert.match(text, />7天为辅导员→学院→学工处/)
  assert.match(text, /returned/)
  assert.match(text, /修改后重新提交/)
  assert.match(text, /续假/)
  assert.match(text, /wait_cancel_leave/)
  assert.match(text, /allowedactions/)
})

test('student affairs risk flow is corrected instead of keeping fixed 72-hour claim', () => {
  const flow = VERIFIED_HELP_FLOW_OVERRIDES['flow-sa-risk']
  const text = JSON.stringify(flow).toLowerCase()

  assert.match(text, /按风险等级/)
  assert.match(text, /当前生效 sla/)
  assert.match(text, /assignhours/)
  assert.match(text, /processhours/)
  assert.match(text, /followhours/)
  assert.match(text, /自动分派/)
  assert.match(text, /自动升级/)
  assert.match(text, /escalated/)
  assert.doesNotMatch(text, /分派后72小时未处置自动升级/)
})

test('student affairs archive flow uses real package manifest and sha semantics', () => {
  const flow = VERIFIED_HELP_FLOW_OVERRIDES['flow-sa-archive']
  const text = JSON.stringify(flow).toLowerCase()

  assert.match(text, /draft → collecting → college_review → sa_confirm → archived/)
  assert.match(text, /xlsx/)
  assert.match(text, /manifest/)
  assert.match(text, /sha-256/)
  assert.match(text, /导出任务/)
  assert.match(text, /未就绪档案.*不能进入最终归档/)
  assert.doesNotMatch(text, /加密水印档案包/)
  assert.doesNotMatch(text, /无驳回分支/)
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

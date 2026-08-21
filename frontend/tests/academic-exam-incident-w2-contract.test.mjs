import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const api = readFileSync(
  new URL('../src/modules/academicAffairs/api/academic-exam-incident.api.js', import.meta.url),
  'utf8'
)
const workbench = readFileSync(
  new URL('../src/modules/academicAffairs/components/AaExamIncidentWorkbench.vue', import.meta.url),
  'utf8'
)
const consoleView = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaExamConsoleView.vue', import.meta.url),
  'utf8'
)

test('W2 API consumes canonical workbench and formal resolve command', () => {
  assert.match(api, /\/academic-affairs\/exam\/incidents/)
  assert.match(api, /\/workbench/)
  assert.match(api, /\/resolve/)
  assert.match(api, /method:\s*'POST'/)
  assert.match(api, /disciplineCaseRef/)
})

test('existing exam console mounts W2 workbench as its single incident consumer', () => {
  assert.match(consoleView, /AaExamIncidentWorkbench/)
  assert.match(consoleView, /<AaExamIncidentWorkbench/)
  assert.doesNotMatch(consoleView, /v-for="i in incidents"/)
  assert.doesNotMatch(consoleView, /api\.listIncidents\(/)
})

test('W2 workbench exposes full lifecycle, server filters and authoritative refresh', () => {
  for (const text of ['待处置', '已闭环', '已作废', '异常类型', '学生 / 课程 / 考场', '考试日期']) {
    assert.match(workbench, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(workbench, /HANDOFF/)
  assert.match(workbench, /CLOSE/)
  assert.match(workbench, /VOID/)
  assert.match(workbench, /academicAffairs\.exam\.recordAbnormal/)
  assert.match(workbench, /closureEvidenceConsistent/)
  assert.match(workbench, /await this\.load\(\)/)
  assert.doesNotMatch(workbench, /row\.closureStatus\s*=/)
  assert.doesNotMatch(workbench, /splice\([^)]*closure/i)
})

test('high-risk decisions require explicit reason confirmation', () => {
  assert.match(workbench, /AppConfirmDialog/)
  assert.match(workbench, /:require-reason="true"/)
  assert.match(workbench, /:reason-min-length="5"/)
  assert.match(workbench, /处分 \/ 后续处理线索编号/)
  assert.match(workbench, /确认正式关闭缺考异常/)
  assert.match(workbench, /确认作废异常登记/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue', import.meta.url)
const constantsUrl = new URL('../src/modules/academicAffairs/constants/grade-graduation.js', import.meta.url)

test('Stage D 毕业审核首屏只使用现有五个批次事实给出办理优先级', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    '毕业审核批次健康概览',
    '当前结论',
    '建议下一动作',
    '终审覆盖度',
    'currentBatch?.total',
    'currentBatch?.passed',
    'currentBatch?.abnormal',
    'currentBatch?.concluded',
    'currentBatch?.archived',
    'batchHealthLabel',
    'batchNextAction',
    'finalProgressPct'
  ]) assert.ok(source.includes(token), `missing Stage D overview token: ${token}`)

  assert.doesNotMatch(source, /<DecisionTrace|import .*DecisionTrace|healthScore|健康分|模拟通过率|mock chart/i)
})

test('Stage D 毕业审核不得把系统通过冒充最终毕业结论', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.match(source, /系统通过/)
  assert.match(source, /已形成正式终审结论/)
  assert.match(source, /unconcludedCount/)
  assert.match(source, /延毕等结论按既有规则不强制进入本次归档/)
})

test('Stage D 毕业审核保留学院初审、不可逆终审、费用 UNKNOWN 与归档真动作', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    "academicAffairsApi.collegeReviewGrad",
    "academicAffairsApi.finalGrad(this.detail.row.resultId, this.finalConclusion, true)",
    "academicAffairsApi.archiveGradBatch(this.batchId)",
    "费用结清默认 UNKNOWN（不阻断）",
    "涉学籍终态，不可在本页撤销",
    "GRAD_FAIL_GROUPS"
  ]) assert.ok(source.includes(token), `missing graduation truth guard: ${token}`)
})

test('D-W0 ARCHIVE 展示必须指向学工归档语义而非迎新归档', async () => {
  const source = await readFile(constantsUrl, 'utf8')
  assert.match(source, /ARCHIVE:\s*'学工归档'/)
  assert.doesNotMatch(source, /ARCHIVE:\s*'迎新归档'/)
  assert.match(source, /十一项供数/)
})

test('Stage D 毕业审核详情与首屏均有响应式商业化收口', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.match(source, /grid-template-columns: repeat\(5, minmax\(0, 1fr\)\)/)
  assert.match(source, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(source, /@media \(max-width: 1080px\)/)
  assert.match(source, /@media \(max-width: 760px\)/)
  assert.match(source, /@media \(max-width: 520px\)/)
})


test('D-W0 SYSTEM_ABNORMAL 不得暴露普通毕业终审动作', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'canNormalFinal(row)',
    "r.status === 'ACADEMIC_REVIEW' && r.overall === 'SYSTEM_PASSED'",
    '系统异常 · 先治理阻断项',
    '普通教务终审不可用审核备注覆盖评估结论',
    '正式例外必须走独立 Override 流程'
  ]) assert.ok(source.includes(token), `missing D-W0 final guard token: ${token}`)
  assert.doesNotMatch(source, /v-if="detail\.row\.status === 'ACADEMIC_REVIEW'" class="agc-actions"/)
})

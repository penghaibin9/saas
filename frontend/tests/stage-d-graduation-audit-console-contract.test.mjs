import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue', import.meta.url)
const resultUrl = new URL('../src/modules/academicAffairs/views/AaGraduationResultView.vue', import.meta.url)
const constantsUrl = new URL('../src/modules/academicAffairs/constants/grade-graduation.js', import.meta.url)
const batchUrl = new URL('../src/modules/academicAffairs/views/AaGraduationBatchView.vue', import.meta.url)
const termArchiveUrl = new URL('../src/modules/academicAffairs/views/AaTermArchiveView.vue', import.meta.url)

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

test('D-W0/W1 可达入口必须显示十一项毕业预审与十三域教务归档', async () => {
  const [batchSource, termArchiveSource] = await Promise.all([
    readFile(batchUrl, 'utf8'),
    readFile(termArchiveUrl, 'utf8')
  ])
  assert.match(batchSource, /十一项供数三态预审/)
  assert.match(batchSource, /执行十一项预审/)
  assert.match(batchSource, /学工归档\/费用/)
  assert.match(batchSource, /只有最新完整正式 Run 为 SYSTEM_PASSED 才能学院通过并进入教务终审/)
  assert.doesNotMatch(batchSource, /十项供数|执行十项预审/)
  assert.match(termArchiveSource, /13数据域完整性检查/)
  assert.match(termArchiveSource, /13 数据域完整性检查/)
  assert.match(termArchiveSource, /归档后发现错误必须走纠错版本链，不普通解冻/)
  assert.doesNotMatch(termArchiveSource, /9数据域|9 数据域|特批解冻/)
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

test('D-W0 预审结果页学院通过与普通终审都必须绑定完整 SYSTEM_PASSED', async () => {
  const source = await readFile(resultUrl, 'utf8')
  for (const token of [
    'canCollegeApprove(r)',
    "r.overall === 'SYSTEM_PASSED'",
    'canNormalFinal(r)',
    "r.status === 'ACADEMIC_REVIEW' && r.overall === 'SYSTEM_PASSED'",
    '系统异常须先治理阻断项并重新预审，不能直接学院通过',
    '系统异常 · 普通教务终审不可用'
  ]) assert.ok(source.includes(token), `missing result-view W0 guard token: ${token}`)
  assert.doesNotMatch(source, /v-if="r\.status === 'ACADEMIC_REVIEW'" variant="primary" @click="openFinal\(r\)"/)
})

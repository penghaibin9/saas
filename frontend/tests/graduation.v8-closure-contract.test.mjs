import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('dashboard concrete work exposes the complete human handoff context', async () => {
  const source = await read('../src/modules/graduation/views/GraduationDashboardView.vue')
  for (const token of ['firstWorkItem.whyHere', 'firstWorkItem.waitingOn', 'firstWorkItem.nextActor', 'firstWorkItem.recentChange', 'firstWorkItem.primaryAction']) {
    assert.ok(source.includes(token), `missing promoted dashboard flow context ${token}`)
  }
  assert.match(source, /<b>当前等待<\/b>/)
  assert.match(source, /<b>下一责任人<\/b>/)
  assert.match(source, /@click="goWorkItem\(firstWorkItem\)"/)
  assert.match(source, /remainingWorkItems\(\) \{ return this\.workItems\.slice\(1\) \}/)
})

test('material and review writes expose human receipts backed by server readback', async () => {
  const [materials, proposal, finalReview] = await Promise.all([
    read('../src/modules/graduation/views/GraduationMaterialCenterView.vue'),
    read('../src/modules/graduation/views/_shared/ProposalReviewCard.vue'),
    read('../src/modules/graduation/views/FinalSubmissionListView.vue')
  ])
  assert.match(materials, /stageLabel\(row\.stage\)/)
  assert.match(materials, /scanLabel\(row\.scanStatus\)/)
  assert.match(materials, /<details/)
  assert.match(materials, /actionReceipt/)
  assert.match(materials, /readReviewTruth/)
  assert.match(materials, /api\.studentLibrary\(target\.gdStudentId, true\)/)
  assert.match(materials, /服务器材料台账尚未回读到目标状态/)
  for (const source of [proposal, finalReview]) {
    assert.match(source, /reviewReceipt/)
    assert.match(source, /await this\.load/)
  }
  for (const source of [materials, proposal, finalReview]) {
    assert.match(source, /服务器最新/)
  }
})

test('defense publish performs full preflight and returns durable delivery receipts', async () => {
  const source = await read('../src/modules/graduation/views/DefenseScheduleView.vue')
  for (const token of ['missingJudges', 'conflicts', 'missingLocation', 'missingTime', 'missingSecretary', 'students']) {
    assert.ok(source.includes(token), `missing defense preflight field ${token}`)
  }
  assert.match(source, /await this\.load\(\)/)
  assert.match(source, /不要重复发布/)
  assert.match(source, /服务器最新状态/)
  assert.match(source, /服务器回执：已送达/)
  assert.match(source, /memberNames\(row\)/)
})

test('grade appeals show the bound published version and block stale mutations', async () => {
  const source = await read('../src/modules/graduation/views/GraduationMoreView.vue')
  for (const token of ['appealedGrade', 'currentGrade', 'versionMatches', 'versionMessage', '查看当前成绩']) {
    assert.ok(source.includes(token), `missing appeal evidence token ${token}`)
  }
  assert.match(source, /if \(!row\.versionMatches\) return/)
  assert.match(source, /source: 'grade-appeal'/)
})

test('archive writes use frozen identifiers and unknown outcomes never invite blind retry', async () => {
  const source = await read('../src/modules/graduation/views/GraduationRiskArchiveView.vue')
  assert.match(source, /createSingleArchiveSnapshot\(action, row\)/)
  assert.match(source, /gdStudentId: String\(row\?\.gdStudentId \|\| ''\)/)
  assert.match(source, /archiveBatchNo: row\?\.archiveBatchNo \|\| ''/)
  assert.match(source, /fileArchive\(\s*snapshot\.gdStudentId,\s*snapshot\.archiveBatchNo \|\| null,\s*\{ batchId: snapshot\.batchId \}\s*\)/)
  assert.match(source, /\[503001, 503002\]\.includes\(Number\(res\?\.code\)\)/)
  assert.match(source, /不要(?:直接)?重复(?:点击|提交)/)
  assert.match(source, /刷新(?:归档)?台账核对/)
  assert.match(source, /必须重新预览/)
  assert.match(source, /archiveWriteFailed/)
})

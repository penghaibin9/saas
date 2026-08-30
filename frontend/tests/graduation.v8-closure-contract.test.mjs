import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('dashboard concrete work exposes the complete human handoff context', async () => {
  const source = await read('../src/modules/graduation/views/GraduationDashboardView.vue')
  for (const token of ['item.whyHere', 'item.waitingOn', 'item.nextActor', 'item.recentChange', 'item.primaryAction']) {
    assert.ok(source.includes(token), `missing dashboard flow context ${token}`)
  }
  assert.match(source, /当前等待：/)
  assert.match(source, /下一棒：/)
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
  for (const source of [proposal, finalReview]) {
    assert.match(source, /reviewReceipt/)
  }
  assert.match(materials, /await load\(\)/)
  for (const source of [proposal, finalReview]) {
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
  assert.match(source, /无需重复点击/)
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

test('archive writes use idempotent identifiers and unknown outcomes never invite blind retry', async () => {
  const source = await read('../src/modules/graduation/views/GraduationRiskArchiveView.vue')
  assert.match(source, /fileArchive\(row\.gdStudentId, row\.archiveBatchNo \|\| null\)/)
  assert.match(source, /503001 \|\| Number\(res\?\.code\) === 503002/)
  assert.match(source, /不要重复点击/)
  assert.match(source, /刷新台账核对/)
  assert.match(source, /必须重新预览/)
})

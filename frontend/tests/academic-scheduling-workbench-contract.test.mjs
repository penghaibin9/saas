import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('scheduling opens on one end-to-end workbench instead of isolated feature tabs', () => {
  const source = read('src/modules/academicAffairs/views/AaSchedulingConsoleView.vue')

  assert.match(source, /tab: 'workbench'/)
  for (const label of ['数据准备', '教师偏好', '自动初排', '人工微调', '冲突与漏排', '预发布', '正式发布']) {
    assert.ok(source.includes(label), `missing workflow stage: ${label}`)
  }
  assert.ok(source.includes('当前阻断原因'))
  assert.ok(source.includes('下一步：'))
})

test('task queue routes with internal context and never asks the registrar for IDs', () => {
  const consoleSource = read('src/modules/academicAffairs/views/AaSchedulingConsoleView.vue')
  const maintainSource = read('src/modules/academicAffairs/views/AaScheduleMaintainView.vue')

  assert.match(consoleSource, /query: \{ classId: row\.classId, className: row\.className \|\| '', taskId: row\.taskId \}/)
  assert.match(maintainSource, /this\.(preferredTaskId|classId) = String\(this\.\$route\?\.query\?/)
  assert.ok(maintainSource.includes('已从排课工作台定位任务'))
  assert.doesNotMatch(consoleSource, /请输入.*(?:班级|教学任务).*ID/)
})

test('published batch-wide defects open a safe correction draft instead of taking four-end truth offline', () => {
  const source = read('src/modules/academicAffairs/views/AaSchedulingConsoleView.vue')
  const api = read('src/modules/academicAffairs/api/academic-affairs.api.js')

  assert.ok(source.includes("workbench.batchStatus === 'PUBLISHED'"))
  assert.ok(source.includes('漏排任务处理中心'))
  assert.ok(source.includes('当前正式课表不下线'))
  assert.ok(source.includes('老师学生 PC 和老师学生小程序继续使用当前正式课表'))
  assert.ok(source.includes('创建纠错草稿（保留已排'))
  assert.ok(source.includes('创建草稿后补排'))
  assert.ok(source.includes("matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.schedule.edit')"))
  assert.ok(source.includes('当前身份只能查看漏排'))
  assert.match(source, /academicAffairsApi\.startScheduleCorrection\(sourceBatchId/)
  assert.ok(source.includes("code === 'BATCH_REISSUE'"))
  assert.match(source, /code === 'BATCH_REISSUE'\) return this\.openCorrectionDraft\(\)/)
  assert.match(api, /schedule-batches\/\$\{batchId\}\/correction-draft/)
  assert.doesNotMatch(source, /intent: 'major-correction'/)
})

test('pre-publish and publish actions are gated by the canonical completeness checklist', () => {
  const source = read('src/modules/academicAffairs/views/AaSchedulePublishView.vue')

  assert.match(source, /检查并预发布/)
  assert.match(source, /检查并正式发布/)
  assert.match(source, /复核发布门禁/)
  assert.match(source, /academicAffairsApi\.getScheduleSummary\(row\.batchId\)/)
  for (const label of ['教学任务可排', '应排节次完整', '课位关联有效', '硬冲突清零']) {
    assert.ok(source.includes(label), `missing publish gate: ${label}`)
  }
  assert.match(source, /if \(!this\.gate\.summary\?\.complete/)
  assert.doesNotMatch(source, /\{ key: 'batchId', title: '批次ID' \}/)
})

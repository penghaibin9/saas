import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const root = new URL('../src/modules/academicAffairs/', import.meta.url)

async function source(path) {
  return readFile(new URL(path, root), 'utf8')
}

test('AA-171/173/174 use distinct exam, defer and archive workspaces on their original URL', async () => {
  const view = await source('views/AaExamConsoleView.vue')
  assert.match(view, /tab === 'defer' \? 'defer' : tab === 'archive' \? 'archive' : 'exam'/)
  assert.match(view, /api\.deferList\(/)
  assert.match(view, /api\.listArchived\(/)
  assert.match(view, /学生发起缓考/)
  assert.match(view, /已封存考试批次/)
  assert.match(view, /completenessSummary/)
})

test('AA-171 large exam course lists stay on the canonical paginated read path', async () => {
  const view = await source('views/AaExamConsoleView.vue')
  assert.match(view, /coursePagination:\s*\{ page: 1, pageSize: 20, total: 0 \}/)
  assert.match(view, /api\.listCourses\(id, \{ page: this\.coursePagination\.page, pageSize: this\.coursePagination\.pageSize \}\)/)
  assert.match(view, /@page-change="onCoursePageChange"/)
})

test('AA-172 only prints a deep-linked official room and protects route races', async () => {
  const view = await source('views/AaExamSeatingPrintView.vue')
  assert.match(view, /formalRoomPrint\(id\)/)
  assert.match(view, /documentStatus !== 'OFFICIAL'/)
  assert.match(view, /'\$route\.query\.roomId'/)
  assert.match(view, /seq === this\.loadSeq && id === String\(this\.roomId/)
})

test('AA-175 locks lifecycle and fee confirmations to the selected level exam', async () => {
  const view = await source('views/AaLevelExamView.vue')
  assert.match(view, /LEVEL-EXAM-/)
  assert.match(view, /const exam = \{ \.\.\.this\.current \}/)
  assert.match(view, /exam\.examId !== this\.current\?\.examId/)
  assert.match(view, /const registration = \{ \.\.\.row \}/)
  assert.match(view, /detailSeq/)
})

test('exam local object and stage components expose the required responsibility chain', async () => {
  const [objectBar, stageRail] = await Promise.all([
    source('components/exam/AaExamObjectBar.vue'),
    source('components/exam/AaExamStageRail.vue')
  ])
  // 对象摘要收成一行：保留状态、责任人、阻断和下一岗位，不再展示来源说明和内部编号
  for (const label of ['status', '当前责任人', '当前阻断', '下一责任岗位']) {
    assert.match(objectBar, new RegExp(label))
  }
  assert.doesNotMatch(objectBar, /\{\{ objectId|\{\{ source/)
  assert.match(stageRail, /activeIndex/)
  assert.match(stageRail, /is-active/)
})

test('AA-176/177/178 shared makeup page exposes source, blocker, responsibility and return context', async () => {
  const view = await source('views/AaMakeupConsoleView.vue')
  // 自证文字（对象来源、为什么轮到我、返回位置）已删除，保留责任、阻断和下一岗位
  for (const label of ['当前责任', '当前阻断', '下一责任岗位']) {
    assert.match(view, new RegExp(label))
  }
  assert.match(view, /选择正式不及格成绩/)
  assert.match(view, /按学校政策圈定/)
  assert.match(view, /学生申请缓考/)
  assert.match(view, /row\.nextBatchRef \? '已合流' : '待安排'/)
})

test('an already merged deferred request no longer offers another merge command', async () => {
  const view = await source('views/AaMakeupConsoleView.vue')
  assert.match(view, /canManage && !row\.nextBatchRef/)
  assert.match(view, /刷新查看/)
})

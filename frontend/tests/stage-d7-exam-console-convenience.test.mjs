import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaExamConsoleView.vue', import.meta.url)
const apiUrl = new URL('../src/modules/academicAffairs/api/exam-convenience.api.js', import.meta.url)

test('D7-U 首屏给出发布就绪结论与关键缺口', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    '应考课程', '已排', '漏排', '监考缺口', '教室不足',
    'eligibleCourseCount', 'arrangedCourseCount', 'missedCourseCount',
    'invigilatorGapCount', 'roomShortageCount', 'canPublish', 'blockingReasons'
  ]) {
    assert.ok(source.includes(token), `missing D7 readiness token: ${token}`)
  }
})

test('D7-U 批量圈课先预览再确认，自动排考与发布继续复用既有动作', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'listCourseCandidates', 'previewCourses', 'confirmCourses', 'previewToken',
    'api.autoArrange', "lc('publishBatch', '发布')"
  ]) {
    assert.ok(source.includes(token), `missing D7 convenience action: ${token}`)
  }
})

test('D7-U convenience API 只调用候选、预览、确认与 readiness 路径', async () => {
  const source = await readFile(apiUrl, 'utf8')
  for (const path of [
    '/readiness', '/course-candidates', '/course-candidates/preview', '/course-candidates/confirm'
  ]) {
    assert.ok(source.includes(path), `missing convenience API path: ${path}`)
  }
})

test('D7-U 考务控制台有桌面与窄屏响应式收口', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.match(source, /@media \(max-width: 1080px\)/)
  assert.match(source, /@media \(max-width: 760px\)/)
  assert.match(source, /aaexam-readiness/)
  assert.match(source, /aaexam-candidate/)
})

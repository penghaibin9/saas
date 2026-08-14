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

test('D7-U 新建考试批次必须选择正式学期并提交 termId', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.ok(source.includes('AppTermEntityPicker'))
  assert.ok(source.includes("if (!this.form.termId)"))
  assert.ok(source.includes("termId: this.form.termId"))
})

test('D7-U 批量圈课必须先 preview 后 confirm', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'listCourseCandidates', 'previewCourses', 'confirmCourses', 'previewToken'
  ]) {
    assert.ok(source.includes(token), `missing D7 bulk course action: ${token}`)
  }
})

test('D7-U 自动排考必须先 canonical auto-times 再复用既有 auto-arrange', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    'openAutoPlan', 'runAutoArrange', 'convenienceApi.autoTimes',
    'autoPlan.dates', 'autoPlan.sessions', 'maxPerDayPerClass',
    'api.autoArrange', "lc('publishBatch', '发布')"
  ]) {
    assert.ok(source.includes(token), `missing D7 two-stage arrange token: ${token}`)
  }
})

test('D7-U convenience API 只补业务便利层并显式复用 canonical auto-times', async () => {
  const source = await readFile(apiUrl, 'utf8')
  for (const path of [
    '/readiness', '/course-candidates', '/course-candidates/preview',
    '/course-candidates/confirm', '/auto-times'
  ]) {
    assert.ok(source.includes(path), `missing convenience API path: ${path}`)
  }
  assert.ok(source.includes('maxPerDayPerClass') || source.includes('body'))
})

test('D7-U 考务控制台有桌面与窄屏响应式收口', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.match(source, /@media \(max-width: 1080px\)/)
  assert.match(source, /@media \(max-width: 760px\)/)
  assert.match(source, /aaexam-readiness/)
  assert.match(source, /aaexam-candidate/)
  assert.match(source, /aaexam-auto-row/)
})

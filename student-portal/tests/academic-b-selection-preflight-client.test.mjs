import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const api = await readFile(new URL('../src/services/portalApi.js', import.meta.url), 'utf8')
const view = await readFile(new URL('../src/views/academic/StudentSelectionView.vue', import.meta.url), 'utf8')

test('学生选课未知状态显示中文提示，不暴露内部状态值', () => {
  const records = view.match(/function recordStatusText\(status\) \{[\s\S]*?\n\}/)[0]
  const courses = view.match(/function courseStatusText\(course\) \{[\s\S]*?\n\}/)[0]
  const labels = new Function(`${records}\n${courses}\nreturn { recordStatusText, courseStatusText }`)()
  assert.equal(labels.recordStatusText('INTERNAL_UNKNOWN'), '状态待确认')
  assert.equal(labels.courseStatusText({ status: 'SELECTED' }), '已取得名额')
  assert.equal(labels.courseStatusText({ status: 'INTERNAL_UNKNOWN' }), '状态待确认')
  assert.equal(labels.courseStatusText({ statusLabel: '待补选' }), '待补选')
})

test('student PC preflights before enroll and renders backend decision trace', () => {
  assert.match(api, /academicSelectionPreflight/)
  const start = view.indexOf('async function enroll(course)')
  const block = view.slice(start, view.indexOf('async function drop', start))
  assert.ok(block.indexOf('academicSelectionPreflight') < block.indexOf('academicEnroll'))
  assert.match(block, /preflight\?\.allowed/)
  assert.match(block, /preflight\?\.decisionTrace/)
  assert.match(view, /AcademicDecisionTraceCard/)
})

test('student PC consumes B-C3 server actions instead of deriving eligibility from capacity/status', () => {
  assert.match(view, /allowedActions/)
  assert.match(view, /statusLabel/)
  assert.match(view, /howToResolve/)
  assert.match(view, /function hasAction\(/)
  assert.match(view, /projectionForRecord/)
  assert.doesNotMatch(view, /function canEnroll\(/)
  assert.doesNotMatch(view, /canEnroll\(course\)/)

  const enrollStart = view.indexOf('async function enroll(course)')
  const enrollBlock = view.slice(enrollStart, view.indexOf('async function drop', enrollStart))
  assert.match(enrollBlock, /hasAction\(course, ['"]ENROLL['"]\)/)

  const dropStart = view.indexOf('async function drop(course)')
  const dropBlock = view.slice(dropStart, view.indexOf('onMounted', dropStart))
  assert.match(dropBlock, /hasAction\(projection, ['"]DROP['"]\)/)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('all 21 student academic entries resolve to student-owned views', () => {
  const routes = read('src/router/academicRoutes.js')
  const paths = ['', 'schedule', 'grades', 'registration', 'selection', 'evaluation', 'recheck', 'status', 'exam', 'makeup', 'attendance', 'calendar', 'clearance', 'credits', 'warning', 'textbook', 'level-exam', 'major-split', 'recognition', 'graduation', 'all']
  for (const path of paths) assert.match(routes, path ? new RegExp(`(?:path: |academicReadOnly\\()'${path}'`) : /path: ''/)
  assert.match(routes, /StudentStatusView\.vue/)
  assert.match(routes, /StudentRecognitionView\.vue/)
  const directory = read('src/views/academic/AcademicLegacySafeView.vue')
  assert.doesNotMatch(directory, /AcademicView/)
  assert.match(directory, /不包含教师管理动作/)
})

test('student action pages keep a business receipt and evaluation starts empty', () => {
  for (const name of ['Selection', 'Evaluation', 'Recheck', 'Status', 'Exam', 'Makeup', 'Textbook', 'LevelExam', 'MajorSplit', 'Recognition']) {
    assert.match(read(`src/views/academic/Student${name}View.vue`), /AcademicBusinessReceipt/)
  }
  const evaluation = read('src/views/academic/StudentEvaluationView.vue')
  assert.match(evaluation, /score: ''/)
  assert.doesNotMatch(evaluation, /score: 90/)
})

test('403 and weak network are explicit local states', () => {
  const helper = read('src/components/academic/studentAcademicUi.js')
  assert.match(helper, /页面已清除先前内容/)
  assert.match(helper, /未把本次结果当作“暂无数据”/)
  assert.match(read('src/views/academic/StudentGradesView.vue'), /transcript\.value = \{ items: \[\] \}/)
  assert.match(read('src/views/academic/StudentScheduleView.vue'), /schedule\.value = \{ items: \[\], timeBands: \[\] \}/)
})
